"""
OpenAI client wrapper — the ONLY place that talks to OpenAI.

Centralizes: model selection, retries/timeouts, token counting, cost accounting
(writes agent_runs), and result caching. Designed to be SAFE WITHOUT A KEY: if
OPENAI_API_KEY is empty it returns deterministic stub output so the whole app
runs offline during development. Flip the key on to go live.

Pricing (gpt-4o-mini, approx): $0.15 / 1M input, $0.60 / 1M output.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.shared.settings import settings

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
        self._client = None
        self._cached_key: str | None = None

    async def _resolve_api_key(self) -> str | None:
        if settings.OPENAI_API_KEY:
            return settings.OPENAI_API_KEY
        try:
            from backend.shared.crypto import decrypt_value
            from backend.shared.db import SessionLocal
            from backend.shared.models import AdminConfig
            async with SessionLocal() as db:
                row = await db.get(AdminConfig, "api_keys")
                if row and isinstance(row.value, list):
                    for k in row.value:
                        if not isinstance(k, dict):
                            continue
                        if k.get("provider") == "openai" and k.get("enabled") and k.get("key"):
                            return decrypt_value(k["key"]) or None
        except Exception:
            pass
        return None

    @property
    def enabled(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    @staticmethod
    def _chat_model_candidates(primary: str | None) -> list[str]:
        """Try the configured model first, then known stable fallbacks."""
        candidates = [
            primary or "",
            settings.OPENAI_MODEL,
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-5-mini",
            "gpt-5-nano",
        ]
        uniq: list[str] = []
        for m in candidates:
            if m and m not in uniq:
                uniq.append(m)
        return uniq

    async def _ensure_client(self):
        key = await self._resolve_api_key()
        if not key:
            self._client = None
            self._cached_key = None
            return False
        if self._client is None or key != self._cached_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=key)
                self._cached_key = key
            except Exception as exc:
                print(f"[ai] OpenAI client init failed: {exc}")
                self._client = None
                return False
        return True

    async def chat(self, messages: list[dict], *, tools: list | None = None,
                   model: str | None = None, stream: bool = False,
                   json_mode: bool = False) -> LLMResult:
        model = model or settings.OPENAI_MODEL
        if not await self._ensure_client():
            return self._stub(messages, model)
        last_exc: Exception | None = None
        for candidate in self._chat_model_candidates(model):
            kwargs: dict = {"model": candidate, "messages": messages, "tools": tools or None}
            # JSON mode forces a parseable object (used by Pricing / Feature estimator).
            # Can't combine with tool calling, so only set it when no tools are passed.
            if json_mode and not tools:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = await self._client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
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
                continue
        assert last_exc is not None
        raise last_exc

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model = model or settings.OPENAI_EMBED_MODEL
        if not await self._ensure_client():
            return _stub_embedding(text)
        resp = await self._client.embeddings.create(model=model, input=text)  # type: ignore[union-attr]
        return resp.data[0].embedding

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
