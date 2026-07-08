"""Utility helpers for flask-nacos."""

import socket
from typing import Any, Dict, Optional

_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f", ""}

_SENSITIVE_KEYS = {
    "NACOS_PASSWORD",
    "NACOS_SECRET_KEY",
    "NACOS_ACCESS_KEY",
}


def get_host_ip() -> str:
    """Best-effort detection of the primary outbound IPv4 address of this host.

    Opens a UDP socket to a public address (no packets are actually sent) to let
    the OS pick the interface it would use for outbound traffic. Falls back to
    ``127.0.0.1`` if detection fails.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def to_bool(value: Any, default: bool = False) -> bool:
    """Coerce an arbitrary config value into a boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce a config value into an int, returning ``default`` on failure."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 1.0) -> float:
    """Coerce a config value into a float, returning ``default`` on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def validate_metadata(metadata: Any) -> Dict[str, Any]:
    """Validate service metadata, ensuring it is a plain mapping."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    raise TypeError(
        f"NACOS_SERVICE_METADATA must be a dict, got {type(metadata).__name__!r}"
    )


def mask_sensitive(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``config`` with sensitive values masked for logging."""
    masked: Dict[str, Any] = {}
    for key, value in config.items():
        if key in _SENSITIVE_KEYS and value:
            masked[key] = "***"
        else:
            masked[key] = value
    return masked


__all__ = [
    "get_host_ip",
    "to_bool",
    "to_int",
    "to_float",
    "validate_metadata",
    "mask_sensitive",
]
