"""Unified logging control for flask-nacos and the underlying nacos-sdk-python.

This module centralizes all logging configuration for the extension. A single
set of ``NACOS_LOG_*`` settings controls both the ``flask_nacos`` logger and the
loggers used by ``nacos-sdk-python``. The library is intentionally low side
effect: it never calls :func:`logging.basicConfig`, never touches the root
logger, and never creates a file log unless ``NACOS_LOG_FILE`` is configured.

It also prevents ``nacos-sdk-python`` from creating its default log file at
``~/logs/nacos/nacos-client-python.log`` by making sure the SDK loggers already
have a handler (so the SDK's ``if not logger.hasHandlers()`` guard is skipped)
before the Nacos client is constructed, and by removing any default file handler
the SDK may have already installed.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

from .exceptions import NacosLoggingError

# The flask-nacos logger name.
FLASK_NACOS_LOGGER_NAME = "flask_nacos"

# Underlying nacos-sdk-python logger names that must be controlled. The 2.x
# synchronous client logs through ``nacos.client`` (``logging.getLogger(__name__)``);
# the others are included defensively for other SDK versions/layouts.
SDK_LOGGER_NAMES = ("nacos", "nacos.client", "nacos-sdk-python")

# The default file path that nacos-sdk-python writes to when left uncontrolled.
DEFAULT_SDK_LOG_PATH = os.path.abspath(
    os.path.expanduser(os.path.join("~", "logs", "nacos", "nacos-client-python.log"))
)
DEFAULT_SDK_LOG_DIR = os.path.dirname(DEFAULT_SDK_LOG_PATH)

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Internal logger used only for diagnostics emitted by this module itself.
_internal_logger = logging.getLogger(FLASK_NACOS_LOGGER_NAME)


def get_log_level(level_name: Any, fail_fast: bool = False) -> int:
    """Resolve a textual log level to its numeric value.

    Invalid levels raise :class:`NacosLoggingError` when ``fail_fast`` is true,
    otherwise a warning is logged and ``logging.INFO`` is returned.
    """
    name = str(level_name or "").strip().upper()
    if name in _VALID_LEVELS:
        return int(getattr(logging, name))
    message = (
        f"Invalid NACOS_LOG_LEVEL {level_name!r}; expected one of "
        f"{sorted(_VALID_LEVELS)}"
    )
    if fail_fast:
        raise NacosLoggingError(message)
    _internal_logger.warning("%s; falling back to INFO", message)
    return logging.INFO


def _make_formatter(fmt: Any, fail_fast: bool) -> logging.Formatter:
    """Build a formatter, validating the format string."""
    fmt_str = fmt if isinstance(fmt, str) and fmt else DEFAULT_LOG_FORMAT
    try:
        formatter = logging.Formatter(fmt_str)
        # Validate the format string eagerly so a bad format is caught at
        # configuration time rather than on the first log record.
        formatter.format(
            logging.LogRecord("flask_nacos", logging.INFO, __file__, 0, "check", None, None)
        )
        return formatter
    except Exception as exc:
        message = f"Invalid NACOS_LOG_FORMAT {fmt!r}: {exc}"
        if fail_fast:
            raise NacosLoggingError(message) from exc
        _internal_logger.warning("%s; falling back to default format", message)
        return logging.Formatter(DEFAULT_LOG_FORMAT)


def _is_owned(handler: logging.Handler) -> bool:
    return bool(getattr(handler, "_flask_nacos_handler", False))


def _handler_type(handler: logging.Handler) -> Optional[str]:
    return getattr(handler, "_flask_nacos_handler_type", None)


def _has_console_handler(logger: logging.Logger) -> bool:
    return any(_handler_type(h) == "console" for h in logger.handlers)


def _has_null_handler(logger: logging.Logger) -> bool:
    return any(_handler_type(h) == "null" for h in logger.handlers)


def _has_real_handler(logger: logging.Logger) -> bool:
    """True if the logger has any non-NullHandler handler attached."""
    return any(not isinstance(h, logging.NullHandler) for h in logger.handlers)


def ensure_null_handler(logger: logging.Logger) -> None:
    """Attach a flask-nacos owned NullHandler once.

    A NullHandler keeps ``logger.hasHandlers()`` true (blocking the SDK's
    default file handler) and suppresses the "No handlers could be found"
    warning without emitting anything.
    """
    if _has_null_handler(logger):
        return
    handler: logging.Handler = logging.NullHandler()
    handler._flask_nacos_handler = True  # type: ignore[attr-defined]
    handler._flask_nacos_handler_type = "null"  # type: ignore[attr-defined]
    logger.addHandler(handler)


def add_console_handler_once(
    logger: logging.Logger, formatter: logging.Formatter, level: int
) -> None:
    """Attach a single flask-nacos owned StreamHandler to ``logger``."""
    if _has_console_handler(logger):
        return
    handler: logging.Handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler._flask_nacos_handler = True  # type: ignore[attr-defined]
    handler._flask_nacos_handler_type = "console"  # type: ignore[attr-defined]
    logger.addHandler(handler)


def add_file_handler_once(
    logger: logging.Logger,
    log_file: str,
    formatter: logging.Formatter,
    level: int,
    max_bytes: Optional[int],
    backup_count: Optional[int],
    fail_fast: bool = False,
) -> bool:
    """Attach a single flask-nacos owned file handler for ``log_file``.

    Uses :class:`~logging.handlers.RotatingFileHandler` when ``max_bytes`` is a
    positive integer, otherwise a plain :class:`~logging.FileHandler`. The same
    resolved path is only added once. Returns ``True`` when a handler is present
    for the path after the call, ``False`` when creation failed and was degraded.
    """
    resolved = os.path.abspath(os.path.expanduser(str(log_file)))
    for handler in logger.handlers:
        if getattr(handler, "_flask_nacos_log_file", None) == resolved:
            return True

    try:
        directory = os.path.dirname(resolved)
        if directory:
            os.makedirs(directory, exist_ok=True)
        new_handler: logging.Handler
        if isinstance(max_bytes, int) and not isinstance(max_bytes, bool) and max_bytes > 0:
            new_handler = RotatingFileHandler(
                resolved,
                maxBytes=max_bytes,
                backupCount=int(backup_count) if backup_count else 0,
                encoding="utf-8",
            )
        else:
            new_handler = logging.FileHandler(resolved, encoding="utf-8")
    except Exception as exc:
        message = f"Failed to create log file handler for {resolved!r}: {exc}"
        if fail_fast:
            raise NacosLoggingError(message) from exc
        _internal_logger.warning("%s; file logging disabled", message)
        return False

    new_handler.setLevel(level)
    new_handler.setFormatter(formatter)
    new_handler._flask_nacos_handler = True  # type: ignore[attr-defined]
    new_handler._flask_nacos_handler_type = "file"  # type: ignore[attr-defined]
    new_handler._flask_nacos_log_file = resolved  # type: ignore[attr-defined]
    logger.addHandler(new_handler)
    return True


def _points_to_default_sdk_log(handler: logging.Handler) -> bool:
    base = getattr(handler, "baseFilename", None)
    if not base:
        return False
    resolved = os.path.abspath(base)
    return resolved == DEFAULT_SDK_LOG_PATH or resolved.startswith(
        DEFAULT_SDK_LOG_DIR + os.sep
    )


def remove_nacos_default_file_handlers(
    logger: logging.Logger, fail_fast: bool = False
) -> None:
    """Remove any handler on ``logger`` pointing at the SDK default log path.

    flask-nacos owned handlers are never removed here (they never point at the
    default path). User log files elsewhere are left untouched.
    """
    for handler in list(logger.handlers):
        if _is_owned(handler):
            continue
        if not _points_to_default_sdk_log(handler):
            continue
        try:
            logger.removeHandler(handler)
            handler.close()
        except Exception as exc:  # pragma: no cover - defensive
            message = (
                f"Failed to remove nacos-sdk-python default file handler: {exc}"
            )
            if fail_fast:
                raise NacosLoggingError(message) from exc
            _internal_logger.warning("%s", message)


def _remove_owned_handlers(logger: logging.Logger) -> None:
    """Remove flask-nacos owned console/file/null handlers from ``logger``."""
    for handler in list(logger.handlers):
        if not _is_owned(handler):
            continue
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - defensive
            pass


def _attach_flask_logger_handlers(logger: logging.Logger, app: Any) -> None:
    """Reuse the Flask ``app.logger`` handlers without mutating app.logger."""
    app_logger = getattr(app, "logger", None)
    attached = False
    if app_logger is not None:
        for handler in list(app_logger.handlers):
            if handler not in logger.handlers:
                logger.addHandler(handler)
            attached = True
    if not attached and not _has_real_handler(logger):
        ensure_null_handler(logger)


def configure_named_logger(
    logger: logging.Logger, settings: Dict[str, Any], app: Any = None
) -> None:
    """Apply the resolved logging ``settings`` to a single named logger."""
    # Always strip the SDK default file handler first so it can never win.
    remove_nacos_default_file_handlers(logger, settings["fail_fast"])

    if not settings["enabled"]:
        _remove_owned_handlers(logger)
        ensure_null_handler(logger)
        logger.propagate = False
        logger.disabled = True
        return

    logger.disabled = False
    logger.setLevel(settings["level"])
    logger.propagate = bool(settings["propagate"])

    if settings["use_flask_logger"]:
        _attach_flask_logger_handlers(logger, app)
        return

    added = False
    if settings["to_console"]:
        add_console_handler_once(logger, settings["formatter"], settings["level"])
        added = True
    if settings["file"]:
        if add_file_handler_once(
            logger,
            settings["file"],
            settings["formatter"],
            settings["level"],
            settings["max_bytes"],
            settings["backup_count"],
            settings["fail_fast"],
        ):
            added = True
    if not added:
        ensure_null_handler(logger)


def _managed_loggers() -> List[logging.Logger]:
    loggers = [logging.getLogger(FLASK_NACOS_LOGGER_NAME)]
    loggers.extend(logging.getLogger(name) for name in SDK_LOGGER_NAMES)
    return loggers


def _build_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    fail_fast = bool(cfg.get("NACOS_FAIL_FAST", False))
    return {
        "enabled": bool(cfg.get("NACOS_LOG_ENABLED", True)),
        "level": get_log_level(cfg.get("NACOS_LOG_LEVEL", "INFO"), fail_fast),
        "formatter": _make_formatter(cfg.get("NACOS_LOG_FORMAT"), fail_fast),
        "to_console": bool(cfg.get("NACOS_LOG_TO_CONSOLE", False)),
        "file": cfg.get("NACOS_LOG_FILE"),
        "propagate": bool(cfg.get("NACOS_LOG_PROPAGATE", True)),
        "use_flask_logger": bool(cfg.get("NACOS_LOG_USE_FLASK_LOGGER", False)),
        "max_bytes": cfg.get("NACOS_LOG_MAX_BYTES"),
        "backup_count": cfg.get("NACOS_LOG_BACKUP_COUNT", 5),
        "fail_fast": fail_fast,
    }


def configure_sdk_loggers(settings: Dict[str, Any], app: Any = None) -> None:
    """Apply the resolved ``settings`` to every underlying SDK logger."""
    for name in SDK_LOGGER_NAMES:
        configure_named_logger(logging.getLogger(name), settings, app)


def configure_logger(app: Any, cfg: Dict[str, Any]) -> None:
    """Configure flask-nacos and nacos-sdk-python logging from ``cfg``.

    This is the single entry point used by :class:`FlaskNacos`. It must run
    before the Nacos client is created so the SDK never installs its default
    file handler.
    """
    settings = _build_settings(cfg)
    configure_named_logger(logging.getLogger(FLASK_NACOS_LOGGER_NAME), settings, app)
    configure_sdk_loggers(settings, app)


def cleanup_sdk_default_handlers(cfg: Dict[str, Any]) -> None:
    """Failsafe: remove any SDK default file handler installed after init.

    Called again after the Nacos client is constructed in case a particular SDK
    version installed its default handler despite the pre-configuration guard.
    """
    fail_fast = bool(cfg.get("NACOS_FAIL_FAST", False))
    for name in SDK_LOGGER_NAMES:
        remove_nacos_default_file_handlers(logging.getLogger(name), fail_fast)


__all__ = [
    "FLASK_NACOS_LOGGER_NAME",
    "SDK_LOGGER_NAMES",
    "DEFAULT_SDK_LOG_PATH",
    "configure_logger",
    "configure_named_logger",
    "configure_sdk_loggers",
    "cleanup_sdk_default_handlers",
    "get_log_level",
    "remove_nacos_default_file_handlers",
    "add_console_handler_once",
    "add_file_handler_once",
    "ensure_null_handler",
]
