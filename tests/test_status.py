"""Tests for the fixed local ``get_status()`` snapshot."""

import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered

EXPECTED_KEYS = {
    "enabled",
    "pid",
    "client_created",
    "service_name",
    "group_name",
    "cluster_name",
    "service_ip",
    "service_port",
    "target_registered",
    "registered",
    "operation_running",
    "last_error",
}


def test_get_status_has_exact_fields_and_configuration_identity(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": "fund-service",
            "NACOS_SERVICE_PORT": 5000,
            "NACOS_SERVICE_GROUP": "FUNDS",
            "NACOS_SERVICE_CLUSTER": "BLUE",
        }
    )
    nacos = FlaskNacos(app)

    status = nacos.get_status(app)
    assert set(status) == EXPECTED_KEYS
    assert status == {
        "enabled": True,
        "pid": lifecycle_module.current_pid(),
        "client_created": False,
        "service_name": "fund-service",
        "group_name": "FUNDS",
        "cluster_name": "BLUE",
        "service_ip": "127.0.0.1",
        "service_port": 5000,
        "target_registered": False,
        "registered": False,
        "operation_running": False,
        "last_error": None,
    }
    assert patched_create_client["count"] == 0


def test_registered_status_uses_actual_cached_identity(
    make_app, patched_create_client, monkeypatch
):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: "192.0.2.25")
    app = make_app(
        {
            "NACOS_SERVICE_IP": None,
            "NACOS_SERVICE_GROUP": "PROD",
            "NACOS_SERVICE_CLUSTER": "GREEN",
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    status = nacos.get_status(app)
    assert status["registered"] is True
    assert status["target_registered"] is True
    assert status["service_ip"] == "192.0.2.25"
    assert status["group_name"] == "PROD"
    assert status["cluster_name"] == "GREEN"


def test_status_does_not_probe_ip_or_create_client(make_app, patched_create_client, monkeypatch):
    import flask_nacos.naming as naming_module

    app = make_app({"NACOS_SERVICE_IP": None})
    nacos = FlaskNacos(app)

    def unexpected_probe():
        raise AssertionError("status must not probe an IP")

    monkeypatch.setattr(naming_module, "get_local_ip", unexpected_probe)
    assert nacos.get_status(app)["service_ip"] is None
    assert patched_create_client["count"] == 0


def test_get_status_disabled_is_fixed(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False})
    nacos = FlaskNacos(app)

    status = nacos.get_status(app)
    assert set(status) == EXPECTED_KEYS
    assert status["enabled"] is False
    assert status["client_created"] is False
    assert status["target_registered"] is False
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] is None
    assert patched_create_client["count"] == 0


def test_get_status_excludes_secrets(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_ACCESS_KEY": "AK-1234567890",
            "NACOS_SECRET_KEY": "SK-abcdefghij",
        }
    )
    nacos = FlaskNacos(app)

    status = nacos.get_status(app)
    values = "".join(str(value) for value in status.values())
    assert "AK-1234567890" not in values
    assert "SK-abcdefghij" not in values
