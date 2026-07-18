"""Opt-in integration test for temporary-instance heartbeat renewal."""

import os
import time
import uuid

import pytest
from flask import Flask

from flask_nacos import FlaskNacos


@pytest.mark.integration
def test_temporary_instance_stays_healthy_after_deletion_window():
    """Keep a temporary instance healthy beyond Nacos' usual timeout window."""
    if os.environ.get("FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION") != "1":
        pytest.skip("set FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION=1 to run this test")

    server_addr = os.environ.get("FLASK_NACOS_TEST_SERVER_ADDR")
    if not server_addr:
        pytest.skip("missing FLASK_NACOS_TEST_SERVER_ADDR")

    wait_seconds = float(
        os.environ.get("FLASK_NACOS_TEST_HEARTBEAT_WAIT_SECONDS", "35")
    )
    service_name = f"flask-nacos-heartbeat-test-{uuid.uuid4().hex}"
    service_port = 20000 + (uuid.uuid4().int % 30000)
    group = "FLASK_NACOS_HEARTBEAT_TEST"

    app = Flask(__name__)
    app.config.update(
        NACOS_SERVER_ADDR=server_addr,
        NACOS_NAMESPACE_ID=os.environ.get("FLASK_NACOS_TEST_NAMESPACE_ID", ""),
        NACOS_USERNAME=os.environ.get("FLASK_NACOS_TEST_USERNAME"),
        NACOS_PASSWORD=os.environ.get("FLASK_NACOS_TEST_PASSWORD"),
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_CONFIG_ENABLED=False,
        NACOS_SERVICE_NAME=service_name,
        NACOS_SERVICE_IP="127.0.0.1",
        NACOS_SERVICE_PORT=service_port,
        NACOS_SERVICE_GROUP=group,
        NACOS_SERVICE_EPHEMERAL=True,
        NACOS_SERVICE_HEARTBEAT_INTERVAL=5.0,
        NACOS_RETRY_ENABLED=False,
        NACOS_FAIL_FAST=True,
    )
    extension = FlaskNacos(app)
    registered = False

    try:
        assert extension.register_instance() is True
        registered = True
        time.sleep(wait_seconds)
        instances = extension.list_instances(
            service_name, group=group, healthy_only=True
        )
        assert any(
            instance["ip"] == "127.0.0.1" and instance["port"] == service_port
            for instance in instances
        )
    finally:
        if registered:
            extension.deregister_instance()
