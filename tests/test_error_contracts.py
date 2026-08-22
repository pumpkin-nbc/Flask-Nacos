"""Tests for deterministic startup and precise synchronous error contracts."""

import logging
import threading
import time

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import (
    FlaskNacosError,
    NacosClientError,
    NacosConfigError,
    NacosDiscoveryError,
)
from tests.helpers import wait_registered, wait_until


def _failing_factory(_config):
    raise RuntimeError("boom: hidden runtime detail")


def test_client_constructor_failure_is_lazy_and_preserves_client_domain_error(
    make_app, monkeypatch
):
    monkeypatch.setattr(extension_module, "create_client", _failing_factory)
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.get_status(app)["client_created"] is False
    with pytest.raises(NacosClientError, match="Failed to create Nacos client") as exc:
        nacos.get_client(app)
    assert isinstance(exc.value.__cause__, RuntimeError)


@pytest.mark.parametrize("operation", ("client", "discovery", "config"))
def test_client_acquisition_domain_error_is_not_rewrapped(
    operation, make_app, monkeypatch
):
    client_error = NacosClientError("safe client failure")

    def failing_client_factory(_config):
        raise client_error

    monkeypatch.setattr(extension_module, "create_client", failing_client_factory)
    app = make_app({"NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    with app.app_context(), pytest.raises(NacosClientError) as exc:
        if operation == "client":
            nacos.get_client(app)
        elif operation == "discovery":
            nacos.list_instances("users")
        else:
            nacos.get_config("application.yaml")

    assert exc.value is client_error


def test_background_client_failure_never_propagates_from_register(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", _failing_factory)
    app = make_app({"NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    status = nacos.get_status(app)
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["last_error"] == "RuntimeError"


def test_auto_registration_local_connection_error_is_transactional(make_app):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_USERNAME": "only-user",
            "NACOS_PASSWORD": None,
        }
    )

    with pytest.raises(NacosConfigError):
        FlaskNacos(app)

    assert "nacos" not in app.extensions


def test_auto_registration_disabled_defers_connection_validation(make_app):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_USERNAME": "only-user",
            "NACOS_PASSWORD": None,
        }
    )
    nacos = FlaskNacos(app)

    assert "nacos" in app.extensions
    with pytest.raises(NacosConfigError):
        nacos.get_client(app)


def test_auto_registration_does_not_wait_for_client_or_network(
    make_app, fake_client, monkeypatch
):
    entered = threading.Event()
    release = threading.Event()

    def slow_factory(_config):
        entered.set()
        assert release.wait(2)
        return fake_client

    monkeypatch.setattr(extension_module, "create_client", slow_factory)
    app = make_app({"NACOS_AUTO_REGISTER": True})
    started = time.monotonic()
    nacos = FlaskNacos(app)

    try:
        assert time.monotonic() - started < 0.5
        assert entered.wait(1)
        assert nacos.get_status(app)["operation_running"] is True
    finally:
        release.set()

    wait_registered(nacos, app)


def test_uninitialized_extension_still_raises_for_operations():
    nacos = FlaskNacos()
    with pytest.raises(FlaskNacosError):
        nacos.list_instances("users")


def test_synchronous_sdk_failures_keep_specific_domain_types_and_causes(
    make_app, patched_create_client, fake_client
):
    config_failure = RuntimeError("config-network")
    discovery_failure = RuntimeError("discovery-network")
    fake_client.get_config.side_effect = config_failure
    fake_client.list_naming_instance.side_effect = discovery_failure
    app = make_app({"NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    with app.app_context():
        with pytest.raises(NacosConfigError) as config_exc:
            nacos.get_config("application.yaml")
        with pytest.raises(NacosDiscoveryError) as discovery_exc:
            nacos.list_instances("users")

    assert config_exc.value.__cause__ is config_failure
    assert discovery_exc.value.__cause__ is discovery_failure


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
