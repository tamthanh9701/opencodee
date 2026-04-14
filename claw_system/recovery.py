import asyncio
from typing import Callable, Awaitable, TypeVar

import structlog

from shared.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")

DEFAULT_MAX_RETRIES = settings.max_retries
DEFAULT_BASE_DELAY = settings.retry_base_delay
DEFAULT_BACKOFF_FACTOR = settings.retry_backoff_factor


class MaxRetriesExceeded(Exception):
    def __init__(self, attempts: int, last_error: Exception) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Max retries exceeded ({attempts} attempts). Last error: {last_error}"
        )


async def retry(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    **kwargs,
) -> T:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("retry_attempt", attempt=attempt, max_retries=max_retries)
            result = await fn(*args, **kwargs)
            logger.info("retry_success", attempt=attempt)
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** (attempt - 1))
                logger.warning(
                    "retry_failed_waiting",
                    attempt=attempt,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "retry_exhausted",
                    attempts=attempt,
                    error=str(e),
                )

    raise MaxRetriesExceeded(max_retries, last_error)