"""Tests for fail-fast boundaries and secret-safe runtime errors."""

import logging

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError, NacosConfigError
from tests.helpers import wait_until


def _failing_factory(_config):
    raise RuntimeError("boom: hidden runtime detail")


@pytest.mark.parametrize("fail_fast", [False, True])
def test_client_constructor_failure_is_lazy_and_get_client_always_raises_safely(
    make_app, monkeypatch, fail_fast
):
    monkeypatch.setattr(extension_module, "create_client", _failing_factory)
    app = make_app({"NACOS_FAIL_FAST": fail_fast})
    nacos = FlaskNacos(app)

    assert nacos.get_status(app)["client_created"] is False
    with pytest.raises(FlaskNacosError, match="Failed to create Nacos client") as exc:
        nacos.get_client(app)
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.parametrize("fail_fast", [False, True])
def test_background_client_failure_never_propagates_from_register(make_app, monkeypatch, fail_fast):
    monkeypatch.setattr(extension_module, "create_client", _failing_factory)
    app = make_app(
        {
            "NACOS_FAIL_FAST": fail_fast,
            "NACOS_RETRY_ENABLED": False,
        }
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    assert nacos.get_status(app)["target_registered"] is True
    assert nacos.get_status(app)["registered"] is False
    assert nacos.get_status(app)["last_error"] == "RuntimeError"


def test_deterministic_connection_error_fails_before_state(make_app):
    app = make_app(
        {
            "NACOS_USERNAME": "only-user",
            "NACOS_PASSWORD": None,
            "NACOS_FAIL_FAST": True,
        }
    )
    with pytest.raises(NacosConfigError):
        FlaskNacos(app)
    assert "nacos" not in app.extensions


def test_non_fail_fast_bad_connection_keeps_state_but_client_request_fails(make_app):
    app = make_app(
        {
            "NACOS_USERNAME": "only-user",
            "NACOS_PASSWORD": None,
            "NACOS_FAIL_FAST": False,
        }
    )
    nacos = FlaskNacos(app)
    assert "nacos" in app.extensions
    with pytest.raises(FlaskNacosError):
        nacos.get_client(app)


def test_uninitialized_extension_still_raises_for_operations():
    nacos = FlaskNacos()
    with pytest.raises(FlaskNacosError):
        nacos.list_instances("users")


def test_non_fail_fast_general_operations_return_safe_defaults(
    make_app, patched_create_client, fake_client
):
    fake_client.get_config.side_effect = RuntimeError("network")
    fake_client.list_naming_instance.side_effect = RuntimeError("network")
    app = make_app({"NACOS_FAIL_FAST": False, "NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    with app.app_context():
        assert nacos.get_config("application.yaml") is None
        assert nacos.list_instances("users") == []


def test_fail_fast_general_config_operation_raises(make_app, patched_create_client, fake_client):
    fake_client.get_config.side_effect = RuntimeError("network")
    app = make_app({"NACOS_FAIL_FAST": True, "NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    with app.app_context(), pytest.raises(NacosConfigError):
        nacos.get_config("application.yaml")


def test_runtime_logs_and_status_never_expose_credentials(
    make_app, patched_create_client, fake_client, caplog
):
    secret_user = "private-user"
    secret_pw = "super-secret-password"
    fake_client.add_naming_instance.side_effect = RuntimeError("network")
    app = make_app(
        {
            "NACOS_USERNAME": secret_user,
            "NACOS_PASSWORD": secret_pw,
            "NACOS_RETRY_ENABLED": False,
            "NACOS_LOG_ENABLED": True,
            "NACOS_LOG_FILE_ENABLED": False,
        }
    )

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        nacos = FlaskNacos(app)
        nacos.register_instance(app)
        wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
        status = nacos.get_status(app)

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_user not in combined
    assert secret_pw not in combined
    assert secret_user not in "".join(str(value) for value in status.values())
    assert secret_pw not in "".join(str(value) for value in status.values())
