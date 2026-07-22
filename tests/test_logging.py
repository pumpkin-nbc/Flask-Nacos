"""Tests for unified NACOS_LOG_* logging control (1.0.2).

These tests verify that flask-nacos configures both its own logger and the
underlying nacos-sdk-python loggers without side effects: no default file, no
``logging.basicConfig()``, no root-logger mutation, and no duplicate handlers.
"""

import logging
from io import StringIO
from logging.handlers import RotatingFileHandler

import pytest
from flask import Flask

import flask_nacos.logging as nlog
from flask_nacos import FlaskNacos
from flask_nacos import config as nconfig
from flask_nacos.exceptions import NacosLoggingError

MANAGED_NAMES = (nlog.FLASK_NACOS_LOGGER_NAME, *nlog.SDK_LOGGER_NAMES)


@pytest.fixture(autouse=True)
def _reset_managed_loggers():
    """Snapshot and restore all managed loggers around each test."""
    root = logging.getLogger()
    snapshot = {}
    for name in MANAGED_NAMES:
        lg = logging.getLogger(name)
        snapshot[name] = (list(lg.handlers), lg.level, lg.propagate, lg.disabled)
    root_snapshot = (list(root.handlers), root.level)

    # Start each test from a clean slate for the managed loggers.
    for name in MANAGED_NAMES:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.setLevel(logging.NOTSET)
        lg.propagate = True
        lg.disabled = False

    yield

    for name, (handlers, level, propagate, disabled) in snapshot.items():
        lg = logging.getLogger(name)
        lg.handlers[:] = handlers
        lg.setLevel(level)
        lg.propagate = propagate
        lg.disabled = disabled
    root.handlers[:] = root_snapshot[0]
    root.setLevel(root_snapshot[1])


def _cfg(**overrides):
    app = Flask(__name__)
    app.config.update(overrides)
    return app, nconfig.load_config(app)


def _flask_logger():
    return logging.getLogger(nlog.FLASK_NACOS_LOGGER_NAME)


def _console_handlers(logger):
    return [
        h
        for h in logger.handlers
        if getattr(h, "_flask_nacos_handler_type", None) == "console"
    ]


def _file_handlers(logger):
    return [
        h
        for h in logger.handlers
        if getattr(h, "_flask_nacos_handler_type", None) == "file"
    ]


# 1-6: default behavior ------------------------------------------------------

def test_default_does_not_create_sdk_default_log_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert not (tmp_path / "logs" / "nacos" / "nacos-client-python.log").exists()


def test_default_does_not_create_logs_nacos_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert not (tmp_path / "logs" / "nacos").exists()


def test_default_creates_no_file_handler():
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        assert _file_handlers(logging.getLogger(name)) == []


def test_default_does_not_call_basic_config():
    root = logging.getLogger()
    before = list(root.handlers)
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert root.handlers == before


def test_default_does_not_modify_root_logger():
    root = logging.getLogger()
    root.addHandler(logging.NullHandler())
    marker = list(root.handlers)
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert root.handlers == marker


def test_default_uses_named_flask_nacos_logger():
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    logger = _flask_logger()
    assert logger.name == "flask_nacos"
    # Only a NullHandler is attached by default (blocks the SDK file quietly).
    assert logger.hasHandlers()
    assert not any(
        not isinstance(h, logging.NullHandler) for h in logger.handlers
    )


# 7: disabled ----------------------------------------------------------------

def test_disabled_silences_flask_nacos_and_sdk_loggers():
    app, cfg = _cfg(NACOS_LOG_ENABLED=False)
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        lg = logging.getLogger(name)
        assert lg.disabled is True
        assert lg.propagate is False
        # No console/file handler, but still has a NullHandler.
        assert _console_handlers(lg) == []
        assert _file_handlers(lg) == []
        assert lg.hasHandlers()


# 8: level -------------------------------------------------------------------

def test_debug_level_applies_to_flask_nacos_and_sdk_loggers():
    app, cfg = _cfg(NACOS_LOG_LEVEL="DEBUG")
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        assert logging.getLogger(name).level == logging.DEBUG


# 9-10: invalid level with fail-fast rules -----------------------------------

def test_invalid_level_without_fail_fast_falls_back_to_info():
    app, cfg = _cfg(NACOS_LOG_LEVEL="BOGUS", NACOS_FAIL_FAST=False)
    nlog.configure_logger(app, cfg)
    assert logging.getLogger("flask_nacos").level == logging.INFO


def test_invalid_level_with_fail_fast_raises():
    app, cfg = _cfg(NACOS_LOG_LEVEL="BOGUS", NACOS_FAIL_FAST=True)
    with pytest.raises(NacosLoggingError):
        nlog.configure_logger(app, cfg)


def test_get_log_level_helper():
    assert nlog.get_log_level("debug") == logging.DEBUG
    assert nlog.get_log_level(None) == logging.INFO
    with pytest.raises(NacosLoggingError):
        nlog.get_log_level("nope", fail_fast=True)


# 11-12: console handler + dedup ---------------------------------------------

def test_console_enabled_adds_stream_handler():
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True)
    nlog.configure_logger(app, cfg)
    logger = _flask_logger()
    consoles = _console_handlers(logger)
    assert len(consoles) == 1
    assert isinstance(consoles[0], logging.StreamHandler)


def test_repeated_configuration_does_not_duplicate_console_handler():
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True)
    nlog.configure_logger(app, cfg)
    nlog.configure_logger(app, cfg)
    assert len(_console_handlers(_flask_logger())) == 1


def test_repeated_init_app_does_not_duplicate_handlers(monkeypatch):
    from flask_nacos import extension as extension_module

    monkeypatch.setattr(
        extension_module, "create_client", lambda cfg: object()
    )
    app = Flask(__name__)
    app.config.update(
        NACOS_ENABLED=True,
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_SERVER_ADDR="127.0.0.1:8848",
        NACOS_LOG_TO_CONSOLE=True,
    )
    nacos = FlaskNacos()
    nacos.init_app(app)
    nacos.init_app(app)
    assert len(_console_handlers(_flask_logger())) == 1


# 13-15: file handler --------------------------------------------------------

def test_file_not_configured_creates_no_file(tmp_path):
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert list(tmp_path.iterdir()) == []
    assert _file_handlers(_flask_logger()) == []


def test_file_configured_adds_file_handler(tmp_path):
    log_file = tmp_path / "sub" / "flask-nacos.log"
    app, cfg = _cfg(NACOS_LOG_FILE=str(log_file))
    nlog.configure_logger(app, cfg)
    files = _file_handlers(_flask_logger())
    assert len(files) == 1
    assert log_file.exists()


def test_file_configured_blocks_sdk_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    log_file = tmp_path / "flask-nacos.log"
    app, cfg = _cfg(NACOS_LOG_FILE=str(log_file))
    nlog.configure_logger(app, cfg)
    for name in nlog.SDK_LOGGER_NAMES:
        assert logging.getLogger(name).hasHandlers()
    assert not (tmp_path / "logs" / "nacos" / "nacos-client-python.log").exists()


# 17: rotating file ----------------------------------------------------------

def test_max_bytes_uses_rotating_file_handler(tmp_path):
    log_file = tmp_path / "rot.log"
    app, cfg = _cfg(
        NACOS_LOG_FILE=str(log_file),
        NACOS_LOG_MAX_BYTES=1024,
        NACOS_LOG_BACKUP_COUNT=3,
    )
    nlog.configure_logger(app, cfg)
    files = _file_handlers(_flask_logger())
    assert len(files) == 1
    assert isinstance(files[0], RotatingFileHandler)


def test_no_max_bytes_uses_plain_file_handler(tmp_path):
    log_file = tmp_path / "plain.log"
    app, cfg = _cfg(NACOS_LOG_FILE=str(log_file))
    nlog.configure_logger(app, cfg)
    handler = _file_handlers(_flask_logger())[0]
    assert isinstance(handler, logging.FileHandler)
    assert not isinstance(handler, RotatingFileHandler)


# 18: file handler dedup -----------------------------------------------------

def test_repeated_configuration_does_not_duplicate_file_handler(tmp_path):
    log_file = tmp_path / "dedup.log"
    app, cfg = _cfg(NACOS_LOG_FILE=str(log_file))
    nlog.configure_logger(app, cfg)
    nlog.configure_logger(app, cfg)
    assert len(_file_handlers(_flask_logger())) == 1


# 19-20: propagation ---------------------------------------------------------

def test_propagate_false_applies_to_all_managed_loggers():
    app, cfg = _cfg(NACOS_LOG_PROPAGATE=False)
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        assert logging.getLogger(name).propagate is False


def test_propagate_true_applies_to_all_managed_loggers():
    app, cfg = _cfg(NACOS_LOG_PROPAGATE=True)
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        assert logging.getLogger(name).propagate is True


# 21: use flask app.logger ---------------------------------------------------

def test_use_flask_logger_adds_no_new_handler():
    app = Flask(__name__)
    app_handler = logging.StreamHandler(StringIO())
    app.logger.addHandler(app_handler)
    app_handlers_before = list(app.logger.handlers)

    cfg = nconfig.load_config(app)
    cfg["NACOS_LOG_USE_FLASK_LOGGER"] = True
    nlog.configure_logger(app, cfg)

    logger = _flask_logger()
    # No flask-nacos owned console/file handler was created.
    assert _console_handlers(logger) == []
    assert _file_handlers(logger) == []
    # The app.logger handler is reused by reference and app.logger is untouched.
    assert app_handler in logger.handlers
    assert app.logger.handlers == app_handlers_before


# 22: remove SDK default file handler ----------------------------------------

def test_sdk_default_file_handler_is_removed(tmp_path, monkeypatch):
    default_path = tmp_path / "logs" / "nacos" / "nacos-client-python.log"
    default_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(nlog, "DEFAULT_SDK_LOG_PATH", str(default_path))
    monkeypatch.setattr(nlog, "DEFAULT_SDK_LOG_DIR", str(default_path.parent))

    sdk_logger = logging.getLogger("nacos.client")
    rogue = logging.FileHandler(str(default_path), encoding="utf-8")
    sdk_logger.addHandler(rogue)
    assert rogue in sdk_logger.handlers

    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    assert rogue not in sdk_logger.handlers


# 23-24: do not touch app.logger / root handlers -----------------------------

def test_does_not_modify_flask_app_logger_handlers():
    app = Flask(__name__)
    app.logger.addHandler(logging.StreamHandler(StringIO()))
    before = list(app.logger.handlers)
    cfg = nconfig.load_config(app)
    nlog.configure_logger(app, cfg)
    assert app.logger.handlers == before


def test_does_not_modify_root_logger_handlers():
    root = logging.getLogger()
    sentinel = logging.StreamHandler(StringIO())
    root.addHandler(sentinel)
    before = list(root.handlers)
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True, NACOS_LOG_FILE=None)
    nlog.configure_logger(app, cfg)
    assert root.handlers == before


# 25: no secrets in logs -----------------------------------------------------

def test_logs_do_not_contain_secrets(monkeypatch):
    from flask_nacos import extension as extension_module

    buffer = StringIO()
    pre = logging.StreamHandler(buffer)
    pre._flask_nacos_handler = True
    pre._flask_nacos_handler_type = "console"
    _flask_logger().addHandler(pre)

    monkeypatch.setattr(
        extension_module, "create_client", lambda cfg: object()
    )
    app = Flask(__name__)
    app.config.update(
        NACOS_ENABLED=True,
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_SERVER_ADDR="127.0.0.1:8848",
        NACOS_USERNAME="admin",
        NACOS_PASSWORD="supersecret-password",
        NACOS_LOG_LEVEL="DEBUG",
        NACOS_LOG_TO_CONSOLE=True,
    )
    FlaskNacos(app)
    output = buffer.getvalue()
    assert "supersecret-password" not in output


# 26: never create a log file at an unexpected path --------------------------

def test_no_file_created_outside_configured_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True)
    nlog.configure_logger(app, cfg)
    # Only console logging requested: nothing on disk anywhere under HOME.
    assert list(tmp_path.rglob("*.log")) == []


# get_config() still returns raw content (regression guard) ------------------

def test_get_config_still_returns_raw_string(monkeypatch):
    from flask_nacos import extension as extension_module

    class _FakeClient:
        def get_config(self, data_id, group, **kwargs):
            return "raw-content-string"

    monkeypatch.setattr(
        extension_module, "create_client", lambda cfg: _FakeClient()
    )
    app = Flask(__name__)
    app.config.update(
        NACOS_ENABLED=True,
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_SERVER_ADDR="127.0.0.1:8848",
    )
    nacos = FlaskNacos(app)
    with app.app_context():
        result = nacos.get_config("some-data-id")
    assert result == "raw-content-string"
