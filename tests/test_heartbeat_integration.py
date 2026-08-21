"""Opt-in real-Nacos integration test for registration and SDK heartbeat behavior."""

import os
import time
import uuid

import pytest
from flask import Flask

from flask_nacos import FlaskNacos
from tests.helpers import wait_registered
from tests.integration_helpers import (
    create_external_sdk_client,
    integration_nacos_config,
    require_nacos_environment,
    wait_for,
)


@pytest.mark.integration
def test_temporary_instance_registration_discovery_and_heartbeat_recovery():
    """Cover auto/explicit registration and SDK behavior after out-of-band deletion."""
    environment = require_nacos_environment(
        "FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION", authenticated=False
    )
    heartbeat_interval = 5.0
    wait_seconds = float(os.environ.get("FLASK_NACOS_TEST_HEARTBEAT_WAIT_SECONDS", "35"))
    service_name = f"flask-nacos-heartbeat-test-{uuid.uuid4().hex}"
    service_port = 20000 + (uuid.uuid4().int % 30000)
    group = "FLASK_NACOS_HEARTBEAT_TEST"
    cluster = "FLASK_NACOS_TEST_CLUSTER"
    metadata = {"flask_nacos_test": uuid.uuid4().hex}

    app = Flask(__name__)
    app.config.update(
        **integration_nacos_config(environment),
        NACOS_AUTO_REGISTER=True,
        NACOS_DEREGISTER_ON_EXIT=False,
        NACOS_CONFIG_ENABLED=False,
        NACOS_SERVICE_NAME=service_name,
        NACOS_SERVICE_IP="127.0.0.1",
        NACOS_SERVICE_PORT=service_port,
        NACOS_SERVICE_GROUP=group,
        NACOS_SERVICE_CLUSTER=cluster,
        NACOS_SERVICE_METADATA=metadata,
        NACOS_SERVICE_EPHEMERAL=True,
        NACOS_SERVICE_HEARTBEAT_INTERVAL=heartbeat_interval,
        NACOS_RETRY_ENABLED=False,
        NACOS_FAIL_FAST=True,
    )
    extension = FlaskNacos(app)
    external_client = create_external_sdk_client(environment)

    def matching_instances():
        result = external_client.list_naming_instance(
            service_name,
            namespace_id=app.config["NACOS_NAMESPACE_ID"],
            group_name=group,
            healthy_only=False,
        )
        return [
            host
            for host in result.get("hosts", [])
            if host.get("ip") == "127.0.0.1" and host.get("port") == service_port
        ]

    try:
        wait_registered(extension, app, timeout=15.0)
        wait_for(lambda: bool(matching_instances()))
        assert matching_instances()[0].get("metadata", {}).get("flask_nacos_test") == metadata[
            "flask_nacos_test"
        ]

        # Observe multiple SDK heartbeat periods without involving the Lifecycle Worker.
        time.sleep(max(wait_seconds, heartbeat_interval * 3.0))
        assert matching_instances()[0].get("healthy") is True
        assert extension.get_status(app)["operation_running"] is False

        # A second SDK client simulates an out-of-band deletion. The owning SDK's
        # heartbeat behavior, not Flask-Nacos Lifecycle state, determines recovery.
        assert external_client.remove_naming_instance(
            service_name,
            "127.0.0.1",
            service_port,
            cluster_name=cluster,
            ephemeral=True,
            group_name=group,
        )
        wait_for(lambda: bool(matching_instances()), timeout=20.0)
        assert extension.get_status(app)["registered"] is True
        assert extension.get_status(app)["operation_running"] is False

        assert extension.deregister_instance(app) is True
        wait_registered(extension, app, expected=False)
        wait_for(lambda: not matching_instances())

        # This second registration is explicitly requested and uses the same state machine.
        assert extension.register_instance(app) is None
        wait_registered(extension, app, timeout=15.0)
        wait_for(lambda: bool(matching_instances()))
    finally:
        if extension.get_status(app)["registered"]:
            extension.deregister_instance(app)
        try:
            external_client.remove_naming_instance(
                service_name,
                "127.0.0.1",
                service_port,
                cluster_name=cluster,
                ephemeral=True,
                group_name=group,
            )
        except Exception:
            # The unique test identity will expire; cleanup must not hide the test result.
            pass
