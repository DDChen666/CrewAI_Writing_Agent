"""Shared Gemini rate limiter utilities."""
from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Deque, Optional

GEMINI_RPM_LIMIT = 10
_RATE_LIMIT_WINDOW = 60.0


class _GeminiRateLimiter:
    """Simple FIFO window rate limiter enforcing a requests-per-minute quota."""

    def __init__(self, max_calls_per_minute: int) -> None:
        if max_calls_per_minute <= 0:
            raise ValueError("max_calls_per_minute must be positive")
        self._max_calls = max_calls_per_minute
        self._timestamps: Deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, timeout: Optional[float] = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            with self._lock:
                now = time.monotonic()
                self._evict_stale(now)
                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return

                wait_time = _RATE_LIMIT_WINDOW - (now - self._timestamps[0])

            if wait_time <= 0:
                # Loop to recalculate after eviction if necessary.
                continue

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for Gemini rate limiter slot")
                wait_time = min(wait_time, remaining)

            time.sleep(min(wait_time, _RATE_LIMIT_WINDOW / self._max_calls))

    def _evict_stale(self, now: float) -> None:
        cutoff = now - _RATE_LIMIT_WINDOW
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()


_global_limiter = _GeminiRateLimiter(GEMINI_RPM_LIMIT)
_patch_lock = threading.Lock()


def acquire_gemini_slot(timeout: Optional[float] = None) -> None:
    """Acquire a slot from the global Gemini rate limiter."""

    _global_limiter.acquire(timeout=timeout)


@contextmanager
def rate_limited_gemini_call(timeout: Optional[float] = None):
    """Context manager variant for wrapping Gemini requests."""

    acquire_gemini_slot(timeout=timeout)
    yield


def ensure_gemini_rate_limit() -> None:
    """Patch known Gemini client entry points with the shared limiter."""

    with _patch_lock:
        _patch_litellm()
        _patch_google_genai()


def _patch_litellm() -> None:
    try:
        import litellm  # type: ignore
    except ImportError:
        return

    if getattr(litellm, "_gemini_rate_limiter_wrapped", False):
        return

    original_completion = litellm.completion
    original_acompletion = getattr(litellm, "acompletion", None)

    def _should_limit(model_name: Optional[str]) -> bool:
        return bool(model_name and "gemini" in model_name.lower())

    def completion_wrapper(*args, **kwargs):
        model_name = _extract_model_name(args, kwargs)
        if _should_limit(model_name):
            acquire_gemini_slot()
        return original_completion(*args, **kwargs)

    async def acompletion_wrapper(*args, **kwargs):  # type: ignore[misc]
        model_name = _extract_model_name(args, kwargs)
        if _should_limit(model_name):
            acquire_gemini_slot()
        return await original_acompletion(*args, **kwargs)  # type: ignore[func-returns-value]

    litellm.completion = completion_wrapper  # type: ignore[assignment]
    if original_acompletion is not None:
        litellm.acompletion = acompletion_wrapper  # type: ignore[assignment]
    litellm._gemini_rate_limiter_wrapped = True  # type: ignore[attr-defined]


def _extract_model_name(args, kwargs) -> Optional[str]:
    if "model" in kwargs:
        return kwargs["model"]
    if args:
        first = args[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("model")  # type: ignore[no-any-return]
        if hasattr(first, "get"):
            try:
                return first.get("model")  # type: ignore[call-arg, no-any-return]
            except Exception:  # pragma: no cover - defensive
                pass
        if hasattr(first, "model"):
            try:
                return getattr(first, "model")  # type: ignore[no-any-return]
            except Exception:  # pragma: no cover - defensive
                pass
    return None


def _patch_google_genai() -> None:
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        return

    model_cls = getattr(genai, "GenerativeModel", None)
    if model_cls is None or getattr(model_cls, "_gemini_rate_limiter_wrapped", False):
        return

    original_generate_content = model_cls.generate_content

    def generate_content_wrapper(self, *args, **kwargs):
        acquire_gemini_slot()
        return original_generate_content(self, *args, **kwargs)

    model_cls.generate_content = generate_content_wrapper  # type: ignore[assignment]

    chat_cls = getattr(genai, "ChatSession", None)
    if chat_cls is not None and not getattr(chat_cls, "_gemini_rate_limiter_wrapped", False):
        original_send_message = chat_cls.send_message

        def send_message_wrapper(self, *args, **kwargs):
            acquire_gemini_slot()
            return original_send_message(self, *args, **kwargs)

        chat_cls.send_message = send_message_wrapper  # type: ignore[assignment]
        chat_cls._gemini_rate_limiter_wrapped = True  # type: ignore[attr-defined]

    model_cls._gemini_rate_limiter_wrapped = True  # type: ignore[attr-defined]
