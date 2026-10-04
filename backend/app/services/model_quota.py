"""Free-tier model quotas + a reservation tracker (Google AI Studio).

The Google free tier is the scarcest resource in the pipeline. Limits are
per-model, per-minute (RPM), per-minute-tokens (TPM) and per-day (RPD) —
see ``app/services/models.py`` for the table and ``.env``-independent
source of truth in ``QUOTAS`` below.

Why this exists: a 5,000-word article is ~6.7K input tokens, which is ~40%
of Gemma's entire 16K TPM budget for a *single* call. Without accounting,
a two-platform run silently 429s mid-pipeline. So every generation call
reserves tokens against the model's windows *before* it is sent.

The mitigation that matters most is upstream: long content is reduced by a
decision model (Clef, Neuron-billed, 64K context) before it ever reaches a
Google model, so the TPM budget is spent on the compressed brief, not the
raw article.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict, deque

log = logging.getLogger(__name__)

# Google AI Studio free tier, per model. rpm = requests/min, tpm = tokens/min,
# rpd = requests/day. Zero/absent entries are unusable.
QUOTAS: dict[str, dict[str, int]] = {
    "gemma-4-31b-it": {"rpm": 30, "tpm": 16_000, "rpd": 14_400},
    "gemma-4-26b-a4b-it": {"rpm": 30, "tpm": 16_000, "rpd": 14_400},
    "gemini-3.1-flash-lite": {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemini-3.5-flash-lite": {"rpm": 15, "tpm": 250_000, "rpd": 500},
    "gemini-2.5-flash": {"rpm": 5, "tpm": 250_000, "rpd": 20},
}

# Requests/minute we will actually issue against a model. Deliberately below
# the published limit so bursty parallel format branches cannot cross it.
SAFE_RPM = {"gemma-4-31b-it": 20, "gemma-4-26b-a4b-it": 20,
            "gemini-3.1-flash-lite": 12, "gemini-3.5-flash-lite": 12,
            "gemini-2.5-flash": 4}

# Headroom on the token budget: prompts + completion routinely overshoot the
# raw estimate, so reserve this fraction of the remaining TPM.
TPM_HEADROOM = 1.25

_MINUTE = 60.0
_DAY = 86_400.0


class _ModelWindow:
    """Sliding-window token/request accounting for one model."""

    def __init__(self) -> None:
        # RLock, not Lock: seconds_until_fit() calls fits() → usage() while
        # already holding the lock, which deadlocks a non-reentrant one.
        self._lock = threading.RLock()
        self._minute: deque[tuple[float, int]] = deque()
        self._day: deque[tuple[float, int]] = deque()
        self._day_requests: deque[float] = deque()

    def _prune(self, now: float) -> None:
        while self._minute and now - self._minute[0][0] > _MINUTE:
            self._minute.popleft()
        while self._day and now - self._day[0][0] > _DAY:
            self._day.popleft()
        while self._day_requests and now - self._day_requests[0] > _DAY:
            self._day_requests.popleft()

    def usage(self) -> dict[str, int]:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return {
                "rpm": len(self._minute),
                "tpm": sum(t for _, t in self._minute),
                "rpd": len(self._day_requests),
            }

    def fits(self, est_tokens: int, rpm_cap: int, tpm_cap: int, rpd_cap: int) -> bool:
        u = self.usage()
        return (
            u["rpm"] + 1 <= rpm_cap
            and u["tpm"] + est_tokens <= tpm_cap
            and u["rpd"] + 1 <= rpd_cap
        )

    def commit(self, tokens: int) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            self._minute.append((now, tokens))
            self._day.append((now, tokens))
            self._day_requests.append(now)

    def seconds_until_fit(
        self, est_tokens: int, rpm_cap: int, tpm_cap: int, rpd_cap: int
    ) -> float:
        """How long until the next call would fit (0.0 if it already does)."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            if self.fits(est_tokens, rpm_cap, tpm_cap, rpd_cap):
                return 0.0
            # RPM window: wait for the oldest request in this minute to expire.
            wait = 0.0
            if len(self._minute) + 1 > rpm_cap:
                wait = max(wait, _MINUTE - (now - self._minute[0][0]) + 0.05)
            # TPM window: wait until enough tokens age out of the minute.
            if sum(t for _, t in self._minute) + est_tokens > tpm_cap:
                for ts, _tok in self._minute:
                    aged = sum(t for t_, t in self._minute if t_ >= ts)
                    if aged + est_tokens <= tpm_cap:
                        wait = max(wait, _MINUTE - (now - ts) + 0.05)
                        break
            # Daily window: only the model cap can help here.
            if len(self._day_requests) + 1 > rpd_cap:
                wait = max(wait, _DAY - (now - self._day_requests[0]) + 0.5)
            return max(wait, 0.05)


_windows: dict[str, _ModelWindow] = defaultdict(_ModelWindow)


def window(model: str) -> _ModelWindow:
    return _windows[model]


def limits(model: str) -> dict[str, int]:
    return QUOTAS.get(model, {"rpm": 0, "tpm": 0, "rpd": 0})


def caps(model: str) -> tuple[int, int, int]:
    lim = limits(model)
    return (
        SAFE_RPM.get(model, max(1, lim["rpm"])),
        int(lim["tpm"] / TPM_HEADROOM) if lim["tpm"] else 0,
        lim["rpd"],
    )


def usage(model: str) -> dict[str, int]:
    return window(model).usage()


def fits(model: str, est_tokens: int) -> bool:
    """Whether a call of ``est_tokens`` fits in this model's budget now."""
    rpm_cap, tpm_cap, rpd_cap = caps(model)
    if not rpm_cap or not rpd_cap:
        return False
    return window(model).fits(est_tokens, rpm_cap, tpm_cap, rpd_cap)


def commit(model: str, tokens: int) -> None:
    if model in QUOTAS:
        window(model).commit(tokens)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) — only used for budgeting."""
    if not text:
        return 0
    return max(1, len(text) // 4)


async def reserve(
    model: str,
    tokens: int,
    max_wait: float = 60.0,
) -> bool:
    """Reserve budget for ``tokens`` on ``model``, waiting if necessary.

    Returns False when the model is unusable or the wait budget is exceeded —
    the caller should then use the next candidate rather than block a
    pipeline for minutes. Commits immediately on success so parallel branches
    cannot both claim the same headroom.
    """
    rpm_cap, tpm_cap, rpd_cap = caps(model)
    if not rpm_cap or not rpd_cap:
        return False
    est = max(1, int(tokens))
    win = window(model)
    waited = 0.0
    while True:
        if win.fits(est, rpm_cap, tpm_cap, rpd_cap):
            win.commit(est)
            return True
        delay = win.seconds_until_fit(est, rpm_cap, tpm_cap, rpd_cap)
        if waited + delay > max_wait:
            log.info(
                "[quota] %s cannot fit %d tokens within %.0fs (usage=%s caps=%s)",
                model, est, max_wait, win.usage(), (rpm_cap, tpm_cap, rpd_cap),
            )
            return False
        log.debug("[quota] %s throttling %.1fs (usage=%s)", model, delay, win.usage())
        await asyncio.sleep(delay)
        waited += delay


def pick_model(
    candidates: list[str],
    tokens: int,
    *,
    require_json: bool = False,
) -> str | None:
    """First candidate whose budget fits ``tokens`` right now.

    ``require_json`` skips models that cannot be relied on to emit a bare
    JSON object (Gemma echoes the prompt instead). Candidate order encodes
    preference: pass the best-quality model first.
    """
    # Models known to not honor "return ONLY valid JSON" reliably.
    json_unreliable = {"gemma-4-31b-it", "gemma-4-26b-a4b-it"}
    for model in candidates:
        if require_json and model in json_unreliable:
            continue
        if fits(model, tokens):
            return model
    return None


def snapshot() -> dict[str, dict]:
    """Per-model usage + limits, for the Studio/health surface."""
    out: dict[str, dict] = {}
    for model in QUOTAS:
        u = usage(model)
        rpm_cap, tpm_cap, rpd_cap = caps(model)
        out[model] = {
            "rpm": f"{u['rpm']}/{rpm_cap}",
            "tpm": f"{u['tpm']}/{tpm_cap}",
            "rpd": f"{u['rpd']}/{rpd_cap}",
        }
    return out
