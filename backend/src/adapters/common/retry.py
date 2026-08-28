"""Retry helpers for adapter subprocess / network calls."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, TypeVar

from src.adapters.base.adapter_exception import AdapterError, AdapterTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    max_retries: int,
    backoff_seconds: float,
    tool_name: str,
    retry_on: tuple[type[BaseException], ...] = (AdapterError,),
) -> T:
    """
    Execute ``func`` with bounded retries and linear backoff.

    ``AdapterTimeoutError`` and ``AdapterPolicyViolationError`` are not
    retried unless included in ``retry_on``.
    """

    from src.adapters.base.adapter_exception import (
        AdapterPolicyViolationError,
        AdapterScopeViolationError,
    )

    non_retryable = (AdapterTimeoutError, AdapterPolicyViolationError, AdapterScopeViolationError)
    attempts = max_retries + 1
    last_error: Optional[BaseException] = None

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except non_retryable:
            raise
        except retry_on as exc:
            last_error = exc
            logger.warning(
                "Adapter call failed tool=%s attempt=%s/%s error=%s",
                tool_name,
                attempt,
                attempts,
                exc,
            )
            if attempt >= attempts:
                break
            if backoff_seconds > 0:
                time.sleep(backoff_seconds * attempt)

    assert last_error is not None
    raise last_error
