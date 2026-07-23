"""Tests for NACOS_FAIL_FAST behavior and secret-safe logging."""

import logging

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import (
    FlaskNacosError,
    NacosClientError,
    NacosConfigError,
    NacosRegistrationError,
)


def _make_failing_factory():
    def _factory(config):
        raise RuntimeError("boom: cannot connect")

    return _factory


def test_init_failure_does_not_raise_when_not_fail_fast(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", _make_failing_factory())
    app = make_app({"NACOS_FAIL_FAST": False})

    # Should not raise; Flask app initialization continues.
    nacos = FlaskNacos(app)
    assert nacos.client is None


def test_init_failure_raises_when_fail_fast(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", _make_failing_factory())
    app = make_app({"NACOS_FAIL_FAST": True})

    with pytest.raises(NacosClientError) as exc_info:
        FlaskNacos(app)
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "nacos" not in app.extensions


def test_failed_init_can_be_retried_after_configuration_is_fixed(
    make_app, monkeypatch, fake_client
):
    calls = {"count": 0}

    def factory(config):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary constructor failure")
        return fake_client

    monkeypatch.setattr(extension_module, "create_client", factory)
    app = make_app({"NACOS_FAIL_FAST": True})
    nacos = FlaskNacos()

    with pytest.raises(NacosClientError):
        nacos.init_app(app)

    assert "nacos" not in app.extensions
    assert nacos.app is None
    nacos.init_app(app)
    assert nacos.client is fake_client
    assert calls["count"] == 2


def test_auto_registration_failure_rolls_back_and_allows_retry(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_AUTO_DEREGISTER": False,
            "NACOS_FAIL_FAST": True,
            "NACOS_RETRY_ENABLED": False,
        }
    )
    fake_client.add_naming_instance.return_value = False
    nacos = FlaskNacos()

    with pytest.raises(NacosRegistrationError):
        nacos.init_app(app)

    assert "nacos" not in app.extensions
    assert nacos.app is None
    fake_client.add_naming_instance.return_value = True
    nacos.init_app(app)
    assert nacos.get_status()["registered"] is True


def test_failed_second_app_init_preserves_previous_app_state(
    make_app, monkeypatch, fake_client
):
    def factory(config):
        if config["NACOS_SERVICE_NAME"] == "service-b":
            raise RuntimeError("second app failed")
        return fake_client

    monkeypatch.setattr(extension_module, "create_client", factory)
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a", "NACOS_FAIL_FAST": True})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b", "NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app_a)

    with pytest.raises(NacosClientError):
        nacos.init_app(app_b)

    assert "nacos" not in app_b.extensions
    assert nacos.app is app_a
    assert nacos.client is fake_client
    assert nacos.get_status()["service_name"] == "service-a"


def test_non_fail_fast_unavailable_client_uses_safe_operation_defaults(
    make_app, monkeypatch
):
    monkeypatch.setattr(extension_module, "create_client", _make_failing_factory())
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is False
    assert nacos.deregister_instance() is False
    assert nacos.list_instances("users") == []
    assert nacos.get_one_healthy_instance("users") is None
    assert nacos.get_config("application.yaml") is None


def test_uninitialized_extension_still_raises_for_operations():
    nacos = FlaskNacos()

    with pytest.raises(FlaskNacosError):
        nacos.list_instances("users")


def test_get_config_error_returns_none_when_not_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.get_config.side_effect = RuntimeError("network error")
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.get_config("application.yaml") is None


def test_get_config_error_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.get_config.side_effect = RuntimeError("network error")
    app = make_app({"NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosConfigError):
        nacos.get_config("application.yaml")


def test_discovery_error_returns_empty_when_not_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.side_effect = RuntimeError("network error")
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.list_instances("user-service") == []


def test_secrets_never_logged(make_app, patched_create_client, fake_client, caplog):
    secret_user = "private-user"
    secret_pw = "super-secret-password"
    secret_ak = "AK-1234567890"
    secret_sk = "SK-abcdefghij"

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        app = make_app(
            {
                "NACOS_USERNAME": secret_user,
                "NACOS_PASSWORD": secret_pw,
                "NACOS_AUTO_REGISTER": True,
                "NACOS_HEALTH_CHECK_ENABLED": True,
                "NACOS_LOG_ENABLED": True,
                "NACOS_LOG_DIR": None,
            }
        )
        nacos = FlaskNacos(app)
        nacos.get_config("application.yaml")
        nacos.list_instances("user-service")
        nacos.deregister_instance()
        nacos.get_status()
        app.test_client().get("/health/nacos")

        ak_app = make_app(
            {
                "NACOS_ACCESS_KEY": secret_ak,
                "NACOS_SECRET_KEY": secret_sk,
            }
        )
        ak_nacos = FlaskNacos(ak_app)
        ak_nacos.get_status()

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_user not in combined
    assert secret_pw not in combined
    assert secret_ak not in combined
    assert secret_sk not in combined


def test_retry_final_failure_logs_no_secrets(
    make_app, patched_create_client, fake_client, caplog
):
    secret_pw = "another-secret-pw"
    fake_client.add_naming_instance.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        app = make_app(
            {
                "NACOS_PASSWORD": secret_pw,
                "NACOS_AUTO_REGISTER": True,
                "NACOS_RETRY_TIMES": 3,
                "NACOS_FAIL_FAST": False,
                "NACOS_LOG_ENABLED": True,
                "NACOS_LOG_DIR": None,
            }
        )
        FlaskNacos(app)

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_pw not in combined
