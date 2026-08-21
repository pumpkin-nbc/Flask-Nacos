"""Regression tests for strict per-application state selection."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import flask_nacos.client as client_module
import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError
from tests.helpers import wait_registered


def _client():
    client = MagicMock()
    client.add_naming_instance.return_value = True
    client.remove_naming_instance.return_value = True
    return client


def test_no_recent_application_fallback(make_app, patched_create_client):
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    with pytest.raises(FlaskNacosError, match="context"):
        nacos.get_status()
    assert nacos.get_status(app_a)["service_name"] == "service-a"
    assert nacos.get_status(app_b)["service_name"] == "service-b"

    with app_a.app_context():
        assert nacos.app is app_a
        assert nacos.config["NACOS_SERVICE_NAME"] == "service-a"
    with app_b.app_context():
        assert nacos.app is app_b
        assert nacos.config["NACOS_SERVICE_NAME"] == "service-b"


def test_two_app_health_routes_are_isolated(make_app, patched_create_client):
    app_a = make_app(
        {
            "NACOS_SERVICE_NAME": "service-a",
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    app_b = make_app(
        {
            "NACOS_SERVICE_NAME": "service-b",
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    assert app_a.test_client().get("/health/nacos").get_json()["enabled"] is True
    assert app_b.test_client().get("/health/nacos").get_json()["enabled"] is True
    assert nacos.get_status(app_a)["service_name"] == "service-a"
    assert nacos.get_status(app_b)["service_name"] == "service-b"


def test_init_inside_other_context_uses_explicit_target(make_app, patched_create_client):
    app_a = make_app({"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/health/a"})
    app_b = make_app({"NACOS_HEALTH_CHECK_ENABLED": True, "NACOS_HEALTH_CHECK_PATH": "/health/b"})
    nacos = FlaskNacos(app_a)

    with app_a.app_context():
        nacos.init_app(app_b)

    assert app_a.test_client().get("/health/a").status_code == 200
    assert app_b.test_client().get("/health/b").status_code == 200
    assert app_b.test_client().get("/health/a").status_code == 404


def test_registration_and_clients_are_isolated(make_app, monkeypatch):
    client_a = _client()
    client_b = _client()
    clients = iter([client_a, client_b])
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: next(clients))
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    nacos.register_instance(app_a)
    wait_registered(nacos, app_a)
    assert nacos.get_status(app_a)["registered"] is True
    assert nacos.get_status(app_b)["registered"] is False
    assert app_a.extensions["nacos"]["_runtime"].client is client_a
    assert app_b.extensions["nacos"]["_runtime"].client is None

    assert nacos.get_client(app_b) is client_b


def test_heartbeat_observability_state_is_isolated_between_apps(make_app, monkeypatch):
    app_a_failing = [True]

    def app_a_heartbeat(*_args, **_kwargs):
        if app_a_failing[0]:
            raise RuntimeError("private")
        return "a-ok"

    client_a = SimpleNamespace(send_heartbeat=app_a_heartbeat)
    client_b = SimpleNamespace(send_heartbeat=lambda *_a, **_k: "b-ok")
    client_module._install_heartbeat_logging(client_a)
    client_module._install_heartbeat_logging(client_b)
    clients = iter([client_a, client_b])
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: next(clients))
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)
    sdk_a = nacos.get_client(app_a)
    sdk_b = nacos.get_client(app_b)
    args = ("shared-name", "10.0.0.8", 8080)

    with pytest.raises(RuntimeError):
        sdk_a.send_heartbeat(*args)
    assert sdk_b.send_heartbeat(*args) == "b-ok"
    safe_logger.info.assert_not_called()

    app_a_failing[0] = False
    assert sdk_a.send_heartbeat(*args) == "a-ok"
    safe_logger.info.assert_called_once()


def test_extension_slot_collision_and_owner_mismatch_are_explicit(make_app, patched_create_client):
    app = make_app()
    owner = FlaskNacos(app)

    with pytest.raises(FlaskNacosError, match="already owned"):
        FlaskNacos(app)

    other = FlaskNacos()
    with pytest.raises(FlaskNacosError, match="not owned"):
        other.get_status(app)
    assert owner.get_status(app)["enabled"] is True


def test_uninitialized_current_app_does_not_use_another_app(make_app, patched_create_client):
    configured = make_app({"NACOS_SERVICE_NAME": "configured"})
    foreign = make_app({"NACOS_SERVICE_NAME": "foreign"})
    nacos = FlaskNacos(configured)

    with foreign.app_context(), pytest.raises(FlaskNacosError, match="not initialized"):
        nacos.register_instance()


def test_atexit_installation_and_cleanup_are_isolated_per_app(make_app, monkeypatch):
    callbacks = []
    client_a = _client()
    client_b = _client()
    clients = iter([client_a, client_b])
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: next(clients))
    monkeypatch.setattr(
        extension_module,
        "atexit",
        SimpleNamespace(register=callbacks.append),
    )

    app_a = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    app_b = make_app({"NACOS_DEREGISTER_ON_EXIT": False})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)
    nacos.register_instance(app_a)
    nacos.register_instance(app_b)
    wait_registered(nacos, app_a)
    wait_registered(nacos, app_b)

    assert len(callbacks) == 1
    callbacks[0]()
    client_b.remove_naming_instance.assert_not_called()
    client_a.remove_naming_instance.assert_called_once()
