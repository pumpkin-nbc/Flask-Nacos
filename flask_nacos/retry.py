"""Unified retry helper for Nacos operations."""

import logging
import time
from typing import Any, Callable, Dict

from .exceptions import NacosValidationError
from .utils import validate_retry_interval, validate_retry_times

logger = logging.getLogger("flask_nacos")


def _sleep(seconds: float) -> None:
    """Indirection around :func:`time.sleep` so tests can patch it cheaply."""
    if seconds and seconds > 0:
        time.sleep(seconds)


def run_with_retry(
    operation: Callable[[], Any],
    operation_name: str,
    config: Dict[str, Any],
) -> Any:
    """Run ``operation`` with optional retries controlled by config.

    Behavior:

    - When ``NACOS_RETRY_ENABLED`` is ``False`` the operation runs exactly once.
    - When enabled, the operation is attempted at most ``NACOS_RETRY_TIMES``
      times, sleeping ``NACOS_RETRY_INTERVAL`` seconds between attempts.
    - Each failed attempt is logged at ``warning`` level.
    - After exhausting attempts the last exception is re-raised; fail-fast
      handling is left to the caller.
    """
    enabled = config.get("NACOS_RETRY_ENABLED", True)
    if not enabled:
        return operation()

    max_attempts = validate_retry_times(config.get("NACOS_RETRY_TIMES", 3))
    interval = validate_retry_interval(config.get("NACOS_RETRY_INTERVAL", 1.0))

    if max_attempts > 1:
        logger.debug(
            "Starting %s with retry (max_attempts=%d, interval=%.3fs)",
            operation_name,
            max_attempts,
            interval,
        )

    last_exc: BaseException = RuntimeError(
        f"{operation_name} did not run"
    )  # pragma: no cover - defensive default
    for attempt in range(1, max_attempts + 1):
        try:
            result = operation()
        except NacosValidationError:
            # Invalid input is deterministic. Retrying would only add latency
            # and duplicate log noise without changing the outcome.
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "%s attempt %d/%d failed: %s",
                operation_name,
                attempt,
                max_attempts,
                exc,
            )
            if attempt < max_attempts:
                _sleep(interval)
            continue
        else:
            if attempt > 1:
                logger.info("%s succeeded after %d attempts", operation_name, attempt)
            return result

    logger.error("%s failed after %d attempts", operation_name, max_attempts)
    raise last_exc


__all__ = ["run_with_retry"]
