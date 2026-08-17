"""Tests for service registration (auto and manual)."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosConfigError
from tests.helpers import wait_registered


def test_auto_register(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": True, "NACOS_AUTO_REGISTER_ON_INIT": True})
    nacos = FlaskNacos(app)
    wait_registered(nacos, app)

    fake_client.add_naming_instance.assert_called_once()
    args, kwargs = fake_client.add_naming_instance.call_args
    assert args[0] == "test-service"
    assert args[1] == "127.0.0.1"
    assert args[2] == 8000
    assert kwargs["group_name"] == "DEFAULT_GROUP"
    assert kwargs["heartbeat_interval"] == 5.0


def test_manual_register(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    fake_client.add_naming_instance.assert_not_called()
    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()


def test_register_uses_configured_values(make_app, patched_create_client, fake_client):
    app = make_app(
        {
            "NACOS_SERVICE_WEIGHT": 3.0,
            "NACOS_SERVICE_CLUSTER": "C1",
            "NACOS_SERVICE_METADATA": {"env": "test"},
            "NACOS_SERVICE_GROUP": "G1",
            "NACOS_SERVICE_HEARTBEAT_INTERVAL": 2.5,
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    _, kwargs = fake_client.add_naming_instance.call_args
    assert kwargs["weight"] == 3.0
    assert kwargs["cluster_name"] == "C1"
    assert kwargs["metadata"] == {"env": "test"}
    assert kwargs["group_name"] == "G1"
    assert kwargs["heartbeat_interval"] == 2.5


def test_persistent_instance_does_not_send_heartbeat_interval(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False, "NACOS_SERVICE_EPHEMERAL": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    _, kwargs = fake_client.add_naming_instance.call_args
    assert kwargs["ephemeral"] is False
    assert "heartbeat_interval" not in kwargs


def test_persistent_instance_ignores_invalid_heartbeat_interval(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_SERVICE_EPHEMERAL": False,
            "NACOS_SERVICE_HEARTBEAT_INTERVAL": "not-used",
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    _, kwargs = fake_client.add_naming_instance.call_args
    assert "heartbeat_interval" not in kwargs


def test_deregister_reuses_the_exact_registered_identity(
    make_app, patched_create_client, fake_client, monkeypatch
):
    import flask_nacos.naming as naming_module

    addresses = iter(("192.0.2.10", "192.0.2.11"))
    monkeypatch.setattr(naming_module, "get_local_ip", lambda: next(addresses))
    app = make_app({"NACOS_SERVICE_IP": None, "NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    assert nacos.deregister_instance(app) is True

    register_args, register_kwargs = fake_client.add_naming_instance.call_args
    deregister_args, deregister_kwargs = fake_client.remove_naming_instance.call_args
    assert register_args[:3] == ("test-service", "192.0.2.10", 8000)
    assert deregister_args[:3] == register_args[:3]
    assert deregister_kwargs["group_name"] == register_kwargs["group_name"]
    assert deregister_kwargs["cluster_name"] == register_kwargs["cluster_name"]


def test_missing_port_fails_fast(make_app, patched_create_client):
    app = make_app(
        {"NACOS_SERVICE_PORT": None, "NACOS_AUTO_REGISTER": False, "NACOS_FAIL_FAST": True}
    )
    nacos = FlaskNacos(app)

    with pytest.raises(NacosConfigError):
        nacos.register_instance(app)


def test_auto_detect_ip_when_unset(make_app, patched_create_client, fake_client, monkeypatch):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: "192.168.1.50")
    app = make_app({"NACOS_SERVICE_IP": None, "NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    args, _ = fake_client.add_naming_instance.call_args
    assert args[1] == "192.168.1.50"


def test_no_auto_register_when_auto_register_false(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False, "NACOS_AUTO_REGISTER_ON_INIT": True})
    nacos = FlaskNacos(app)

    fake_client.add_naming_instance.assert_not_called()
    # Manual registration still works.
    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()


def test_no_auto_register_when_on_init_false(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": True, "NACOS_AUTO_REGISTER_ON_INIT": False})
    nacos = FlaskNacos(app)

    fake_client.add_naming_instance.assert_not_called()
    # Manual registration still works.
    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()


def test_auto_register_on_init_is_enabled_by_default(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos(app)

    with app.app_context():
        assert nacos.config["NACOS_AUTO_REGISTER_ON_INIT"] is True
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()
