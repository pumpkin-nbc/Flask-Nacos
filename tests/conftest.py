"""Shared pytest fixtures with a fully mocked Nacos SDK."""

from unittest.mock import MagicMock

import pytest
from flask import Flask

import flask_nacos.extension as extension_module
import flask_nacos.retry as retry_module


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Make retry backoff instant across the whole test suite."""
    monkeypatch.setattr(retry_module, "_sleep", lambda *a, **k: None)


@pytest.fixture
def fake_client():
    """A MagicMock standing in for the synchronous Nacos client."""
    client = MagicMock(name="NacosClient")
    client.add_naming_instance.return_value = True
    client.remove_naming_instance.return_value = True
    client.list_naming_instance.return_value = {
        "hosts": [
            {"ip": "127.0.0.1", "port": 8000, "healthy": True, "weight": 1.0},
            {"ip": "127.0.0.1", "port": 8001, "healthy": True, "weight": 1.0},
        ]
    }
    client.get_config.return_value = "server:\n  port: 8000\n"
    return client


@pytest.fixture
def patched_create_client(monkeypatch, fake_client):
    """Patch client creation so no real Nacos connection is ever made.

    Returns a dict recording how many times the factory was called and with
    which config, so tests can assert on initialization behavior.
    """
    calls = {"count": 0, "last_config": None}

    def _factory(config):
        calls["count"] += 1
        calls["last_config"] = config
        return fake_client

    monkeypatch.setattr(extension_module, "create_client", _factory)
    return calls


@pytest.fixture
def base_config():
    """Minimal config that enables registration without auto side effects."""
    return {
        "NACOS_SERVER_ADDR": "127.0.0.1:8848",
        "NACOS_SERVICE_NAME": "test-service",
        "NACOS_SERVICE_IP": "127.0.0.1",
        "NACOS_SERVICE_PORT": 8000,
        "NACOS_AUTO_REGISTER": False,
        "NACOS_AUTO_DEREGISTER": False,
    }


@pytest.fixture
def make_app(base_config):
    """Factory returning a configured Flask app.

    Pass ``overrides`` to change or add config values, or ``use_base=False`` to
    start from an empty config.
    """

    def _make(overrides=None, use_base=True):
        app = Flask(__name__)
        if use_base:
            app.config.update(base_config)
        if overrides:
            app.config.update(overrides)
        return app

    return _make
