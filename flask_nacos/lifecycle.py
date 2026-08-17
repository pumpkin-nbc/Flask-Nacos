"""Small process helpers used by the PID-bound lifecycle runtime."""

import os


def current_pid() -> int:
    """Return the current process id (wrapped so tests can patch it)."""
    return os.getpid()


__all__ = ["current_pid"]
