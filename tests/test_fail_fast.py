"""Tests for NACOS_FAIL_FAST behavior and secret-safe logging."""

import logging

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosConfigError


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

    with pytest.raises(RuntimeError):
        FlaskNacos(app)


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
    secret_pw = "super-secret-password"
    secret_ak = "AK-1234567890"
    secret_sk = "SK-abcdefghij"

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        app = make_app(
            {
                "NACOS_PASSWORD": secret_pw,
                "NACOS_ACCESS_KEY": secret_ak,
                "NACOS_SECRET_KEY": secret_sk,
                "NACOS_AUTO_REGISTER": True,
                "NACOS_HEALTH_CHECK_ENABLED": True,
            }
        )
        nacos = FlaskNacos(app)
        nacos.get_config("application.yaml")
        nacos.list_instances("user-service")
        nacos.deregister_instance()
        nacos.get_status()
        app.test_client().get("/health/nacos")

    combined = "\n".join(record.getMessage() for record in caplog.records)
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
            }
        )
        FlaskNacos(app)

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_pw not in combined
