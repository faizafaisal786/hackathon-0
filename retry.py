"""
Retry Utility — Exponential Backoff
=====================================
Decorator for retrying transient failures across all sender modules.

Usage:
    from retry import retry, TransientError, PermanentError

    @retry(max_attempts=3, backoff_base=2)
    def send_something():
        ...
        raise TransientError("timeout")   # Will retry
        raise PermanentError("bad input") # Will NOT retry
"""

import time
import functools


class TransientError(Exception):
    """Retryable error: timeout, rate limit, server error."""
    pass


class PermanentError(Exception):
    """Non-retryable error: bad input, auth failure, insufficient funds."""
    pass


def retry(max_attempts: int = 3, backoff_base: float = 2.0,
          retryable_exceptions: tuple = (TransientError, TimeoutError, ConnectionError)):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        backoff_base: Base for exponential wait (2 = waits 1s, 2s, 4s...)
        retryable_exceptions: Tuple of exception types to retry on

    Raises:
        The last exception if all attempts fail.
        PermanentError immediately (never retried).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except PermanentError:
                    raise  # Never retry permanent errors
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait = backoff_base ** attempt
                        print(f"  [Retry {attempt + 1}/{max_attempts}] {type(e).__name__}: {e}")
                        print(f"  Waiting {wait:.0f}s before retry...")
                        time.sleep(wait)
                    else:
                        print(f"  [Failed] All {max_attempts} attempts exhausted.")
            raise last_exception
        return wrapper
    return decorator


def classify_smtp_error(e: Exception) -> Exception:
    """Classify SMTP exceptions as transient or permanent."""
    import smtplib
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return PermanentError(f"Auth failed: {e}")
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        return PermanentError(f"Recipient refused: {e}")
    if isinstance(e, (TimeoutError, ConnectionError)):
        return TransientError(f"Connection issue: {e}")
    if isinstance(e, smtplib.SMTPException):
        return TransientError(f"SMTP error: {e}")
    return TransientError(f"Unknown: {e}")


def classify_twilio_error(e: Exception) -> Exception:
    """Classify Twilio exceptions as transient or permanent."""
    msg = str(e).lower()
    if "401" in msg or "authenticate" in msg:
        return PermanentError("Twilio auth failed")
    if "21211" in msg or "not a valid phone" in msg:
        return PermanentError(f"Invalid phone number: {e}")
    if "21608" in msg:
        return PermanentError("Recipient not opted in to sandbox")
    if "20003" in msg or "insufficient" in msg:
        return PermanentError("Insufficient funds")
    if "429" in msg or "rate limit" in msg:
        return TransientError("Rate limited")
    if "5" in str(e)[:1]:  # 5xx server errors
        return TransientError(f"Server error: {e}")
    return TransientError(f"Unknown: {e}")


def classify_http_error(status_code: int, body: str) -> Exception:
    """Classify HTTP response as transient or permanent."""
    if status_code == 401:
        return PermanentError("Unauthorized — check access token")
    if status_code == 403:
        return PermanentError("Forbidden — insufficient permissions")
    if status_code == 404:
        return PermanentError("API endpoint not found")
    if status_code == 422:
        return PermanentError(f"Invalid payload: {body[:200]}")
    if status_code == 429:
        return TransientError("Rate limited — try again later")
    if status_code >= 500:
        return TransientError(f"Server error ({status_code})")
    return PermanentError(f"HTTP {status_code}: {body[:200]}")
