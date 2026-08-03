"""
LLM client wrapper — the ONLY place that talks to a model provider.

Centralizes: provider fallback, model selection, retries/timeouts, token
counting, cost accounting (writes agent_runs), and result caching. Designed to
be SAFE WITHOUT A KEY: if no provider is configured it returns deterministic
stub output so the whole app runs offline during development.

Provider order (first that answers wins):
  1. OpenAI      — settings.OPENAI_API_KEY, model settings.OPENAI_MODEL
  2. Gemini      — settings.GEMINI_API_KEY, walking settings.GEMINI_MODELS in
                   order. Each Gemini model has its own quota, so a 429 on one
                   model moves to the next rather than giving up on Gemini.
  3. Admin-configured keys from the admin_configs `api_keys` row.

Pricing (gpt-4o-mini, approx): $0.15 / 1M input, $0.60 / 1M output.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from backend.shared.settings import settings

# How long to reuse the admin-configured provider clients before re-reading the
# admin_configs row. Keeps LLM calls off the DB on the hot path while still
# picking up admin key rotations within a few seconds.
_CONFIG_TTL_S = 20.0

# Hard ceiling on a single provider call. Without this the SDK default (10 min)
# applies, so one hung upstream connection pins a request — and a worker — for
# the whole window instead of failing over to the next provider.
_REQUEST_TIMEOUT_S = 30.0

# Cap on concurrent in-flight provider calls for this process. The per-IP rate
# limiter bounds request *rate* per client; nothing bounded total concurrency,
# so a burst spread across many users could open unlimited upstream connections
# and trigger provider-side 429 storms. Backpressure belongs here, once.
_MAX_CONCURRENT_CALLS = 8
_call_slot = asyncio.Semaphore(_MAX_CONCURRENT_CALLS)

# Width of every stored listing embedding. Cosine similarity zips the query and
# stored vectors, so all providers must agree on this number.
EMBED_DIM = 1536

# Base URLs for OpenAI-compatible providers.
PROVIDER_BASE_URLS = {
    "grok": "https://api.x.ai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

_PRICE = {  # USD per 1M tokens (input, output)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    # gemini fallbacks
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-3-flash-preview": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.10, 0.40),
    "gemini-3.5-flash": (0.30, 2.50),
    "gemini-3.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3-pro-preview": (2.00, 12.00),
    "gemini-3.1-pro-preview": (2.00, 12.00),
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
    provider: str = ""
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
        self._env_clients: list | None = None  # env-key clients (built once)

    def _default(self) -> list[tuple]:
        """Env-key clients in fallback order: OpenAI first, then Gemini.

        Built once and reused. Returns [] when neither key is set, which is what
        drives the offline stub path.
        """
        if self._env_clients is None:
            from openai import AsyncOpenAI
            built: list[tuple] = []
            if settings.OPENAI_API_KEY:
                built.append((AsyncOpenAI(api_key=settings.OPENAI_API_KEY,
                                          timeout=_REQUEST_TIMEOUT_S), "openai"))
            if settings.GEMINI_API_KEY:
                built.append((AsyncOpenAI(api_key=settings.GEMINI_API_KEY,
                                          base_url=PROVIDER_BASE_URLS["gemini"],
                                          timeout=_REQUEST_TIMEOUT_S), "gemini"))
            self._env_clients = built
        return self._env_clients

    async def _resolved_clients(self) -> list[tuple]:
        """(client, provider) list = env-defaults first, then admin-configured.

        Returns a NEW list each call so callers can prepend without mutating the
        cached admin-client list (the previous code leaked a fresh client into
        the cache on every call). The DB is only read once per _CONFIG_TTL_S.
        """
        clients: list[tuple] = list(self._default())
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
                _bases = PROVIDER_BASE_URLS
                clients = []
                for k in active:
                    provider = k.get("provider")
                    raw_key = decrypt_value(k["key"])
                    if not raw_key or provider not in ("openai", "grok", "nvidia", "gemini", "custom"):
                        continue
                    base_url = _bases.get(provider)
                    clients.append((AsyncOpenAI(api_key=raw_key, base_url=base_url,
                                                timeout=_REQUEST_TIMEOUT_S), provider))

                self._clients = clients
                self._cached_hash = config_hash
        except Exception as e:
            print(f"[ai] Client resolve error: {e}")
            # keep last-known clients rather than dropping to none on a transient error
        self._ever_configured = True
        self._configured_at = time.monotonic()
        return self._clients

    async def chat(self, messages: list[dict], *, tools: list | None = None,
                   model: str | None = None, json_mode: bool = False) -> LLMResult:

        clients = await self._resolved_clients()

        if not clients:
            return self._stub(model or settings.OPENAI_MODEL)

        last_exc: Exception | None = None

        for client, provider in clients:
            # Map standard OpenAI models to provider-specific models if needed
            candidates = self._get_provider_models(provider, model)

            for candidate in candidates:
                kwargs: dict = {"model": candidate, "messages": messages, "tools": tools or None}
                if json_mode and not tools:
                    # Gemini's OpenAI-compat endpoint honours json_object too.
                    if provider in ("openai", "grok", "gemini"):
                        kwargs["response_format"] = {"type": "json_object"}
                try:
                    async with _call_slot:
                        resp = await asyncio.wait_for(
                            client.chat.completions.create(**kwargs),
                            timeout=_REQUEST_TIMEOUT_S,
                        )
                    choice = resp.choices[0].message
                    usage = resp.usage
                    if last_exc is not None:
                        print(f"[ai] fell back to {provider}/{candidate} after: {last_exc}")
                    return LLMResult(
                        text=choice.content or "",
                        tool_calls=[tc.model_dump() for tc in (choice.tool_calls or [])],
                        tokens_in=getattr(usage, "prompt_tokens", 0),
                        tokens_out=getattr(usage, "completion_tokens", 0),
                        model=candidate,
                        provider=provider,
                    )
                except Exception as exc:
                    last_exc = exc
                    continue # Try next model or next provider

        # Every provider/model failed. Degrade to the offline stub instead of
        # 500-ing the caller: agents already know how to handle stub output, and
        # a transient upstream outage should not take the whole app down.
        print(f"[ai] all providers failed ({last_exc}); serving stub")
        return self._stub(model or settings.OPENAI_MODEL)

    def _get_provider_models(self, provider: str, requested: str | None) -> list[str]:
        if provider == "openai":
            return [requested or settings.OPENAI_MODEL, "gpt-4o-mini", "gpt-4-turbo"]
        elif provider == "grok":
            return ["grok-beta", "grok-2-latest"]
        elif provider == "nvidia":
            return ["meta/llama-3.1-70b-instruct", "nvidia/nemotron-4-340b-instruct"]
        elif provider == "gemini":
            # Each model carries its own quota — walk the configured priority
            # list so a 429 on one model rolls to the next instead of failing.
            return settings.gemini_models
        return [requested or settings.OPENAI_MODEL]

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        clients = await self._resolved_clients()

        # Stored vectors are 1536-dim and cosine similarity zips the two lists,
        # so a provider returning a different width would silently score
        # garbage. Pin every provider to EMBED_DIM and drop any reply that
        # isn't that width.
        for client, provider in clients:
            if provider not in ("openai", "gemini"):
                continue
            if provider == "openai":
                embed_model = model or settings.OPENAI_EMBED_MODEL
                kwargs = {"model": embed_model, "input": text, "dimensions": EMBED_DIM}
            else:
                embed_model = settings.GEMINI_EMBED_MODEL
                kwargs = {"model": embed_model, "input": text, "dimensions": EMBED_DIM}
            try:
                async with _call_slot:
                    resp = await asyncio.wait_for(
                        client.embeddings.create(**kwargs), timeout=_REQUEST_TIMEOUT_S
                    )
                vec = resp.data[0].embedding
                if len(vec) != EMBED_DIM:
                    continue
                return vec
            except Exception:
                continue

        return _stub_embedding(text)

    @staticmethod
    def _stub(model: str) -> LLMResult:
        # Deliberately does NOT echo the prompt. Callers must gate on `.stub`,
        # but any that forget would otherwise republish prompt content — the
        # negotiator's prompt opens with the buyer's authorised max budget, so
        # an echo here surfaced it straight to the seller.
        return LLMResult(
            text=f"[stub:{model}] no model provider configured",
            tokens_in=50, tokens_out=20, model=model, stub=True,
        )


def _stub_embedding(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic pseudo-embedding so semantic search 'works' offline."""
    import hashlib
    import math

    h = hashlib.sha256(text.encode()).digest()
    vals = [(b / 255.0) - 0.5 for b in h]
    vec = [vals[i % len(vals)] for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


client = AIClient()
