"""Flask lifecycle and normalization compatibility tests."""

from flask_nacos import FlaskNacos
from flask_nacos.discovery import normalize_instance
from flask_nacos.health import HEALTH_ENDPOINT, register_health_route


class _ObjInstance:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_standard_mode_registers_extension(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    assert "nacos" in app.extensions
    assert nacos.config is not None


def test_factory_mode_registers_extension(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos()
    nacos.init_app(app)
    assert "nacos" in app.extensions
    assert nacos.config is not None


def test_repeated_init_app_does_not_raise(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos()
    nacos.init_app(app)
    nacos.init_app(app)
    assert "nacos" in app.extensions


def test_health_route_registers_when_enabled(make_app, patched_create_client):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True})
    FlaskNacos(app)
    assert HEALTH_ENDPOINT in app.view_functions


def test_health_route_repeat_registration_is_idempotent(
    make_app, patched_create_client
):
    app = make_app({"NACOS_HEALTH_CHECK_ENABLED": True})
    nacos = FlaskNacos(app)
    # A second explicit registration must not raise and must be skipped.
    assert register_health_route(app, nacos) is False


def test_normalize_camelcase_dict():
    result = normalize_instance(
        {
            "ip": "10.0.0.1",
            "port": 8080,
            "serviceName": "svc",
            "clusterName": "DEFAULT",
        }
    )
    assert result["service_name"] == "svc"
    assert result["cluster_name"] == "DEFAULT"


def test_normalize_snakecase_dict():
    result = normalize_instance(
        {
            "ip": "10.0.0.1",
            "port": 8080,
            "service_name": "svc",
            "cluster_name": "CANARY",
        }
    )
    assert result["service_name"] == "svc"
    assert result["cluster_name"] == "CANARY"


def test_normalize_camelcase_object():
    instance = _ObjInstance(ip="10.0.0.2", port=9000, serviceName="svc2")
    result = normalize_instance(instance)
    assert result["service_name"] == "svc2"


def test_normalize_snakecase_object():
    instance = _ObjInstance(ip="10.0.0.2", port=9000, service_name="svc3")
    result = normalize_instance(instance)
    assert result["service_name"] == "svc3"


def test_normalize_missing_fields_defaults():
    result = normalize_instance({"ip": "10.0.0.3", "port": 7000})
    assert result["service_name"] is None
    assert result["cluster_name"] == "DEFAULT"
    assert result["weight"] == 1.0
    assert result["healthy"] is True
    assert result["enabled"] is True
    assert result["ephemeral"] is True
    assert result["metadata"] == {}
