"""Tests for service instance normalization."""

from flask_nacos import FlaskNacos
from flask_nacos.discovery import normalize_instance


class _ObjInstance:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_normalize_dict_instance(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    result = nacos.normalize_instance(
        {
            "ip": "10.0.0.1",
            "port": 8080,
            "serviceName": "user-service",
            "clusterName": "DEFAULT",
            "weight": 2.0,
            "healthy": True,
            "enabled": True,
            "ephemeral": True,
            "metadata": {"version": "v1"},
        }
    )
    assert result == {
        "ip": "10.0.0.1",
        "port": 8080,
        "service_name": "user-service",
        "cluster_name": "DEFAULT",
        "weight": 2.0,
        "healthy": True,
        "enabled": True,
        "ephemeral": True,
        "metadata": {"version": "v1"},
    }


def test_normalize_object_instance():
    instance = _ObjInstance(
        ip="10.0.0.2",
        port=9000,
        serviceName="order-service",
        clusterName="CANARY",
        weight=3.0,
        healthy=False,
        metadata={"zone": "east"},
    )
    result = normalize_instance(instance)
    assert result["ip"] == "10.0.0.2"
    assert result["port"] == 9000
    assert result["service_name"] == "order-service"
    assert result["cluster_name"] == "CANARY"
    assert result["weight"] == 3.0
    assert result["healthy"] is False
    assert result["metadata"] == {"zone": "east"}


def test_normalize_missing_fields_defaults():
    result = normalize_instance({"ip": "10.0.0.3", "port": 7000})
    assert result["ip"] == "10.0.0.3"
    assert result["port"] == 7000
    assert result["service_name"] is None
    assert result["cluster_name"] == "DEFAULT"
    assert result["weight"] == 1.0
    assert result["healthy"] is True
    assert result["enabled"] is True
    assert result["ephemeral"] is True
    assert result["metadata"] == {}


def test_normalize_failure_returns_none(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.normalize_instance(None) is None


def test_bad_instance_skipped_without_failing_discovery(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = {
        "hosts": [
            {"ip": "127.0.0.1", "port": 8000, "healthy": True},
            None,  # malformed instance -> should be skipped
            {"ip": "127.0.0.1", "port": 8001, "healthy": True},
        ]
    }
    app = make_app()
    nacos = FlaskNacos(app)

    result = nacos.list_instances("user-service")
    assert len(result) == 2
    assert {r["port"] for r in result} == {8000, 8001}
