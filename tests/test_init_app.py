"""Tests for transactional, client-lazy extension initialization."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError
from flask_nacos.extension import EXTENSION_KEY


def test_direct_mode_stores_state_without_creating_client(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)

    state = app.extensions[EXTENSION_KEY]
    assert state["config"]["NACOS_SERVICE_NAME"] == "test-service"
    assert state["_runtime"].client is None
    assert patched_create_client["count"] == 0
    assert nacos.get_client(app) is fake_client
    assert patched_create_client["count"] == 1


def test_factory_mode_requires_context_for_properties(make_app, patched_create_client):
    nacos = FlaskNacos()
    with pytest.raises(FlaskNacosError, match="context"):
        _ = nacos.app

    app = make_app()
    nacos.init_app(app)
    with pytest.raises(FlaskNacosError, match="context"):
        _ = nacos.client

    with app.app_context():
        assert nacos.app is app
        assert nacos.client is None
        assert nacos.config["NACOS_SERVICE_NAME"] == "test-service"


def test_disabled_initialization_never_creates_client(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False})
    nacos = FlaskNacos(app)

    assert nacos.get_client(app) is None
    assert app.extensions[EXTENSION_KEY]["_runtime"].client is None
    assert patched_create_client["count"] == 0


def test_constructing_without_app_has_no_side_effects():
    nacos = FlaskNacos()
    assert isinstance(Flask(__name__), Flask)
    with pytest.raises(FlaskNacosError, match="context"):
        nacos.get_status()


def test_concurrent_initialization_commits_complete_isolated_states(
    make_app, patched_create_client
):
    nacos = FlaskNacos()
    apps = [
        make_app({"NACOS_SERVICE_NAME": "service-a"}),
        make_app({"NACOS_SERVICE_NAME": "service-b"}),
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(nacos.init_app, apps))

    assert patched_create_client["count"] == 0
    for app in apps:
        state = app.extensions[EXTENSION_KEY]
        assert state["_runtime"].client is None
        assert state["config"]["NACOS_SERVICE_NAME"] in {"service-a", "service-b"}


def test_repeated_init_is_idempotent(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    original_state = app.extensions[EXTENSION_KEY]

    nacos.init_app(app)

    assert app.extensions[EXTENSION_KEY] is original_state
    assert patched_create_client["count"] == 0
