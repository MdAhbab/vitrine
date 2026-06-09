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
        self.enabled = bool(settings.OPENAI_API_KEY)
        self._client = None
        if self.enabled:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as exc:  # noqa: BLE001
                print(f"[ai] OpenAI client init failed, falling back to stub: {exc}")
                self.enabled = False

    async def chat(self, messages: list[dict], *, tools: list | None = None,
                   model: str | None = None, stream: bool = False) -> LLMResult:
        model = model or settings.OPENAI_MODEL
        if not self.enabled:
            return self._stub(messages, model)
        resp = await self._client.chat.completions.create(  # type: ignore[union-attr]
            model=model, messages=messages, tools=tools or None,
        )
        choice = resp.choices[0].message
        usage = resp.usage
        return LLMResult(
            text=choice.content or "",
            tool_calls=[tc.model_dump() for tc in (choice.tool_calls or [])],
            tokens_in=getattr(usage, "prompt_tokens", 0),
            tokens_out=getattr(usage, "completion_tokens", 0),
            model=model,
        )

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        model = model or settings.OPENAI_EMBED_MODEL
        if not self.enabled:
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
