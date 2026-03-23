"""
retry_handler.py — Exponential Backoff Retry Decorator
=======================================================
Wraps any function with configurable retry logic.
Distinguishes between transient errors (retry) and fatal errors (raise immediately).

Usage:
    from error_recovery.retry_handler import with_retry, TransientError

    @with_retry(max_attempts=3, base_delay=1, max_delay=60)
    def call_gmail_api():
        ...
"""

import time
import logging
from functools import wraps
from typing import Type

logger = logging.getLogger("RetryHandler")


# ─── Custom Exceptions ────────────────────────────────────────────────────────

class TransientError(Exception):
    """Temporary error that should be retried (network timeout, rate limit, etc.)"""


class AuthenticationError(Exception):
    """Auth failure — do NOT retry, alert human immediately."""


class FatalError(Exception):
    """Unrecoverable error — stop immediately."""


# ─── Retry Decorator ─────────────────────────────────────────────────────────

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (TransientError, ConnectionError, TimeoutError),
    on_retry=None,
):
    """
    Decorator that retries a function on transient failures with exponential backoff.

    Args:
        max_attempts: Total attempts (including the first).
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Maximum delay cap in seconds.
        retryable_exceptions: Exception types that trigger a retry.
        on_retry: Optional callback(attempt, exception, delay) called before each retry.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except AuthenticationError:
                    # Never retry auth errors
                    raise
                except FatalError:
                    # Never retry fatal errors
                    raise
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e, delay)

                    time.sleep(delay)

            raise last_exception  # Should not reach here

        return wrapper
    return decorator


# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Simple token-bucket rate limiter.
    Prevents the AI from making too many external calls per hour.
    """

    def __init__(self, max_calls: int, period_seconds: int = 3600):
        self.max_calls = max_calls
        self.period = period_seconds
        self.calls: list[float] = []

    def is_allowed(self) -> bool:
        now = time.time()
        # Remove calls older than the period
        self.calls = [t for t in self.calls if now - t < self.period]
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False

    def wait_if_needed(self):
        """Block until a call is allowed."""
        while not self.is_allowed():
            oldest = min(self.calls)
            wait_time = self.period - (time.time() - oldest) + 0.1
            logger.info(f"Rate limit reached. Waiting {wait_time:.0f}s...")
            time.sleep(min(wait_time, 60))


# ─── Shared Rate Limiters ─────────────────────────────────────────────────────

RATE_LIMITS = {
    "email_send": RateLimiter(max_calls=10, period_seconds=3600),
    "payment": RateLimiter(max_calls=3, period_seconds=3600),
    "social_post": RateLimiter(max_calls=5, period_seconds=3600),
    "claude_invoke": RateLimiter(max_calls=20, period_seconds=3600),
}
