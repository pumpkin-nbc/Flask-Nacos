"""Opt-in integration test for a real username/password-protected Nacos."""

import os
import uuid

import pytest
from flask import Flask

from flask_nacos import FlaskNacos


@pytest.mark.integration
def test_authenticated_config_round_trip():
    """Publish, read, and remove a temporary config through authenticated Nacos."""
    if os.environ.get("FLASK_NACOS_RUN_AUTH_INTEGRATION") != "1":
        pytest.skip("set FLASK_NACOS_RUN_AUTH_INTEGRATION=1 to run this test")

    required_names = (
        "FLASK_NACOS_TEST_SERVER_ADDR",
        "FLASK_NACOS_TEST_USERNAME",
        "FLASK_NACOS_TEST_PASSWORD",
    )
    missing = [name for name in required_names if not os.environ.get(name)]
    if missing:
        pytest.skip("missing authenticated Nacos integration-test environment")

    app = Flask(__name__)
    app.config.update(
        NACOS_SERVER_ADDR=os.environ["FLASK_NACOS_TEST_SERVER_ADDR"],
        NACOS_NAMESPACE_ID=os.environ.get("FLASK_NACOS_TEST_NAMESPACE_ID", ""),
        NACOS_USERNAME=os.environ["FLASK_NACOS_TEST_USERNAME"],
        NACOS_PASSWORD=os.environ["FLASK_NACOS_TEST_PASSWORD"],
        NACOS_AUTO_REGISTER=False,
        NACOS_AUTO_DEREGISTER=False,
        NACOS_CONFIG_ENABLED=True,
        NACOS_REQUEST_TIMEOUT=5.0,
        NACOS_RETRY_ENABLED=False,
        NACOS_FAIL_FAST=True,
    )
    extension = FlaskNacos(app)
    client = extension.get_client()
    data_id = f"flask-nacos-auth-test-{uuid.uuid4().hex}.properties"
    group = "FLASK_NACOS_TEST"
    content = f"test.id={uuid.uuid4().hex}"

    try:
        assert client.publish_config(data_id, group, content, timeout=5.0)
        assert extension.get_config(data_id, group=group) == content
    finally:
        client.remove_config(data_id, group, timeout=5.0)
