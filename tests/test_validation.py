"""Tests for enhanced service registration parameter validation."""

import logging

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosValidationError
from flask_nacos.extension import EXTENSION_KEY


@pytest.fixture
def nacos_factory(make_app, patched_create_client):
    """Build a FlaskNacos with the given config overrides (auto-register off)."""

    def _build(overrides):
        merged = {"NACOS_AUTO_REGISTER": False}
        merged.update(overrides)
        app = make_app(merged)
        return FlaskNacos(app)

    return _build


# -- fail-fast = True: validation raises -----------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"NACOS_SERVICE_NAME": None},
        {"NACOS_SERVICE_NAME": ""},
        {"NACOS_SERVICE_PORT": None},
        {"NACOS_SERVICE_PORT": 0},
        {"NACOS_SERVICE_PORT": 70000},
        {"NACOS_SERVICE_PORT": 8000.5},
        {"NACOS_SERVICE_PORT": True},
        {"NACOS_SERVICE_PORT": float("inf")},
        {"NACOS_SERVICE_PORT": "not-a-port"},
        {"NACOS_SERVICE_WEIGHT": 0},
        {"NACOS_SERVICE_WEIGHT": -1},
        {"NACOS_SERVICE_WEIGHT": True},
        {"NACOS_SERVICE_WEIGHT": float("nan")},
        {"NACOS_SERVICE_WEIGHT": float("inf")},
        {"NACOS_SERVICE_WEIGHT": "abc"},
        {"NACOS_SERVICE_METADATA": ["not", "a", "dict"]},
        {"NACOS_SERVICE_METADATA": "string"},
        {"NACOS_SERVICE_EPHEMERAL": "yes"},
        {"NACOS_SERVICE_EPHEMERAL": 1},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": 0},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": -1},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": True},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": float("nan")},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": float("inf")},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": "abc"},
    ],
)
def test_invalid_params_raise_when_fail_fast(nacos_factory, overrides):
    overrides = {**overrides, "NACOS_FAIL_FAST": True}
    nacos = nacos_factory(overrides)
    with pytest.raises(NacosValidationError):
        nacos.register_instance()


@pytest.mark.parametrize("mode", ["direct", "factory"])
@pytest.mark.parametrize("service_name", [None, "", "   ", 123, True])
def test_auto_registration_preflight_fails_before_client_and_state(
    make_app,
    patched_create_client,
    fake_client,
    mode,
    service_name,
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": service_name,
            "NACOS_REGISTER_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_AUTO_REGISTER_ON_INIT": True,
            "NACOS_FAIL_FAST": True,
        }
    )

    if mode == "direct":
        with pytest.raises(NacosValidationError, match="NACOS_SERVICE_NAME"):
            FlaskNacos(app)
    else:
        nacos = FlaskNacos()
        with pytest.raises(NacosValidationError, match="NACOS_SERVICE_NAME"):
            nacos.init_app(app)
        assert nacos.app is None
        assert nacos.client is None

    assert EXTENSION_KEY not in app.extensions
    assert patched_create_client["count"] == 0
    fake_client.add_naming_instance.assert_not_called()


def test_invalid_auto_registration_logs_and_continues_when_not_fail_fast(
    make_app,
    patched_create_client,
    fake_client,
    caplog,
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_REGISTER_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_AUTO_REGISTER_ON_INIT": True,
            "NACOS_FAIL_FAST": False,
            "NACOS_LOG_ENABLED": True,
            "NACOS_LOG_DIR": None,
        }
    )

    with caplog.at_level(logging.ERROR, logger="flask_nacos"):
        nacos = FlaskNacos(app)

    assert patched_create_client["count"] == 1
    fake_client.add_naming_instance.assert_not_called()
    assert nacos.get_status()["registered"] is False
    assert nacos.get_config("application.yaml") == "server:\n  port: 8000\n"
    assert "Automatic registration skipped" in caplog.text
    assert "NACOS_SERVICE_NAME" in caplog.text


@pytest.mark.parametrize(
    "disabled_switch",
    [
        "NACOS_REGISTER_ENABLED",
        "NACOS_AUTO_REGISTER",
        "NACOS_AUTO_REGISTER_ON_INIT",
    ],
)
def test_missing_service_name_is_allowed_when_auto_registration_is_disabled(
    make_app,
    patched_create_client,
    fake_client,
    disabled_switch,
):
    overrides = {
        "NACOS_SERVICE_NAME": None,
        "NACOS_REGISTER_ENABLED": True,
        "NACOS_AUTO_REGISTER": True,
        "NACOS_AUTO_REGISTER_ON_INIT": True,
        "NACOS_FAIL_FAST": True,
        disabled_switch: False,
    }
    app = make_app(overrides)

    nacos = FlaskNacos(app)

    assert patched_create_client["count"] == 1
    fake_client.add_naming_instance.assert_not_called()
    assert nacos.get_config("application.yaml") == "server:\n  port: 8000\n"
    with pytest.raises(NacosValidationError, match="NACOS_SERVICE_NAME"):
        nacos.register_instance()
    fake_client.add_naming_instance.assert_not_called()


# -- fail-fast = False: register returns False ------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"NACOS_SERVICE_NAME": None},
        {"NACOS_SERVICE_PORT": None},
        {"NACOS_SERVICE_PORT": 70000},
        {"NACOS_SERVICE_PORT": 8000.5},
        {"NACOS_SERVICE_PORT": True},
        {"NACOS_SERVICE_PORT": float("inf")},
        {"NACOS_SERVICE_WEIGHT": 0},
        {"NACOS_SERVICE_WEIGHT": True},
        {"NACOS_SERVICE_WEIGHT": float("nan")},
        {"NACOS_SERVICE_WEIGHT": float("inf")},
        {"NACOS_SERVICE_METADATA": ["not", "a", "dict"]},
        {"NACOS_SERVICE_EPHEMERAL": "yes"},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": 0},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": -1},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": True},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": float("nan")},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": float("inf")},
        {"NACOS_SERVICE_HEARTBEAT_INTERVAL": "abc"},
    ],
)
def test_invalid_params_return_false_when_not_fail_fast(
    nacos_factory, overrides, fake_client
):
    overrides = {**overrides, "NACOS_FAIL_FAST": False}
    nacos = nacos_factory(overrides)
    assert nacos.register_instance() is False
    fake_client.add_naming_instance.assert_not_called()


# -- IP auto-detection ------------------------------------------------------

def test_ip_auto_detect_failure_raises_when_fail_fast(nacos_factory, monkeypatch):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: None)
    nacos = nacos_factory({"NACOS_SERVICE_IP": None, "NACOS_FAIL_FAST": True})
    with pytest.raises(NacosValidationError):
        nacos.register_instance()


def test_ip_auto_detect_failure_returns_false_when_not_fail_fast(
    nacos_factory, monkeypatch, fake_client
):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: None)
    nacos = nacos_factory({"NACOS_SERVICE_IP": None, "NACOS_FAIL_FAST": False})
    assert nacos.register_instance() is False
    fake_client.add_naming_instance.assert_not_called()


def test_valid_params_register_successfully(nacos_factory, fake_client):
    nacos = nacos_factory({"NACOS_SERVICE_PORT": 8080, "NACOS_SERVICE_WEIGHT": 2.0})
    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()
