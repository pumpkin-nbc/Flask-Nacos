"""Process-aware lifecycle helpers for registration and deregistration.

These small, side-effect-free helpers keep the extension methods thin and make
the multi-worker (Gunicorn/uWSGI) behavior easy to unit test.
"""

import os
from typing import Optional, Tuple


def current_pid() -> int:
    """Return the current process id (wrapped so tests can patch it)."""
    return os.getpid()


def should_skip_register(
    registered: bool,
    registered_pid: Optional[int],
    current: int,
    once_per_process: bool,
) -> bool:
    """Return ``True`` when registration should be skipped for this process.

    Skipping happens only when the instance is already registered, the
    once-per-process policy is enabled, and the recorded pid matches the current
    process. A changed pid (e.g. a forked worker) allows re-registration.
    """
    return bool(registered and once_per_process and registered_pid == current)


def should_skip_deregister(
    registered_pid: Optional[int], current: int
) -> Tuple[bool, str]:
    """Decide whether deregistration should be skipped due to a pid mismatch.

    Returns ``(skip, reason)``. Skipping only applies when a registration pid was
    recorded and differs from the current process, to avoid deregistering an
    instance owned by another process. A never-registered object
    (``registered_pid is None``) is not skipped here.
    """
    if registered_pid is not None and registered_pid != current:
        return True, (
            f"instance was registered in pid {registered_pid} but current pid is "
            f"{current}; skipping deregistration to avoid affecting another process"
        )
    return False, ""


__all__ = [
    "current_pid",
    "should_skip_register",
    "should_skip_deregister",
]
