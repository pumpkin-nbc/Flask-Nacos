"""Tests for deterministic registration validation and fail-fast boundaries."""

import logging

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosValidationError
from flask_nacos.extension import EXTENSION_KEY
from tests.helpers import wait_registered, wait_until

INVALID_REGISTRATION_SETTINGS = [
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
]


@pytest.mark.parametrize("overrides", INVALID_REGISTRATION_SETTINGS)
def test_manual_register_reuses_cached_validation_and_fail_fast(
    make_app, patched_create_client, fake_client, overrides
):
    app = make_app({**overrides, "NACOS_AUTO_REGISTER": False, "NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosValidationError):
        nacos.register_instance(app)

    status = nacos.get_status(app)
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == "NacosValidationError"
    assert patched_create_client["count"] == 0
    fake_client.add_naming_instance.assert_not_called()


@pytest.mark.parametrize("overrides", INVALID_REGISTRATION_SETTINGS)
def test_non_fail_fast_invalid_register_has_stable_error_without_worker(
    make_app, patched_create_client, fake_client, overrides
):
    app = make_app({**overrides, "NACOS_AUTO_REGISTER": False, "NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)
    runtime = app.extensions[EXTENSION_KEY]["_runtime"]

    nacos.register_instance(app)
    generation = runtime.operation_generation
    nacos.register_instance(app)

    assert runtime.operation_generation == generation
    assert nacos.get_status(app)["last_error"] == "NacosValidationError"
    assert nacos.get_status(app)["operation_running"] is False
    assert patched_create_client["count"] == 0
    fake_client.add_naming_instance.assert_not_called()


@pytest.mark.parametrize("mode", ["direct", "factory"])
@pytest.mark.parametrize("service_name", [None, "", "   ", 123, True])
def test_auto_registration_fail_fast_is_transactional(
    make_app, patched_create_client, fake_client, mode, service_name
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": service_name,
            "NACOS_REGISTER_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
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

    assert EXTENSION_KEY not in app.extensions
    assert patched_create_client["count"] == 0
    fake_client.add_naming_instance.assert_not_called()


def test_invalid_auto_registration_non_fail_fast_keeps_usable_extension(
    make_app, patched_create_client, fake_client, caplog
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_FAIL_FAST": False,
            "NACOS_LOG_ENABLED": True,
            "NACOS_LOG_FILE_ENABLED": False,
        }
    )

    with caplog.at_level(logging.ERROR, logger="flask_nacos"):
        nacos = FlaskNacos(app)

    status = nacos.get_status(app)
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == "NacosValidationError"
    assert patched_create_client["count"] == 0
    with app.app_context():
        assert nacos.get_config("application.yaml") == "server:\n  port: 8000\n"
    assert patched_create_client["count"] == 1
    fake_client.add_naming_instance.assert_not_called()
    assert "NACOS_SERVICE_NAME" in caplog.text


@pytest.mark.parametrize(
    "invalid_retry",
    [
        {"NACOS_RETRY_TIMES": 0},
        {"NACOS_RETRY_TIMES": True},
        {"NACOS_RETRY_TIMES": 1.5},
        {"NACOS_RETRY_INTERVAL": -1},
        {"NACOS_RETRY_INTERVAL": float("nan")},
    ],
)
def test_auto_registration_retry_config_is_deterministic(
    make_app, patched_create_client, invalid_retry
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_FAIL_FAST": True,
            **invalid_retry,
        }
    )
    with pytest.raises(NacosValidationError):
        FlaskNacos(app)
    assert EXTENSION_KEY not in app.extensions
    assert patched_create_client["count"] == 0


def test_retry_numbers_are_ignored_when_retry_disabled(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {
            "NACOS_RETRY_ENABLED": False,
            "NACOS_RETRY_TIMES": 0,
            "NACOS_RETRY_INTERVAL": float("nan"),
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()


def test_register_enabled_false_makes_registration_a_noop(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_REGISTER_ENABLED": False,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    status = nacos.get_status(app)
    assert status["target_registered"] is False
    assert status["last_error"] is None
    assert patched_create_client["count"] == 0
    fake_client.add_naming_instance.assert_not_called()


def test_missing_service_name_allowed_at_init_but_explicit_register_fails(
    make_app, patched_create_client
):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_AUTO_REGISTER": False,
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos(app)
    with pytest.raises(NacosValidationError):
        nacos.register_instance(app)


@pytest.mark.parametrize("fail_fast", [False, True])
def test_ip_auto_detect_failure_is_background_runtime_error(
    make_app, patched_create_client, fake_client, monkeypatch, fail_fast
):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: None)
    app = make_app(
        {
            "NACOS_SERVICE_IP": None,
            "NACOS_FAIL_FAST": fail_fast,
            "NACOS_RETRY_ENABLED": False,
        }
    )
    nacos = FlaskNacos(app)
    assert nacos.register_instance(app) is None
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    assert nacos.get_status(app)["last_error"] == "NacosValidationError"
    fake_client.add_naming_instance.assert_not_called()


def test_valid_registration_settings_succeed(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_SERVICE_PORT": 8080, "NACOS_SERVICE_WEIGHT": 2.0})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()
