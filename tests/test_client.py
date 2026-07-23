"""Tests for isolated Nacos SDK client construction."""

import logging
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.client import create_client
from flask_nacos.exceptions import NacosClientError, NacosConfigError


def _config(**overrides):
    config = {
        "NACOS_SERVER_ADDR": "nacos.example:8848",
        "NACOS_NAMESPACE_ID": "tenant-a",
        "NACOS_USERNAME": None,
        "NACOS_PASSWORD": None,
        "NACOS_ACCESS_KEY": None,
        "NACOS_SECRET_KEY": None,
    }
    config.update(overrides)
    return config


def test_create_client_forwards_username_and_password(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    client = create_client(
        _config(
            NACOS_USERNAME="user",
            NACOS_PASSWORD="password",
        )
    )

    assert client is constructor.return_value
    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
        username="user",
        password="password",
    )


def test_create_client_forwards_access_key_authentication(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    client = create_client(
        _config(
            NACOS_ACCESS_KEY="access",
            NACOS_SECRET_KEY="secret",
        )
    )

    assert client is constructor.return_value
    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
        ak="access",
        sk="secret",
    )


def test_create_client_omits_empty_authentication(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    create_client(_config(NACOS_NAMESPACE_ID=""))

    constructor.assert_called_once_with(
        "nacos.example:8848", namespace="", logDir=tempfile.gettempdir()
    )


def test_create_client_uses_configured_log_directory(monkeypatch, tmp_path):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))
    log_directory = tmp_path / "logs"

    create_client(
        _config(NACOS_LOG_ENABLED=True, NACOS_LOG_PATH=str(log_directory))
    )

    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=os.path.abspath(str(log_directory)),
    )


def test_create_client_does_not_pass_an_existing_file_as_log_directory(
    monkeypatch, tmp_path
):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))
    legacy_file = tmp_path / "logs"
    legacy_file.write_text("legacy", encoding="utf-8")

    create_client(_config(NACOS_LOG_ENABLED=True, NACOS_LOG_PATH=str(legacy_file)))

    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
    )


def test_create_client_wraps_constructor_failure(monkeypatch):
    constructor = MagicMock(side_effect=RuntimeError("invalid SDK setup"))
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    with pytest.raises(NacosClientError) as exc_info:
        create_client(_config())

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_create_client_wraps_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "nacos", None)

    with pytest.raises(NacosClientError) as exc_info:
        create_client(_config())

    assert isinstance(exc_info.value.__cause__, ImportError)


def test_real_sdk_constructor_creates_no_home_or_temporary_log(
    monkeypatch, tmp_path
):
    pytest.importorskip("nacos")
    fake_home = tmp_path / "home"
    sdk_temp = tmp_path / "temp"
    fake_home.mkdir()
    sdk_temp.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(sdk_temp))

    client = create_client(_config(NACOS_SERVER_ADDR="127.0.0.1:8848"))

    assert client is not None
    assert not (fake_home / "logs" / "nacos").exists()
    assert not (sdk_temp / "nacos-client-python.log").exists()


def test_real_sdk_does_not_create_configured_directory_when_logging_disabled(
    monkeypatch, tmp_path
):
    pytest.importorskip("nacos")
    configured_directory = tmp_path / "disabled-logs"
    sdk_temp = tmp_path / "temp"
    sdk_temp.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(sdk_temp))

    client = create_client(
        _config(
            NACOS_SERVER_ADDR="127.0.0.1:8848",
            NACOS_LOG_ENABLED=False,
            NACOS_LOG_PATH=str(configured_directory),
        )
    )

    assert client is not None
    assert not configured_directory.exists()
    assert not (sdk_temp / "nacos-client-python.log").exists()


@pytest.mark.parametrize(
    "auth_config",
    [
        {"NACOS_USERNAME": "user"},
        {"NACOS_PASSWORD": "password"},
        {"NACOS_ACCESS_KEY": "access"},
        {"NACOS_SECRET_KEY": "secret"},
        {
            "NACOS_USERNAME": "user",
            "NACOS_PASSWORD": "password",
            "NACOS_ACCESS_KEY": "access",
            "NACOS_SECRET_KEY": "secret",
        },
        {"NACOS_USERNAME": 123, "NACOS_PASSWORD": "password"},
    ],
)
def test_invalid_authentication_fails_before_client_creation(
    make_app, patched_create_client, auth_config
):
    app = make_app({**auth_config, "NACOS_FAIL_FAST": True})

    with pytest.raises(NacosConfigError):
        FlaskNacos(app)

    assert patched_create_client["count"] == 0
    assert "nacos" not in app.extensions


def test_invalid_authentication_is_safe_when_not_fail_fast(
    make_app, patched_create_client
):
    app = make_app(
        {
            "NACOS_USERNAME": "user",
            "NACOS_PASSWORD": "password",
            "NACOS_ACCESS_KEY": "access",
            "NACOS_SECRET_KEY": "secret",
            "NACOS_FAIL_FAST": False,
        }
    )

    extension = FlaskNacos(app)

    assert extension.client is None
    assert patched_create_client["count"] == 0


def test_invalid_authentication_does_not_log_credentials(
    make_app, patched_create_client, caplog
):
    credentials = (
        "private-auth-user",
        "private-auth-password",
        "private-auth-access-key",
        "private-auth-secret-key",
    )
    app = make_app(
        {
            "NACOS_USERNAME": credentials[0],
            "NACOS_PASSWORD": credentials[1],
            "NACOS_ACCESS_KEY": credentials[2],
            "NACOS_SECRET_KEY": credentials[3],
            "NACOS_FAIL_FAST": False,
            "NACOS_LOG_ENABLED": True,
            "NACOS_LOG_FILE_ENABLED": False,
        }
    )

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        extension = FlaskNacos(app)

    assert extension.client is None
    output = "\n".join(record.getMessage() for record in caplog.records)
    assert all(value not in output for value in credentials)
    assert patched_create_client["count"] == 0
