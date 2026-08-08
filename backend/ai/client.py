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
import logging
import re
import time
from dataclasses import dataclass, field
from typing import NamedTuple

from backend.shared.settings import settings

_log = logging.getLogger("vitrine.ai.client")

# How long to reuse the admin-configured provider clients before re-reading the
# admin_configs row. Keeps LLM calls off the DB on the hot path while still
# picking up admin key rotations within a few seconds.
_CONFIG_TTL_S = 20.0

# Hard ceiling on a single provider call. Without this the SDK default (10 min)
# applies, so one hung upstream connection pins a request — and a worker — for
# the whole window instead of failing over to the next provider.
_REQUEST_TIMEOUT_S = 30.0

# Local inference is far slower than a hosted API, and the very first call also
# pays to load the weights into memory. 30s would time out a cold start on CPU
# and make a working setup look broken, so local calls get their own ceiling.
_LOCAL_REQUEST_TIMEOUT_S = 300.0


def _timeout_for(provider: str) -> float:
    return _LOCAL_REQUEST_TIMEOUT_S if provider in ("ollama",) else _REQUEST_TIMEOUT_S

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
    # Local Ollama daemon, spoken to over its OpenAI-compatible surface.
    "ollama": settings.OLLAMA_BASE_URL,
}

# Providers that cost nothing to call. Their token usage is still recorded for
# observability, but it must not draw down OPENAI_DAILY_LIMIT_USD — otherwise a
# few hundred free local calls silently trip the kill-switch and take the
# hosted providers down with them.
FREE_PROVIDERS = {"ollama"}

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
        # A local model is free. Without this branch it would be priced at the
        # gpt-4o-mini default (estimate_cost falls back for unknown names), so
        # running entirely on Ollama would still march the daily spend counter
        # toward its cap and eventually refuse to answer at all.
        if self.provider in FREE_PROVIDERS:
            return 0.0
        return estimate_cost(self.model, self.tokens_in, self.tokens_out)


# ---------------------------------------------------------------------------
# Failure reporting.
#
# A dead provider fails the SAME way on every single call: a key without credit
# stays without credit, a 403 stays a 403. Printing the full provider error blob
# per call drowned the real logs, so every notice below goes through one
# throttle — the first occurrence is logged in full, identical repeats drop to
# DEBUG, and one compact reminder is emitted every _NOTICE_EVERY occurrences or
# _NOTICE_AFTER_S seconds, whichever comes first. A failure the operator has not
# seen before hashes to a different key, so it is never suppressed.
# ---------------------------------------------------------------------------
_NOTICE_EVERY = 50
_NOTICE_AFTER_S = 900.0     # 15 minutes
_BRIEF_CHARS = 160
_MAX_TRACKED_NOTICES = 256

# Redact anything shaped like a credential before it can reach a log record.
# Provider error bodies do not normally echo the key back, but this is the one
# place every provider error passes through, so it is the one place worth it.
# The catch-all arm needs a digit as well as a letter: a random 32-char secret
# has one with near-certainty, while the long words-and-underscores identifiers
# providers put in error bodies (`generate_content_free_tier_requests`) do not,
# and redacting those would gut the diagnostic detail this is protecting.
_SECRET_RE = re.compile(
    r"(?:sk-|gsk_|xai-|AIza)[A-Za-z0-9_\-]{8,}"
    r"|(?=[A-Za-z0-9_\-]*[A-Za-z])(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{32,}"
)

# Provider errors arrive as a serialised JSON blob; the human-readable part is
# its `message` field. Lifting that out turns 150 characters of nested
# punctuation into one readable clause.
_MESSAGE_RE = re.compile(r"['\"]message['\"]\s*:\s*['\"](.+?)['\"]", re.S)


class _Failure(NamedTuple):
    """Identity of a failure *kind* — what makes two errors 'the same error'.

    Volatile tails (retry delays, request ids) fall outside the truncated brief,
    so one outage keeps one identity across calls, while a genuinely different
    error produces a new one and is therefore reported immediately.
    """
    provider: str
    kind: str
    status: object
    brief: str


def _scrub(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text)


def _error_brief(exc: BaseException) -> str:
    """One short, readable line. The raw blob belongs at DEBUG, not here."""
    text = _scrub(" ".join(str(exc).split()))
    if not text:
        return type(exc).__name__
    match = _MESSAGE_RE.search(text)
    # A message containing an apostrophe closes the non-greedy match early; a
    # suspiciously short capture means that happened, so keep the raw blob.
    if match and len(match.group(1).strip()) >= 16:
        status = getattr(exc, "status_code", None)
        text = (f"{status} " if status else "") + match.group(1).strip()
    if len(text) > _BRIEF_CHARS:
        text = text[:_BRIEF_CHARS].rstrip() + "..."
    return f"{type(exc).__name__}: {text}"


def _error_detail(exc: BaseException) -> str:
    """The whole provider payload, on one line. DEBUG only."""
    return _scrub(" ".join(str(exc).split())) or type(exc).__name__


def _failure_of(provider: str, exc: BaseException) -> _Failure:
    return _Failure(provider, type(exc).__name__,
                    getattr(exc, "status_code", None), _error_brief(exc))


def _ago(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f}m"
    return f"{seconds / 3600:.1f}h"


class _NoticeThrottle:
    """Answers 'have I already told the operator about this?'.

    observe() returns (verdict, repeats, elapsed):
      "new"     — never seen: log it in full.
      "summary" — seen `repeats` more times over `elapsed`: one compact line.
      "repeat"  — reported already and not due again: DEBUG only.
    """

    def __init__(self, every: int, after_s: float) -> None:
        self._every = every
        self._after_s = after_s
        self._seen: dict[tuple, list] = {}   # key -> [suppressed, last_notice_ts]

    def observe(self, key: tuple) -> tuple[str, int, float]:
        now = time.monotonic()
        state = self._seen.get(key)
        if state is None:
            if len(self._seen) >= _MAX_TRACKED_NOTICES:
                # Bounded: an error carrying a varying id would otherwise grow
                # this dict without limit. Insertion order == oldest first.
                del self._seen[next(iter(self._seen))]
            self._seen[key] = [0, now]
            return "new", 0, 0.0
        state[0] += 1
        if state[0] >= self._every or (now - state[1]) >= self._after_s:
            repeats, elapsed = state[0], now - state[1]
            state[0], state[1] = 0, now
            return "summary", repeats, elapsed
        return "repeat", state[0], now - state[1]


# One event loop, and observe() never awaits between its read and its write, so
# no lock is needed. State is per-process, which is what we want: each worker
# tells its own operator once.
_notices = _NoticeThrottle(_NOTICE_EVERY, _NOTICE_AFTER_S)


def _report_failures(failures: dict[_Failure, tuple]) -> None:
    """One line per provider per error kind — not one per candidate model."""
    for failure, (exc, models) in failures.items():
        verdict, repeats, elapsed = _notices.observe(failure)
        if verdict == "new":
            # dict.fromkeys: the candidate list can repeat a model (OPENAI_MODEL
            # defaults to one of its own fallbacks) — say each name once.
            _log.warning("[ai] provider %s unavailable (tried %s): %s",
                         failure.provider, ", ".join(dict.fromkeys(models)),
                         failure.brief)
            # A traceback adds nothing to an HTTP status error — the payload is
            # the diagnosis, and the frames are all SDK internals. For anything
            # else it IS the diagnosis: the broad `except Exception` around the
            # call catches timeouts and our own bugs too.
            _log.debug("[ai] provider %s full error: %s", failure.provider,
                       _error_detail(exc), exc_info=None if failure.status else exc)
        elif verdict == "summary":
            _log.warning("[ai] provider %s still unavailable: %d more failures in "
                         "the last %s (%s)", failure.provider, repeats,
                         _ago(elapsed), failure.brief)
        else:
            _log.debug("[ai] provider %s failed again (%d since last notice): %s",
                       failure.provider, repeats, _error_detail(exc))


def _report_fallback(provider: str, model: str, failures: dict[_Failure, tuple]) -> None:
    """A later provider answered. That is normal operation when the earlier keys
    are dead, so announce the route once and then keep quiet about it."""
    skipped = ", ".join(dict.fromkeys(f.provider for f in failures))
    verdict, repeats, elapsed = _notices.observe(("fallback", provider, model, skipped))
    if verdict == "new":
        _log.warning("[ai] now serving from %s/%s after %s failed; repeats of this "
                     "fallback are logged at DEBUG", provider, model, skipped)
    elif verdict == "summary":
        _log.warning("[ai] still serving from %s/%s (%s unavailable): %d more calls "
                     "in the last %s", provider, model, skipped, repeats, _ago(elapsed))
    else:
        _log.debug("[ai] fell back to %s/%s after %s failed", provider, model, skipped)


def _report_exhausted(failures: dict[_Failure, tuple], last_exc: Exception | None) -> None:
    providers = ", ".join(dict.fromkeys(f.provider for f in failures)) or "none"
    verdict, repeats, elapsed = _notices.observe(
        ("stub", providers, tuple(f.brief for f in failures))
    )
    if verdict == "new":
        _log.error("[ai] every provider failed (%s); serving stub output. Last error: %s",
                   providers, _error_brief(last_exc) if last_exc else "unknown")
    elif verdict == "summary":
        _log.error("[ai] still serving stub output (%s failing): %d more calls in the last %s",
                   providers, repeats, _ago(elapsed))
    else:
        _log.debug("[ai] all providers failed again (%d since last notice); serving stub",
                   repeats)


class AIClient:
    def __init__(self) -> None:
        self._clients: list = []             # admin-configured provider clients (cached)
        self._cached_hash: int | None = None
        self._configured_at: float = 0.0     # monotonic ts of last DB read
        self._ever_configured: bool = False
        self._env_clients: list | None = None  # env-key clients (built once)

    def _default(self) -> list[tuple]:
        """Env-key clients in fallback order: OpenAI, then Gemini, then Ollama.

        Built once and reused. Returns [] when nothing at all is configured,
        which is what drives the offline stub path.

        Ollama is deliberately last. A hosted key, when it works, is faster and
        better than a small local model, so local inference is the safety net
        rather than the default — it answers when the keys are missing, out of
        credit, or refused.
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
            if settings.OLLAMA_ENABLED:
                # Ollama ignores the key but the SDK requires a non-empty one.
                built.append((AsyncOpenAI(api_key="ollama",
                                          base_url=settings.OLLAMA_BASE_URL,
                                          timeout=_LOCAL_REQUEST_TIMEOUT_S), "ollama"))
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
        except Exception as exc:
            # Keep last-known clients rather than dropping to none on a transient
            # error. Throttled: this path retries every _CONFIG_TTL_S, so a
            # persistent DB fault would otherwise repeat forever.
            verdict, repeats, elapsed = _notices.observe(_failure_of("admin-config", exc))
            if verdict == "new":
                _log.warning("[ai] could not read admin provider config, keeping the "
                             "last known clients: %s", _error_brief(exc))
                _log.debug("[ai] admin provider config read failed", exc_info=True)
            elif verdict == "summary":
                _log.warning("[ai] admin provider config still unreadable: %d more "
                             "attempts in the last %s (%s)", repeats, _ago(elapsed),
                             _error_brief(exc))
            else:
                _log.debug("[ai] admin provider config read failed again (%d since "
                           "last notice): %s", repeats, _error_detail(exc))
        self._ever_configured = True
        self._configured_at = time.monotonic()
        return self._clients

    async def chat(self, messages: list[dict], *, tools: list | None = None,
                   model: str | None = None, json_mode: bool = False) -> LLMResult:

        clients = await self._resolved_clients()

        if not clients:
            return self._stub(model or settings.OPENAI_MODEL)

        last_exc: Exception | None = None
        # Failures seen during THIS call, grouped by error kind so a provider
        # that fails identically across five candidate models is reported as one
        # line, not five. Logging bookkeeping only — it does not steer fallback.
        failures: dict[_Failure, tuple] = {}

        for client, provider in clients:
            # Map standard OpenAI models to provider-specific models if needed
            candidates = self._get_provider_models(provider, model)

            for candidate in candidates:
                kwargs: dict = {"model": candidate, "messages": messages, "tools": tools or None}
                if json_mode and not tools:
                    # Gemini's and Ollama's OpenAI-compat endpoints both honour
                    # json_object too.
                    if provider in ("openai", "grok", "gemini", "ollama"):
                        kwargs["response_format"] = {"type": "json_object"}
                try:
                    async with _call_slot:
                        resp = await asyncio.wait_for(
                            client.chat.completions.create(**kwargs),
                            timeout=_timeout_for(provider),
                        )
                    choice = resp.choices[0].message
                    usage = resp.usage
                    if last_exc is not None:
                        _report_failures(failures)
                        _report_fallback(provider, candidate, failures)
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
                    failures.setdefault(_failure_of(provider, exc), (exc, []))[1].append(candidate)
                    continue # Try next model or next provider

        # Every provider/model failed. Degrade to the offline stub instead of
        # 500-ing the caller: agents already know how to handle stub output, and
        # a transient upstream outage should not take the whole app down.
        _report_failures(failures)
        _report_exhausted(failures, last_exc)
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
        elif provider == "ollama":
            # Exactly one tag: whatever is actually pulled locally. Guessing
            # alternatives here would just produce 404s from the daemon.
            return [settings.OLLAMA_MODEL]
        return [requested or settings.OPENAI_MODEL]

    async def embed(self, text: str, *, model: str | None = None) -> list[float]:
        clients = await self._resolved_clients()

        # Stored vectors are 1536-dim and cosine similarity zips the two lists,
        # so a provider returning a different width would silently score
        # garbage. Pin every provider to EMBED_DIM and drop any reply that
        # isn't that width.
        for client, provider in clients:
            if provider not in ("openai", "gemini", "ollama"):
                continue
            if provider == "openai":
                embed_model = model or settings.OPENAI_EMBED_MODEL
                kwargs = {"model": embed_model, "input": text, "dimensions": EMBED_DIM}
            elif provider == "gemini":
                embed_model = settings.GEMINI_EMBED_MODEL
                kwargs = {"model": embed_model, "input": text, "dimensions": EMBED_DIM}
            else:
                # Local embedding models have a fixed native width (768 for
                # nomic-embed-text, 1024 for mxbai-embed-large) and no
                # `dimensions` knob, so the request must not ask for one.
                embed_model = settings.OLLAMA_EMBED_MODEL
                kwargs = {"model": embed_model, "input": text}
            try:
                async with _call_slot:
                    resp = await asyncio.wait_for(
                        client.embeddings.create(**kwargs), timeout=_timeout_for(provider)
                    )
                vec = resp.data[0].embedding
                if len(vec) == EMBED_DIM:
                    return vec
                if provider == "ollama" and len(vec) < EMBED_DIM:
                    # Right-pad with zeros to reach the stored width. Cosine
                    # similarity is *exactly* preserved by this: the zeros add
                    # nothing to either dot product or magnitude. What it does
                    # NOT survive is mixing widths in one store — a padded
                    # local vector and a native OpenAI vector describe
                    # different spaces, so switching embedding provider means
                    # re-embedding the catalogue, not just the query.
                    return list(vec) + [0.0] * (EMBED_DIM - len(vec))
                continue
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
