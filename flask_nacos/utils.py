"""Utility helpers for flask-nacos."""

import logging
import socket
from typing import Any, Dict, Optional

from .exceptions import NacosValidationError

logger = logging.getLogger("flask_nacos")

_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "off", "n", "f", ""}

_SENSITIVE_KEYS = {
    "NACOS_PASSWORD",
    "NACOS_SECRET_KEY",
    "NACOS_ACCESS_KEY",
}


def get_local_ip(raise_on_failure: bool = False) -> Optional[str]:
    """Best-effort detection of the primary outbound IPv4 address of this host.

    Opens a UDP socket to a public address (no packets are actually sent) to let
    the OS pick the interface it would use for outbound traffic.

    Returns the detected IP string on success. On failure, logs an error and
    either returns ``None`` (default) or raises :class:`NacosValidationError`
    when ``raise_on_failure`` is ``True``.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = None
    finally:
        sock.close()

    if ip and ip != "0.0.0.0":
        logger.info("Auto-detected local IP: %s", ip)
        return ip

    logger.error("Failed to auto-detect local IP")
    if raise_on_failure:
        raise NacosValidationError("Failed to auto-detect local IP address")
    return None


def get_host_ip() -> str:
    """Backward-compatible alias of :func:`get_local_ip`.

    Falls back to ``127.0.0.1`` when detection fails to preserve the 0.1.0
    behavior of always returning a usable string.
    """
    return get_local_ip() or "127.0.0.1"


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


def to_float(value: Any, default: Optional[float] = 1.0) -> Optional[float]:
    """Coerce a config value into a float, returning ``default`` on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_bool(value: Any) -> bool:
    """Return ``True`` only when ``value`` is a genuine bool."""
    return isinstance(value, bool)


def validate_port(value: Any) -> int:
    """Validate that ``value`` is a legal TCP port (1-65535)."""
    if isinstance(value, bool):
        raise NacosValidationError("NACOS_SERVICE_PORT must be an integer, got bool")
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise NacosValidationError(
            f"NACOS_SERVICE_PORT must be an integer, got {value!r}"
        )
    if not (1 <= port <= 65535):
        raise NacosValidationError(
            f"NACOS_SERVICE_PORT must be in range 1-65535, got {port}"
        )
    return port


def validate_weight(value: Any) -> float:
    """Validate that ``value`` is a number greater than zero."""
    if isinstance(value, bool):
        raise NacosValidationError("NACOS_SERVICE_WEIGHT must be a number, got bool")
    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise NacosValidationError(
            f"NACOS_SERVICE_WEIGHT must be a number, got {value!r}"
        )
    if weight <= 0:
        raise NacosValidationError(
            f"NACOS_SERVICE_WEIGHT must be greater than 0, got {weight}"
        )
    return weight


def validate_metadata(metadata: Any) -> Dict[str, Any]:
    """Validate service metadata, ensuring it is a plain mapping."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    raise NacosValidationError(
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
    "get_local_ip",
    "get_host_ip",
    "to_bool",
    "to_int",
    "to_float",
    "is_bool",
    "validate_port",
    "validate_weight",
    "validate_metadata",
    "mask_sensitive",
]
