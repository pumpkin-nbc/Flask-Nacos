"""Tests for isolated Nacos SDK client construction."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from flask_nacos.client import create_client
from flask_nacos.exceptions import NacosClientError


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
        ak="access",
        sk="secret",
    )


def test_create_client_omits_empty_authentication(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    create_client(_config(NACOS_NAMESPACE_ID=""))

    constructor.assert_called_once_with("nacos.example:8848", namespace="")


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
