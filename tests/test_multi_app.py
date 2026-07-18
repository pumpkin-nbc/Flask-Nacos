"""Regression tests for per-application state selection and lifecycle."""

from unittest.mock import MagicMock

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError


def _client():
    client = MagicMock()
    client.add_naming_instance.return_value = True
    client.remove_naming_instance.return_value = True
    return client


def test_context_selects_app_state_and_outside_uses_latest(make_app, monkeypatch):
    client_a = _client()
    client_b = _client()
    clients = iter([client_a, client_b])
    monkeypatch.setattr(extension_module, "create_client", lambda config: next(clients))

    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    assert nacos.app is app_b
    assert nacos.client is client_b
    assert nacos.get_status()["service_name"] == "service-b"

    with app_a.app_context():
        assert nacos.app is app_a
        assert nacos.client is client_a
        assert nacos.config["NACOS_SERVICE_NAME"] == "service-a"
        assert nacos.get_status()["service_name"] == "service-a"


def test_two_app_health_routes_do_not_share_latest_state(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", lambda config: _client())
    app_a = make_app(
        {
            "NACOS_SERVICE_NAME": "service-a",
            "NACOS_SERVICE_PORT": 8001,
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    app_b = make_app(
        {
            "NACOS_SERVICE_NAME": "service-b",
            "NACOS_SERVICE_PORT": 8002,
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    health_a = app_a.test_client().get("/health/nacos").get_json()
    health_b = app_b.test_client().get("/health/nacos").get_json()

    assert health_a["service_name"] == "service-a"
    assert health_a["service_port"] == 8001
    assert health_b["service_name"] == "service-b"
    assert health_b["service_port"] == 8002


def test_init_inside_other_context_uses_target_health_config(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", lambda config: _client())
    app_a = make_app(
        {"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/health/a"}
    )
    app_b = make_app(
        {"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/health/b"}
    )
    nacos = FlaskNacos(app_a)

    with app_a.app_context():
        nacos.init_app(app_b)

    assert app_a.test_client().get("/health/a").status_code == 200
    assert app_b.test_client().get("/health/b").status_code == 200
    assert app_b.test_client().get("/health/a").status_code == 404


def test_registration_state_is_isolated_between_apps(make_app, monkeypatch):
    monkeypatch.setattr(extension_module, "create_client", lambda config: _client())
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    with app_a.app_context():
        assert nacos.register_instance() is True
        assert nacos.get_status()["registered"] is True
    with app_b.app_context():
        assert nacos.get_status()["registered"] is False


def test_repeated_init_reuses_client_and_registration(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos(app)

    nacos.init_app(app)

    assert patched_create_client["count"] == 1
    fake_client.add_naming_instance.assert_called_once()


def test_extension_slot_collision_is_explicit(make_app, patched_create_client):
    app = make_app()
    FlaskNacos(app)

    with pytest.raises(FlaskNacosError, match="already owned"):
        FlaskNacos(app)


def test_foreign_app_context_does_not_use_latest_state(
    make_app, patched_create_client
):
    configured = make_app({"NACOS_SERVICE_NAME": "configured"})
    foreign = make_app({"NACOS_SERVICE_NAME": "foreign"})
    nacos = FlaskNacos(configured)

    with foreign.app_context(), pytest.raises(FlaskNacosError, match="current Flask app"):
        nacos.register_instance()


def test_each_atexit_callback_only_deregisters_its_app(make_app, monkeypatch):
    callbacks = []
    client_a = _client()
    client_b = _client()
    clients = iter([client_a, client_b])
    monkeypatch.setattr(extension_module, "create_client", lambda config: next(clients))
    monkeypatch.setattr(extension_module.atexit, "register", callbacks.append)

    app_a = make_app({"NACOS_AUTO_DEREGISTER": True})
    app_b = make_app({"NACOS_AUTO_DEREGISTER": True})
    nacos = FlaskNacos(app_a)
    with app_a.app_context():
        nacos.register_instance()
    nacos.init_app(app_b)

    assert len(callbacks) == 2
    callbacks[1]()
    callbacks[0]()

    client_b.remove_naming_instance.assert_not_called()
    client_a.remove_naming_instance.assert_called_once()
