"""Tests for the optional Flask health-check route."""

from flask_nacos import FlaskNacos
from flask_nacos.health import HEALTH_ENDPOINT
from tests.helpers import wait_registered, wait_until


def test_health_route_registered_when_enabled(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True})
    FlaskNacos(app)

    assert HEALTH_ENDPOINT in app.view_functions
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/health/nacos" in paths


def test_health_route_not_registered_when_disabled(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": False})
    FlaskNacos(app)

    assert HEALTH_ENDPOINT not in app.view_functions


def test_health_custom_path(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/healthz"})
    FlaskNacos(app)

    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/healthz" in paths


def test_health_endpoint_returns_ok(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_HEALTH_CHECK_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_SERVICE_NAME": "fund-service",
            "NACOS_SERVICE_PORT": 5000,
        }
    )
    nacos = FlaskNacos(app)
    wait_registered(nacos, app)

    resp = app.test_client().get("/health/nacos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert set(data) == {
        "status",
        "enabled",
        "client_created",
        "target_registered",
        "registered",
        "operation_running",
        "last_error",
    }
    assert data["enabled"] is True
    assert data["client_created"] is True
    assert data["target_registered"] is True
    assert data["registered"] is True


def test_health_endpoint_disabled_status(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False, "NACOS_HEALTH_CHECK_ENABLED": True})
    FlaskNacos(app)

    resp = app.test_client().get("/health/nacos")
    data = resp.get_json()
    assert data["status"] == "disabled"
    assert data["enabled"] is False
    assert data["client_created"] is False
    assert data["target_registered"] is False


def test_health_endpoint_error_status_for_runtime_registration_failure(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.return_value = False
    app = make_app(
        {
            "NACOS_HEALTH_CHECK_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_RETRY_ENABLED": False,
        }
    )
    nacos = FlaskNacos(app)
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)

    resp = app.test_client().get("/health/nacos")
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["enabled"] is True
    assert data["client_created"] is True
    assert data["target_registered"] is True
    assert data["last_error"] == "NacosRegistrationError"


def test_heartbeat_failure_does_not_change_health_contract(
    make_app, patched_create_client
):
    app = make_app(
        {
            "NACOS_HEALTH_CHECK_ENABLED": True,
            "NACOS_AUTO_REGISTER": True,
        }
    )
    nacos = FlaskNacos(app)
    wait_registered(nacos, app)
    runtime = app.extensions["nacos"]["_runtime"]
    with runtime.state_lock:
        runtime.heartbeat_state = "failing"
        runtime.last_heartbeat_failure_at = 123.0
        runtime.heartbeat_error_type = "ConnectionError"

    data = app.test_client().get("/health/nacos").get_json()

    assert data["status"] == "ok"
    assert len(data) == 7
    assert "heartbeat_state" not in data
    assert nacos.get_status(app)["heartbeat_state"] == "failing"


def test_repeated_init_app_does_not_double_register(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True})
    nacos = FlaskNacos()
    nacos.init_app(app)
    # Second init_app on the same app must not raise or duplicate the route.
    nacos.init_app(app)

    rules = [r for r in app.url_map.iter_rules() if r.endpoint == HEALTH_ENDPOINT]
    assert len(rules) == 1


def test_preexisting_route_does_not_raise(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True})

    @app.route("/health/nacos")
    def existing():
        return "already here"

    # Should skip registration gracefully rather than raise.
    FlaskNacos(app)

    resp = app.test_client().get("/health/nacos")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "already here"
