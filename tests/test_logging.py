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
def _reset_managed_loggers(tmp_path, monkeypatch):
    """Snapshot and restore all managed loggers around each test."""
    monkeypatch.chdir(tmp_path)
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
    app.config["NACOS_LOG_ENABLED"] = True
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


def test_disabled_default_creates_no_file_handler():
    app, cfg = _cfg(NACOS_LOG_ENABLED=False)
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


def test_disabled_default_uses_named_flask_nacos_logger():
    app, cfg = _cfg(NACOS_LOG_ENABLED=False)
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


def test_disabled_ignores_configured_path_and_filename(tmp_path):
    log_directory = tmp_path / "must-not-exist"
    app, cfg = _cfg(
        NACOS_LOG_ENABLED=False,
        NACOS_LOG_DIR=str(log_directory),
        NACOS_LOG_FILENAME="nested/invalid.log",
        NACOS_FAIL_FAST=True,
    )

    nlog.configure_logger(app, cfg)

    assert not log_directory.exists()
    assert _file_handlers(_flask_logger()) == []


# 8: level -------------------------------------------------------------------

def test_debug_level_applies_only_to_flask_nacos_logger():
    app, cfg = _cfg(NACOS_LOG_LEVEL="DEBUG")
    nlog.configure_logger(app, cfg)
    assert _flask_logger().level == logging.DEBUG
    for name in nlog.SDK_LOGGER_NAMES:
        sdk_logger = logging.getLogger(name)
        assert sdk_logger.level > logging.CRITICAL
        assert sdk_logger.disabled is True


# 9-10: invalid level with fail-fast rules -----------------------------------

def test_invalid_level_without_fail_fast_falls_back_to_info():
    app, cfg = _cfg(NACOS_LOG_LEVEL="BOGUS", NACOS_FAIL_FAST=False)
    nlog.configure_logger(app, cfg)
    assert logging.getLogger("flask_nacos").level == logging.INFO


def test_invalid_level_with_fail_fast_raises():
    app, cfg = _cfg(NACOS_LOG_LEVEL="BOGUS", NACOS_FAIL_FAST=True)
    with pytest.raises(NacosLoggingError):
        nlog.configure_logger(app, cfg)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("NACOS_LOG_DIR", ""),
        ("NACOS_LOG_DIR", 123),
        ("NACOS_LOG_FILENAME", ""),
        ("NACOS_LOG_FILENAME", "nested/flask_nacos.log"),
        ("NACOS_LOG_FILENAME", "nested\\flask_nacos.log"),
        ("NACOS_LOG_MAX_BYTES", True),
        ("NACOS_LOG_MAX_BYTES", -1),
        ("NACOS_LOG_MAX_BYTES", 1.5),
        ("NACOS_LOG_BACKUP_COUNT", True),
        ("NACOS_LOG_BACKUP_COUNT", -1),
        ("NACOS_LOG_BACKUP_COUNT", float("inf")),
    ],
)
def test_invalid_log_file_and_rotation_settings_fail_fast(key, value):
    app, cfg = _cfg(NACOS_FAIL_FAST=True, **{key: value})

    with pytest.raises(NacosLoggingError):
        nlog.validate_logging_config(cfg)


def test_valid_string_rotation_settings_are_coerced(tmp_path):
    log_directory = tmp_path / "rotating"
    app, cfg = _cfg(
        NACOS_LOG_DIR=str(log_directory),
        NACOS_LOG_MAX_BYTES="1024",
        NACOS_LOG_BACKUP_COUNT="2",
        NACOS_FAIL_FAST=True,
    )

    nlog.configure_logger(app, cfg)

    handler = _file_handlers(_flask_logger())[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == 1024
    assert handler.backupCount == 2


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


def test_last_configuration_atomically_removes_console_handler():
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True)
    nlog.configure_logger(app, cfg)
    assert len(_console_handlers(_flask_logger())) == 1

    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=False)
    nlog.configure_logger(app, cfg)
    assert _console_handlers(_flask_logger()) == []


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
        NACOS_LOG_ENABLED=True,
        NACOS_LOG_TO_CONSOLE=True,
        NACOS_LOG_DIR=None,
    )
    nacos = FlaskNacos()
    nacos.init_app(app)
    nacos.init_app(app)
    assert len(_console_handlers(_flask_logger())) == 1


# 13-15: file handler --------------------------------------------------------

def test_enabled_without_directory_uses_default_path(tmp_path):
    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)
    expected = tmp_path / "logs" / "flask_nacos.log"
    assert expected.exists()
    assert len(_file_handlers(_flask_logger())) == 1


def test_file_configured_adds_file_handler(tmp_path):
    log_directory = tmp_path / "sub"
    app, cfg = _cfg(
        NACOS_LOG_DIR=str(log_directory), NACOS_LOG_FILENAME="custom.log"
    )
    nlog.configure_logger(app, cfg)
    files = _file_handlers(_flask_logger())
    assert len(files) == 1
    assert (log_directory / "custom.log").exists()
    assert log_directory.is_dir()


def test_existing_file_cannot_be_used_as_log_directory(tmp_path):
    legacy_file = tmp_path / "logs"
    legacy_file.write_text("legacy log content", encoding="utf-8")
    app, cfg = _cfg(NACOS_LOG_DIR=str(legacy_file), NACOS_FAIL_FAST=True)

    with pytest.raises(NacosLoggingError, match="must point to a directory"):
        nlog.validate_logging_config(cfg)

    assert legacy_file.read_text(encoding="utf-8") == "legacy log content"


def test_file_configured_blocks_sdk_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    log_directory = tmp_path / "flask-nacos"
    app, cfg = _cfg(NACOS_LOG_DIR=str(log_directory))
    nlog.configure_logger(app, cfg)
    for name in nlog.SDK_LOGGER_NAMES:
        assert logging.getLogger(name).hasHandlers()
    assert not (tmp_path / "logs" / "nacos" / "nacos-client-python.log").exists()


def test_non_fail_fast_file_failure_keeps_requested_console_logging(monkeypatch):
    def fail_file_handler(*args, **kwargs):
        raise OSError("read-only destination")

    monkeypatch.setattr(nlog, "_create_file_handler", fail_file_handler)
    app, cfg = _cfg(
        NACOS_LOG_TO_CONSOLE=True,
        NACOS_LOG_DIR="unwritable",
        NACOS_FAIL_FAST=False,
    )

    nlog.configure_logger(app, cfg)

    assert len(_console_handlers(_flask_logger())) == 1
    assert _file_handlers(_flask_logger()) == []


# 17: rotating file ----------------------------------------------------------

def test_max_bytes_uses_rotating_file_handler(tmp_path):
    log_directory = tmp_path / "rotating"
    app, cfg = _cfg(
        NACOS_LOG_DIR=str(log_directory),
        NACOS_LOG_MAX_BYTES=1024,
        NACOS_LOG_BACKUP_COUNT=3,
    )
    nlog.configure_logger(app, cfg)
    files = _file_handlers(_flask_logger())
    assert len(files) == 1
    assert isinstance(files[0], RotatingFileHandler)


def test_no_max_bytes_uses_plain_file_handler(tmp_path):
    log_directory = tmp_path / "plain"
    app, cfg = _cfg(NACOS_LOG_DIR=str(log_directory))
    nlog.configure_logger(app, cfg)
    handler = _file_handlers(_flask_logger())[0]
    assert isinstance(handler, logging.FileHandler)
    assert not isinstance(handler, RotatingFileHandler)


# 18: file handler dedup -----------------------------------------------------

def test_repeated_configuration_does_not_duplicate_file_handler(tmp_path):
    log_directory = tmp_path / "dedup"
    app, cfg = _cfg(NACOS_LOG_DIR=str(log_directory))
    nlog.configure_logger(app, cfg)
    nlog.configure_logger(app, cfg)
    assert len(_file_handlers(_flask_logger())) == 1


def test_last_configuration_replaces_and_then_removes_file_handler(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    app, cfg = _cfg(NACOS_LOG_DIR=str(first))
    nlog.configure_logger(app, cfg)

    app, cfg = _cfg(NACOS_LOG_DIR=str(second))
    nlog.configure_logger(app, cfg)
    files = _file_handlers(_flask_logger())
    assert len(files) == 1
    assert files[0].baseFilename == str((second / "flask_nacos.log").resolve())

    app, cfg = _cfg(NACOS_LOG_ENABLED=False)
    nlog.configure_logger(app, cfg)
    assert _file_handlers(_flask_logger()) == []


# 19-20: propagation ---------------------------------------------------------

def test_propagate_false_applies_to_all_managed_loggers():
    app, cfg = _cfg(NACOS_LOG_PROPAGATE=False)
    nlog.configure_logger(app, cfg)
    for name in MANAGED_NAMES:
        assert logging.getLogger(name).propagate is False


def test_propagate_true_never_enables_sdk_propagation():
    app, cfg = _cfg(NACOS_LOG_PROPAGATE=True)
    nlog.configure_logger(app, cfg)
    assert _flask_logger().propagate is True
    for name in nlog.SDK_LOGGER_NAMES:
        assert logging.getLogger(name).propagate is False


# 21: use flask app.logger ---------------------------------------------------

def test_use_flask_logger_adds_no_new_handler():
    app = Flask(__name__)
    app_handler = logging.StreamHandler(StringIO())
    app.logger.addHandler(app_handler)
    app_handlers_before = list(app.logger.handlers)

    cfg = nconfig.load_config(app)
    cfg["NACOS_LOG_ENABLED"] = True
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


def test_sdk_records_never_reach_root_or_flask_nacos_handlers():
    root_buffer = StringIO()
    wrapper_buffer = StringIO()
    root_handler = logging.StreamHandler(root_buffer)
    wrapper_handler = logging.StreamHandler(wrapper_buffer)
    logging.getLogger().addHandler(root_handler)
    _flask_logger().addHandler(wrapper_handler)

    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=False, NACOS_LOG_PROPAGATE=True)
    nlog.configure_logger(app, cfg)
    logging.getLogger("nacos.client").critical("credential-and-config-content")

    assert root_buffer.getvalue() == ""
    assert wrapper_buffer.getvalue() == ""


def test_unrelated_sdk_file_handler_is_removed_to_enforce_total_isolation(tmp_path):
    custom_path = tmp_path / "user-added-sdk.log"
    sdk_logger = logging.getLogger("nacos.client")
    handler = logging.FileHandler(str(custom_path), encoding="utf-8")
    sdk_logger.addHandler(handler)

    app, cfg = _cfg()
    nlog.configure_logger(app, cfg)

    assert handler not in sdk_logger.handlers
    assert all(isinstance(item, logging.NullHandler) for item in sdk_logger.handlers)


def test_configured_file_contains_only_safe_wrapper_records(tmp_path):
    secrets = (
        "private-user",
        "private-password",
        "private-access-key",
        "private-secret-key",
        "private-access-token",
        "private-signature",
        "private-config-body",
    )
    log_directory = tmp_path / "logs"
    log_file = log_directory / "flask_nacos.log"
    app, cfg = _cfg(
        NACOS_LOG_DIR=str(log_directory), NACOS_LOG_LEVEL="DEBUG"
    )
    nlog.configure_logger(app, cfg)

    for secret in secrets:
        logging.getLogger("nacos.client").critical("raw SDK value: %s", secret)
    _flask_logger().info("safe wrapper status")
    for handler in _flask_logger().handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "safe wrapper status" in content
    assert all(secret not in content for secret in secrets)


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
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True)
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
        NACOS_LOG_ENABLED=True,
        NACOS_LOG_LEVEL="DEBUG",
        NACOS_LOG_TO_CONSOLE=True,
        NACOS_LOG_DIR=None,
    )
    FlaskNacos(app)
    output = buffer.getvalue()
    assert "supersecret-password" not in output


# 26: never create a log file at an unexpected path --------------------------

def test_no_file_created_outside_configured_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app, cfg = _cfg(NACOS_LOG_TO_CONSOLE=True, NACOS_LOG_DIR=None)
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
