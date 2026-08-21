"""Opt-in integration tests for a real username/password-protected Nacos."""

import importlib.metadata
import uuid

import pytest
from flask import Flask

import flask_nacos.client as client_module
import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError
from tests.integration_helpers import (
    TcpGate,
    integration_nacos_config,
    parse_single_server_address,
    require_nacos_environment,
    wait_for,
)


@pytest.mark.integration
def test_authenticated_config_round_trip():
    """Publish, read, miss, and remove a unique config through authenticated Nacos."""
    environment = require_nacos_environment(
        "FLASK_NACOS_RUN_AUTH_INTEGRATION", authenticated=True
    )
    app = Flask(__name__)
    app.config.update(
        **integration_nacos_config(environment),
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_CONFIG_ENABLED=True,
        NACOS_REQUEST_TIMEOUT=5.0,
        NACOS_RETRY_ENABLED=False,
        NACOS_FAIL_FAST=True,
    )
    extension = FlaskNacos(app)
    client = extension.get_client()
    run_id = uuid.uuid4().hex
    data_id = f"flask-nacos-auth-test-{run_id}.properties"
    missing_data_id = f"flask-nacos-auth-missing-{run_id}.properties"
    group = "FLASK_NACOS_TEST"
    content = f"test.id={run_id}"

    try:
        assert extension.get_config(missing_data_id, group=group) is None
        assert client.publish_config(data_id, group, content, timeout=5.0)
        assert extension.get_config(data_id, group=group) == content
    finally:
        client.remove_config(data_id, group, timeout=5.0)


@pytest.mark.integration
def test_invalid_credentials_fail_deterministically():
    """A protected real server must reject an intentionally wrong password."""
    environment = require_nacos_environment(
        "FLASK_NACOS_RUN_AUTH_INTEGRATION", authenticated=True
    )
    config = integration_nacos_config(environment)
    config["NACOS_PASSWORD"] = f"flask-nacos-invalid-{uuid.uuid4().hex}"
    app = Flask(__name__)
    app.config.update(
        **config,
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_CONFIG_ENABLED=False,
        NACOS_RETRY_ENABLED=False,
        NACOS_FAIL_FAST=True,
    )
    extension = FlaskNacos(app)

    with pytest.raises(FlaskNacosError, match="Failed to create Nacos client"):
        extension.get_client(app)


@pytest.mark.integration
def test_authenticated_client_create_recovers_through_tcp_gate(monkeypatch):
    """Recover in the final PID without HTTP, a second register, or get_client()."""
    environment = require_nacos_environment(
        "FLASK_NACOS_RUN_AUTH_INTEGRATION", authenticated=True
    )
    if importlib.metadata.version("nacos-sdk-python") != "2.0.11":
        pytest.skip("the exact CLIENT_CREATE Recovery guarantee targets SDK 2.0.11")
    try:
        upstream = parse_single_server_address(environment["FLASK_NACOS_TEST_SERVER_ADDR"])
    except ValueError as exc:
        pytest.skip(str(exc))

    actual_create_client = client_module.create_client
    create_attempts = []

    def counted_create_client(config):
        create_attempts.append(object())
        return actual_create_client(config)

    monkeypatch.setattr(extension_module, "create_client", counted_create_client)
    service_name = f"flask-nacos-gate-test-{uuid.uuid4().hex}"
    service_port = 20000 + (uuid.uuid4().int % 30000)

    with TcpGate(upstream) as gate:
        config = integration_nacos_config(environment)
        config["NACOS_SERVER_ADDR"] = gate.address
        app = Flask(__name__)
        app.config.update(
            **config,
            NACOS_AUTO_REGISTER=True,
            NACOS_AUTO_DEREGISTER=False,
            NACOS_CONFIG_ENABLED=False,
            NACOS_SERVICE_NAME=service_name,
            NACOS_SERVICE_IP="127.0.0.1",
            NACOS_SERVICE_PORT=service_port,
            NACOS_SERVICE_GROUP="FLASK_NACOS_GATE_TEST",
            NACOS_SERVICE_METADATA={"flask_nacos_test": uuid.uuid4().hex},
            NACOS_RETRY_ENABLED=True,
            NACOS_RETRY_TIMES=1,
            NACOS_RETRY_INTERVAL=0.0,
            NACOS_FAIL_FAST=True,
        )
        extension = FlaskNacos(app)
        try:
            wait_for(
                lambda: len(create_attempts) > 1
                and extension.get_status(app)["operation_running"] is True,
                timeout=20.0,
            )
            assert extension.get_status(app)["registered"] is False
            gate.open()
            wait_for(
                lambda: extension.get_status(app)["registered"] is True
                and extension.get_status(app)["operation_running"] is False,
                timeout=30.0,
            )
            status = extension.get_status(app)
            assert status["target_registered"] is True
            assert status["registered"] is True
            assert status["last_error"] is None
            assert len(create_attempts) > 1
            assert gate.connection_count > 1
        finally:
            if extension.get_status(app)["registered"]:
                extension.deregister_instance(app)
