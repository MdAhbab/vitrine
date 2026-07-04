"""
OpenAI client wrapper — the ONLY place that talks to OpenAI.

Centralizes: model selection, retries/timeouts, token counting, cost accounting
(writes agent_runs), and result caching. Designed to be SAFE WITHOUT A KEY: if
OPENAI_API_KEY is empty it returns deterministic stub output so the whole app
runs offline during development. Flip the key on to go live.

Pricing (gpt-4o-mini, approx): $0.15 / 1M input, $0.60 / 1M output.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from backend.shared.settings import settings

# How long to reuse the admin-configured provider clients before re-reading the
# admin_configs row. Keeps LLM calls off the DB on the hot path while still
# picking up admin key rotations within a few seconds.
_CONFIG_TTL_S = 20.0

_PRICE = {  # USD per 1M tokens (input, output)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = _PRICE.get(model, _PRICE["gpt-4o-mini"])
    return (tokens_in * pin + tokens_out * pout) / 1_000_000


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    stub: bool = False

    @property
    def cost_usd(self) -> float:
        return estimate_cost(self.model, self.tokens_in, self.tokens_out)


class AIClient:
    def __init__(self) -> None:
        self._clients: list = []             # admin-configured provider clients (cached)
        self._cached_hash: int | None = None
        self._configured_at: float = 0.0     # monotonic ts of last DB read
        self._ever_configured: bool = False
        self._default_client = None          # env-key OpenAI client (built once)

    def _default(self):
        """The settings.OPENAI_API_KEY client, constructed once and reused."""
        if settings.OPENAI_API_KEY and self._default_client is None:
            from openai import AsyncOpenAI
            self._default_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._default_client

    async def _resolved_clients(self) -> list[tuple]:
        """(client, provider) list = env-default first, then admin-configured.

        Returns a NEW list each call so callers can prepend without mutating the
        cached admin-client list (the previous code leaked a fresh client into
        the cache on every call). The DB is only read once per _CONFIG_TTL_S.
        """
        clients: list[tuple] = []
        default = self._default()
        if default is not None:
            clients.append((default, "openai"))
        clients.extend(await self._get_configured_clients())
        return clients

    async def _get_configured_clients(self) -> list[tuple]:
        # Serve the cached provider clients without touching the DB inside the TTL.
        if self._ever_configured and (time.monotonic() - self._configured_at) < _CONFIG_TTL_S:
            return self._clients
        try:
            from backend.shared.crypto import decrypt_value
            from backend.shared.db import SessionLocal
            from backend.shared.models import AdminConfig
            import json
            async with SessionLocal() as db:
                row = await db.get(AdminConfig, "api_keys")
                active = ([k for k in row.value if isinstance(k, dict) and k.get("enabled") and k.get("key")]
                          if row and isinstance(row.value, list) else [])
                config_hash = hash(json.dumps([{**k, "key": "MASKED"} for k in active], sort_keys=True))

                if self._cached_hash == config_hash and self._ever_configured:
                    self._configured_at = time.monotonic()
                    return self._clients

                from openai import AsyncOpenAI
                _bases = {
                    "grok": "https://api.x.ai/v1",
                    "nvidia": "https://integrate.api.nvidia.com/v1",
                    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
                }
                clients = []
                for k in active:
                    provider = k.get("provider")
                    raw_key = decrypt_value(k["key"])
                    if not raw_key or provider not in ("openai", "grok", "nvidia", "gemini", "custom"):
                        continue
                    base_url = _bases.get(provider)
                    clients.append((AsyncOpenAI(api_key=raw_key, base_url=base_url) if base_url
                                    else AsyncOpenAI(api_key=raw_key), provider))

                self._clients = clients
                self._cached_hash = config_hash
        except Exception as e:
            print(f"[ai] Client resolve error: {e}")
            # keep last-known clients rather than dropping to none on a transient error
        self._ever_configured = True
        self._configured_at = time.monotonic()
        return self._clients

    async def chat(self, messages: list[dict], *, tools: list | None = None,
                   model: str | None = None, stream: bool = False,
                   json_mode: bool = False) -> LLMResult:

        clients = await self._resolved_clients()

        if not clients:
            return self._stub(messages, model or settings.OPENAI_MODEL)

        last_exc: Exception | None = None
        
        for client, provider in clients:
            # Map standard OpenAI models to provider-specific models if needed
            candidates = self._get_provider_models(provider, model)
            
            for candidate in candidates:
                kwargs: dict = {"model": candidate, "messages": messages, "tools": tools or None}
                if json_mode and not tools:
                    # Not all providers support json_object, but we try
                    if provider in ("openai", "grok"):
                        kwargs["response_format"] = {"type": "json_object"}
                try:
                    resp = await client.chat.completions.create(**kwargs)
                    choice = resp.choices[0].message
                    usage = resp.usage
                    return LLMResult(
                        text=choice.content or "",
                        tool_calls=[tc.model_dump() for tc in (choice.tool_calls or [])],
                        tokens_in=getattr(usage, "prompt_tokens", 0),
                        tokens_out=getattr(usage, "completion_tokens", 0),
                        model=candidate,
                    )
                except Exception as exc:
                    last_exc = exc
                    continue # Try next model or next provider
                    
        assert last_exc is not None
        raise last_exc

    def _get_provider_models(self, provider: str, requested: str | None) -> list[str]:
        if provider == "openai":
            return [requested or settings.OPENAI_MODEL, "gpt-4o-mini", "gpt-4-turbo"]
        elif provider == "grok":
            return ["grok-beta", "grok-2-latest"]
        elif provider == "nvidia":
            return ["meta/llama-3.1-70b-instruct", "nvidia/nemotron-4-340b-instruct"]
        elif provider == "gemini":
            return ["gemini-1.5-flash", "gemini-1.5-pro"]
        return [requested or settings.OPENAI_MODEL]

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model = model or settings.OPENAI_EMBED_MODEL
        clients = await self._resolved_clients()

        # For embeddings, we prefer OpenAI since vector stores expect 1536 dim
        # but let's try the first available client that is OpenAI compatible for embeddings
        for client, provider in clients:
            if provider in ("openai", "gemini"): 
                embed_model = "text-embedding-3-small" if provider == "openai" else "text-embedding-004"
                try:
                    resp = await client.embeddings.create(model=embed_model, input=text)
                    return resp.data[0].embedding
                except Exception:
                    continue
                    
        return _stub_embedding(text)

    @staticmethod
    def _stub(messages: list[dict], model: str) -> LLMResult:
        last = messages[-1]["content"] if messages else ""
        return LLMResult(
            text=f"[stub:{model}] (no OPENAI_API_KEY) echo: {str(last)[:120]}",
            tokens_in=50, tokens_out=20, model=model, stub=True,
        )


def _stub_embedding(text: str, dim: int = 1536) -> list[float]:
    """Deterministic pseudo-embedding so semantic search 'works' offline."""
    import hashlib
    import math

    h = hashlib.sha256(text.encode()).digest()
    vals = [(b / 255.0) - 0.5 for b in h]
    vec = [vals[i % len(vals)] for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


client = AIClient()
