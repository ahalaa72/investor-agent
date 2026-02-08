"""
HTTP clients, retry logic, and async/sync utilities.
"""
import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, after_log
from yfinance.exceptions import YFRateLimitError

from .config import DEFAULT_FUTURE_TIMEOUT

logger = logging.getLogger(__name__)


def api_retry(func):
    """Unified retry decorator for API calls (yfinance and HTTP)."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2.0, min=2.0, max=30.0),
        retry=retry_if_exception(lambda e:
            isinstance(e, YFRateLimitError) or
            (hasattr(e, 'status_code') and getattr(e, 'status_code', 0) >= 500) or
            any(term in str(e).lower() for term in [
                "rate limit", "too many requests", "temporarily blocked",
                "timeout", "connection", "network", "temporary", "5", "429", "502", "503", "504"
            ])
        ),
        after=after_log(logger, logging.WARNING)
    )(func)


def safe_future_result(future, timeout: float = DEFAULT_FUTURE_TIMEOUT, default=None, context: str = ""):
    """
    Safely get result from a future with timeout and exception handling.

    Prevents server crashes from hanging API calls by catching timeouts
    and exceptions, logging them, and returning a default value.
    """
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError:
        logger.error(f"Timeout after {timeout}s: {context}")
        return default
    except Exception as e:
        logger.error(f"Exception in {context}: {type(e).__name__}: {e}")
        return default


def create_async_client(headers: dict | None = None) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with longer timeout, automatic redirect and custom headers."""
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers=headers,
    )


@api_retry
async def fetch_json(url: str, headers: dict | None = None) -> dict:
    """Generic JSON fetcher with retry logic."""
    async with create_async_client(headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


@api_retry
def fetch_json_sync(url: str, headers: dict | None = None) -> dict:
    """Synchronous JSON fetcher with retry logic."""
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


@api_retry
async def fetch_text(url: str, headers: dict | None = None) -> str:
    """Generic text fetcher with retry logic."""
    async with create_async_client(headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
