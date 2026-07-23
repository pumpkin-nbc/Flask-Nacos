"""Safe logging configuration for Flask-Nacos and nacos-sdk-python.

``NACOS_LOG_*`` settings configure only records emitted by Flask-Nacos.  The
classic synchronous Nacos SDK is deliberately isolated because supported 2.x
versions may log access tokens, authentication request data, and configuration
content.  SDK records are therefore never forwarded to application handlers.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import NacosLoggingError

FLASK_NACOS_LOGGER_NAME = "flask_nacos"
SDK_LOGGER_NAMES = ("nacos", "nacos.client", "nacos-sdk-python")

DEFAULT_SDK_LOG_PATH = os.path.abspath(
    os.path.expanduser(os.path.join("~", "logs", "nacos", "nacos-client-python.log"))
)
DEFAULT_SDK_LOG_DIR = os.path.dirname(DEFAULT_SDK_LOG_PATH)
FLASK_NACOS_LOG_FILENAME = "flask_nacos.log"
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_CONFIG_LOCK = RLock()
_internal_logger = logging.getLogger(FLASK_NACOS_LOGGER_NAME)
_borrowed_handlers: List[logging.Handler] = []


def _warn_or_raise(message: str, fail_fast: bool) -> None:
    if fail_fast:
        raise NacosLoggingError(message)
    _internal_logger.warning("%s; using a safe fallback", message)


def get_log_level(level_name: Any, fail_fast: bool = False) -> int:
    """Resolve a textual Flask-Nacos log level."""
    name = str(level_name or "").strip().upper()
    if name in _VALID_LEVELS:
        return int(getattr(logging, name))
    _warn_or_raise(
        f"Invalid NACOS_LOG_LEVEL {level_name!r}; expected one of "
        f"{sorted(_VALID_LEVELS)}",
        fail_fast,
    )
    return logging.INFO


def _make_formatter(fmt: Any, fail_fast: bool) -> logging.Formatter:
    if not isinstance(fmt, str) or not fmt:
        _warn_or_raise("NACOS_LOG_FORMAT must be a non-empty string", fail_fast)
        fmt = DEFAULT_LOG_FORMAT
    try:
        formatter = logging.Formatter(fmt)
        formatter.format(
            logging.LogRecord("flask_nacos", logging.INFO, __file__, 0, "check", None, None)
        )
        return formatter
    except Exception as exc:
        if fail_fast:
            raise NacosLoggingError(f"Invalid NACOS_LOG_FORMAT {fmt!r}: {exc}") from exc
        _internal_logger.warning(
            "Invalid NACOS_LOG_FORMAT %r; using the default format", fmt
        )
        return logging.Formatter(DEFAULT_LOG_FORMAT)


def _optional_non_negative_int(
    value: Any, key: str, default: Optional[int], fail_fast: bool
) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        _warn_or_raise(f"{key} must be a non-negative integer or None", fail_fast)
        return default
    if isinstance(value, float) and not value.is_integer():
        _warn_or_raise(f"{key} must be a non-negative integer or None", fail_fast)
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        _warn_or_raise(f"{key} must be a non-negative integer or None", fail_fast)
        return default
    if parsed < 0:
        _warn_or_raise(f"{key} must be greater than or equal to 0", fail_fast)
        return default
    return parsed


def _normalize_log_file(
    directory: Any, filename: Any, fail_fast: bool
) -> Optional[str]:
    if directory is None:
        return None
    if not isinstance(directory, str) or not directory.strip():
        _warn_or_raise(
            "NACOS_LOG_DIR must be a non-empty directory path or None",
            fail_fast,
        )
        return None
    if (
        not isinstance(filename, str)
        or not filename.strip()
        or filename.strip() in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or os.path.basename(filename.strip()) != filename.strip()
    ):
        _warn_or_raise(
            "NACOS_LOG_FILENAME must be a non-empty filename without a path",
            fail_fast,
        )
        return None
    log_directory = os.path.abspath(os.path.expanduser(directory.strip()))
    if os.path.exists(log_directory) and not os.path.isdir(log_directory):
        _warn_or_raise(
            "NACOS_LOG_DIR must point to a directory, but an existing file "
            f"was found at {log_directory!r}",
            fail_fast,
        )
        return None
    return os.path.join(log_directory, filename.strip())


def _build_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    fail_fast = bool(cfg.get("NACOS_FAIL_FAST", False))
    enabled = bool(cfg.get("NACOS_LOG_ENABLED", False))
    if not enabled:
        return {
            "enabled": False,
            "level": logging.INFO,
            "formatter": logging.Formatter(DEFAULT_LOG_FORMAT),
            "to_console": False,
            "file": None,
            "propagate": False,
            "use_flask_logger": False,
            "max_bytes": None,
            "backup_count": 0,
            "fail_fast": fail_fast,
        }
    max_bytes = _optional_non_negative_int(
        cfg.get("NACOS_LOG_MAX_BYTES"), "NACOS_LOG_MAX_BYTES", None, fail_fast
    )
    backup_count = _optional_non_negative_int(
        cfg.get("NACOS_LOG_BACKUP_COUNT", 5),
        "NACOS_LOG_BACKUP_COUNT",
        5,
        fail_fast,
    )
    return {
        "enabled": True,
        "level": get_log_level(cfg.get("NACOS_LOG_LEVEL", "INFO"), fail_fast),
        "formatter": _make_formatter(cfg.get("NACOS_LOG_FORMAT"), fail_fast),
        "to_console": bool(cfg.get("NACOS_LOG_TO_CONSOLE", False)),
        "file": _normalize_log_file(
            cfg.get("NACOS_LOG_DIR", "./logs"),
            cfg.get("NACOS_LOG_FILENAME", FLASK_NACOS_LOG_FILENAME),
            fail_fast,
        ),
        "propagate": bool(cfg.get("NACOS_LOG_PROPAGATE", True)),
        "use_flask_logger": bool(cfg.get("NACOS_LOG_USE_FLASK_LOGGER", False)),
        "max_bytes": max_bytes,
        "backup_count": backup_count,
        "fail_fast": fail_fast,
    }


def validate_logging_config(cfg: Dict[str, Any]) -> None:
    """Validate logging settings before constructing the SDK client."""
    _build_settings(cfg)


def _is_owned(handler: logging.Handler) -> bool:
    return bool(getattr(handler, "_flask_nacos_handler", False))


def _handler_type(handler: logging.Handler) -> Optional[str]:
    return getattr(handler, "_flask_nacos_handler_type", None)


def _mark_owned(handler: logging.Handler, kind: str) -> logging.Handler:
    handler._flask_nacos_handler = True  # type: ignore[attr-defined]
    handler._flask_nacos_handler_type = kind  # type: ignore[attr-defined]
    return handler


def ensure_null_handler(logger: logging.Logger) -> None:
    """Attach one Flask-Nacos-owned ``NullHandler``."""
    if any(_handler_type(handler) == "null" for handler in logger.handlers):
        return
    logger.addHandler(_mark_owned(logging.NullHandler(), "null"))


def add_console_handler_once(
    logger: logging.Logger, formatter: logging.Formatter, level: int
) -> None:
    """Attach or update one owned console handler."""
    for handler in logger.handlers:
        if _handler_type(handler) == "console":
            handler.setLevel(level)
            handler.setFormatter(formatter)
            return
    handler = _mark_owned(logging.StreamHandler(), "console")
    handler.setLevel(level)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _create_file_handler(
    log_file: str,
    formatter: logging.Formatter,
    level: int,
    max_bytes: Optional[int],
    backup_count: Optional[int],
) -> logging.Handler:
    directory = os.path.dirname(log_file)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if max_bytes is not None and max_bytes > 0:
        handler: logging.Handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count or 0,
            encoding="utf-8",
        )
    else:
        handler = logging.FileHandler(log_file, encoding="utf-8")
    _mark_owned(handler, "file")
    handler._flask_nacos_log_file = log_file  # type: ignore[attr-defined]
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def add_file_handler_once(
    logger: logging.Logger,
    log_file: str,
    formatter: logging.Formatter,
    level: int,
    max_bytes: Optional[int],
    backup_count: Optional[int],
    fail_fast: bool = False,
) -> bool:
    """Attach or update one owned file handler for ``log_file``."""
    resolved = os.path.abspath(os.path.expanduser(str(log_file)))
    for handler in logger.handlers:
        if getattr(handler, "_flask_nacos_log_file", None) == resolved:
            handler.setLevel(level)
            handler.setFormatter(formatter)
            return True
    try:
        logger.addHandler(
            _create_file_handler(
                resolved, formatter, level, max_bytes, backup_count
            )
        )
    except Exception as exc:
        if fail_fast:
            raise NacosLoggingError(
                f"Failed to create log file handler for {resolved!r}: {exc}"
            ) from exc
        _internal_logger.warning(
            "Failed to create log file handler for %r; file logging disabled",
            resolved,
        )
        return False
    return True


def _points_to_default_sdk_log(handler: logging.Handler) -> bool:
    base = getattr(handler, "baseFilename", None)
    return bool(base and os.path.abspath(base) == DEFAULT_SDK_LOG_PATH)


def remove_nacos_default_file_handlers(
    logger: logging.Logger, fail_fast: bool = False
) -> None:
    """Remove only the SDK's exact default log handler."""
    for handler in list(logger.handlers):
        if _is_owned(handler) or not _points_to_default_sdk_log(handler):
            continue
        try:
            logger.removeHandler(handler)
            handler.close()
        except Exception as exc:  # pragma: no cover - defensive
            if fail_fast:
                raise NacosLoggingError(
                    "Failed to remove nacos-sdk-python default file handler"
                ) from exc


def _remove_owned_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if not _is_owned(handler):
            continue
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - defensive
            pass


def _detach_borrowed_handlers(logger: logging.Logger) -> None:
    global _borrowed_handlers
    for handler in _borrowed_handlers:
        if handler in logger.handlers:
            logger.removeHandler(handler)
    _borrowed_handlers = []


def _desired_handlers(
    settings: Dict[str, Any], app: Any
) -> Tuple[List[logging.Handler], List[logging.Handler]]:
    owned: List[logging.Handler] = []
    borrowed: List[logging.Handler] = []
    if not settings["enabled"]:
        return [_mark_owned(logging.NullHandler(), "null")], borrowed
    if settings["use_flask_logger"]:
        app_logger = getattr(app, "logger", None)
        if app_logger is not None:
            borrowed = list(app_logger.handlers)
        if not borrowed:
            owned.append(_mark_owned(logging.NullHandler(), "null"))
        return owned, borrowed
    if settings["to_console"]:
        handler = _mark_owned(logging.StreamHandler(), "console")
        handler.setLevel(settings["level"])
        handler.setFormatter(settings["formatter"])
        owned.append(handler)
    if settings["file"]:
        try:
            owned.append(
                _create_file_handler(
                    settings["file"],
                    settings["formatter"],
                    settings["level"],
                    settings["max_bytes"],
                    settings["backup_count"],
                )
            )
        except Exception as exc:
            if settings["fail_fast"]:
                for handler in owned:
                    handler.close()
                raise NacosLoggingError(
                    f"Failed to create log file handler for {settings['file']!r}: {exc}"
                ) from exc
            _internal_logger.warning(
                "Failed to create log file handler for %r; file logging disabled",
                settings["file"],
            )
    if not owned:
        owned.append(_mark_owned(logging.NullHandler(), "null"))
    return owned, borrowed


def configure_named_logger(
    logger: logging.Logger, settings: Dict[str, Any], app: Any = None
) -> None:
    """Atomically reconcile one logger to the requested Flask-Nacos state."""
    global _borrowed_handlers
    with _CONFIG_LOCK:
        owned, borrowed = _desired_handlers(settings, app)
        if logger.name == FLASK_NACOS_LOGGER_NAME:
            _detach_borrowed_handlers(logger)
        _remove_owned_handlers(logger)
        for handler in owned + borrowed:
            if handler not in logger.handlers:
                logger.addHandler(handler)
        if logger.name == FLASK_NACOS_LOGGER_NAME:
            _borrowed_handlers = borrowed
        logger.setLevel(settings["level"])
        logger.propagate = bool(settings["propagate"]) if settings["enabled"] else False
        logger.disabled = not settings["enabled"]


def configure_sdk_loggers(_settings: Optional[Dict[str, Any]] = None, app: Any = None) -> None:
    """Silence raw SDK loggers and block the SDK's default file handler."""
    del app
    with _CONFIG_LOCK:
        for name in SDK_LOGGER_NAMES:
            sdk_logger = logging.getLogger(name)
            # SDK records can contain tokens, signatures, request payloads and
            # configuration bodies. Detach every existing destination before
            # installing our sink; unowned handlers are not closed because
            # their lifecycle belongs to the application that created them.
            for handler in list(sdk_logger.handlers):
                sdk_logger.removeHandler(handler)
                if _is_owned(handler) or _points_to_default_sdk_log(handler):
                    try:
                        handler.close()
                    except Exception:  # pragma: no cover - defensive
                        pass
            ensure_null_handler(sdk_logger)
            sdk_logger.setLevel(logging.CRITICAL + 1)
            sdk_logger.propagate = False
            sdk_logger.disabled = True


def configure_logger(app: Any, cfg: Dict[str, Any]) -> None:
    """Configure safe Flask-Nacos logs and isolate raw SDK logs."""
    settings = _build_settings(cfg)
    configure_named_logger(logging.getLogger(FLASK_NACOS_LOGGER_NAME), settings, app)
    configure_sdk_loggers()


def cleanup_sdk_default_handlers(cfg: Dict[str, Any]) -> None:
    """Re-assert SDK isolation after client construction."""
    del cfg
    configure_sdk_loggers()


__all__ = [
    "FLASK_NACOS_LOGGER_NAME",
    "SDK_LOGGER_NAMES",
    "DEFAULT_SDK_LOG_PATH",
    "FLASK_NACOS_LOG_FILENAME",
    "configure_logger",
    "configure_named_logger",
    "configure_sdk_loggers",
    "cleanup_sdk_default_handlers",
    "validate_logging_config",
    "get_log_level",
    "remove_nacos_default_file_handlers",
    "add_console_handler_once",
    "add_file_handler_once",
    "ensure_null_handler",
]
