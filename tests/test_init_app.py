"""Tests for extension initialization in both standard and factory modes."""

from concurrent.futures import ThreadPoolExecutor

from flask import Flask

from flask_nacos import FlaskNacos
from flask_nacos.extension import EXTENSION_KEY


def test_direct_mode_init(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    assert EXTENSION_KEY in app.extensions
    assert app.extensions[EXTENSION_KEY]["client"] is fake_client
    assert nacos.app is app
    assert nacos.client is fake_client
    assert nacos.get_client() is fake_client
    assert patched_create_client["count"] == 1


def test_factory_mode_init(make_app, patched_create_client, fake_client):
    nacos = FlaskNacos()
    assert nacos.app is None
    assert nacos.client is None

    app = make_app()
    nacos.init_app(app)

    assert app.extensions[EXTENSION_KEY]["client"] is fake_client
    assert nacos.client is fake_client


def test_state_stored_in_extensions(make_app, patched_create_client):
    app = make_app()
    FlaskNacos(app)

    state = app.extensions[EXTENSION_KEY]
    assert "client" in state
    assert "config" in state
    assert state["config"]["NACOS_SERVICE_NAME"] == "test-service"


def test_disabled_does_not_create_client(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False})
    nacos = FlaskNacos(app)

    assert nacos.client is None
    assert app.extensions[EXTENSION_KEY]["client"] is None
    assert patched_create_client["count"] == 0


def test_no_real_connection_on_import():
    # Importing and constructing without an app must not create a client.
    nacos = FlaskNacos()
    assert nacos.client is None
    assert isinstance(Flask(__name__), Flask)


def test_concurrent_initialization_commits_complete_state(
    make_app, patched_create_client
):
    nacos = FlaskNacos()
    apps = [
        make_app({"NACOS_SERVICE_NAME": "service-a"}),
        make_app({"NACOS_SERVICE_NAME": "service-b"}),
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(nacos.init_app, apps))

    assert patched_create_client["count"] == 2
    for app in apps:
        state = app.extensions[EXTENSION_KEY]
        assert state["client"] is not None
        assert state["config"]["NACOS_SERVICE_NAME"] in {"service-a", "service-b"}
