"""Tests for service registration (auto and manual)."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosConfigError


def test_auto_register(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    FlaskNacos(app)

    fake_client.add_naming_instance.assert_called_once()
    args, kwargs = fake_client.add_naming_instance.call_args
    assert args[0] == "test-service"
    assert args[1] == "127.0.0.1"
    assert args[2] == 8000
    assert kwargs["group_name"] == "DEFAULT_GROUP"


def test_manual_register(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    fake_client.add_naming_instance.assert_not_called()
    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()


def test_register_uses_configured_values(make_app, patched_create_client, fake_client):
    app = make_app(
        {
            "NACOS_SERVICE_WEIGHT": 3.0,
            "NACOS_SERVICE_CLUSTER": "C1",
            "NACOS_SERVICE_METADATA": {"env": "test"},
            "NACOS_SERVICE_GROUP": "G1",
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance()

    _, kwargs = fake_client.add_naming_instance.call_args
    assert kwargs["weight"] == 3.0
    assert kwargs["cluster_name"] == "C1"
    assert kwargs["metadata"] == {"env": "test"}
    assert kwargs["group_name"] == "G1"


def test_missing_port_fails_fast(make_app, patched_create_client):
    app = make_app(
        {"NACOS_SERVICE_PORT": None, "NACOS_AUTO_REGISTER": False, "NACOS_FAIL_FAST": True}
    )
    nacos = FlaskNacos(app)

    with pytest.raises(NacosConfigError):
        nacos.register_instance()


def test_auto_detect_ip_when_unset(make_app, patched_create_client, fake_client, monkeypatch):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: "192.168.1.50")
    app = make_app({"NACOS_SERVICE_IP": None})
    nacos = FlaskNacos(app)
    nacos.register_instance()

    args, _ = fake_client.add_naming_instance.call_args
    assert args[1] == "192.168.1.50"
