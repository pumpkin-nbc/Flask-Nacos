"""Tests for the optional Flask health-check route."""

from flask_nacos import FlaskNacos
from flask_nacos.health import HEALTH_ENDPOINT


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
    app = make_app(
        {"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/healthz"}
    )
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
    FlaskNacos(app)

    resp = app.test_client().get("/health/nacos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["nacos_enabled"] is True
    assert data["client_initialized"] is True
    assert data["registered"] is True
    assert data["service_name"] == "fund-service"
    assert data["service_port"] == 5000


def test_health_endpoint_disabled_status(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False, "NACOS_HEALTH_CHECK_ENABLED": True})
    FlaskNacos(app)

    resp = app.test_client().get("/health/nacos")
    data = resp.get_json()
    assert data["status"] == "disabled"
    assert data["nacos_enabled"] is False
    assert data["client_initialized"] is False


def test_health_endpoint_error_status(make_app, monkeypatch):
    import flask_nacos.extension as extension_module

    def _failing_factory(config):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(extension_module, "create_client", _failing_factory)
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_FAIL_FAST": False})
    FlaskNacos(app)

    resp = app.test_client().get("/health/nacos")
    data = resp.get_json()
    assert data["status"] == "error"
    assert data["nacos_enabled"] is True
    assert data["client_initialized"] is False


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
