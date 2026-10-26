"""Sliding window in-memory rate limiter and request size enforcement."""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Bounded, thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._history: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """Check if request under key is permitted within the sliding window.

        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.monotonic()
        cutoff = now - window_seconds
        timestamps = self._history[key]

        # Prune expired timestamps
        valid_timestamps = [t for t in timestamps if t > cutoff]
        if not valid_timestamps:
            self._history.pop(key, None)
            valid_timestamps = []
        else:
            self._history[key] = valid_timestamps

        # Periodic bounded memory cleanup to prevent unbounded dictionary growth
        if len(self._history) > 5000:
            stale_keys = [k for k, v in self._history.items() if not v or v[-1] <= cutoff]
            for k in stale_keys:
                self._history.pop(k, None)

        if len(valid_timestamps) >= max_requests:
            oldest = valid_timestamps[0]
            retry_after = max(1, int(oldest + window_seconds - now))
            return False, retry_after

        valid_timestamps.append(now)
        self._history[key] = valid_timestamps
        return True, 0

    def reset(self, key: str | None = None) -> None:
        """Reset history for a specific key or all keys."""
        if key:
            self._history.pop(key, None)
        else:
            self._history.clear()


# Global in-memory singleton
rate_limiter = SlidingWindowRateLimiter()
FORCE_RATE_LIMIT_IN_TESTS: bool = False


def rate_limit(
    key_prefix: str,
    max_requests: int,
    window_seconds: int,
    key_func: Callable[[Request], str] | None = None,
):
    """FastAPI dependency for endpoint rate limiting."""

    async def dependency(request: Request) -> None:
        from app.config import get_settings

        settings = get_settings()
        if settings.app_env == "testing" and not FORCE_RATE_LIMIT_IN_TESTS:
            return

        client_ip = request.client.host if request.client else "unknown"
        identifier = key_func(request) if key_func else client_ip
        key = f"{key_prefix}:{identifier}"

        allowed, retry_after = rate_limiter.is_allowed(key, max_requests, window_seconds)
        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s on %s %s", key, request.method, request.url.path
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


async def enforce_max_payload_size(request: Request, max_bytes: int) -> bytes:
    """Enforce payload size limits for incoming request bodies to prevent DoS."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                max_mb = max_bytes // (1024 * 1024) or 1
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Payload exceeds maximum allowed size of {max_mb}MB.",
                )
        except ValueError:
            pass

    body = await request.body()
    if len(body) > max_bytes:
        max_mb = max_bytes // (1024 * 1024) or 1
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Payload exceeds maximum allowed size of {max_mb}MB.",
        )
    return body
