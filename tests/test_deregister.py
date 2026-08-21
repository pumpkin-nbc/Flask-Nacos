"""Tests for service deregistration (auto via atexit and manual)."""

from types import SimpleNamespace

import pytest

from flask_nacos import FlaskNacos
from tests.helpers import wait_registered


@pytest.mark.parametrize("deregister_on_exit", [True, False])
def test_manual_deregister_is_independent_of_exit_setting(
    make_app, patched_create_client, fake_client, deregister_on_exit
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_DEREGISTER_ON_EXIT": deregister_on_exit,
        }
    )
    nacos = FlaskNacos(app)
    wait_registered(nacos, app)

    assert nacos.deregister_instance(app) is True
    fake_client.remove_naming_instance.assert_called_once()
    args, kwargs = fake_client.remove_naming_instance.call_args
    assert args[0] == "test-service"
    assert args[1] == "127.0.0.1"
    assert args[2] == 8000
    assert kwargs["group_name"] == "DEFAULT_GROUP"


def test_deregister_on_exit_registers_atexit(make_app, patched_create_client, monkeypatch):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module,
        "atexit",
        SimpleNamespace(register=lambda fn: registered.append(fn)),
    )

    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    FlaskNacos(app)

    assert len(registered) == 1
    assert app.extensions["nacos"]["_atexit_registered"] is True


def test_atexit_callback_deregisters(make_app, patched_create_client, fake_client, monkeypatch):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module,
        "atexit",
        SimpleNamespace(register=lambda fn: registered.append(fn)),
    )

    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    registered[0]()
    fake_client.remove_naming_instance.assert_called_once()


def test_atexit_is_not_installed_when_remote_cleanup_is_disabled(
    make_app, patched_create_client, monkeypatch
):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module,
        "atexit",
        SimpleNamespace(register=lambda fn: registered.append(fn)),
    )

    app = make_app({"NACOS_DEREGISTER_ON_EXIT": False})
    FlaskNacos(app)

    assert registered == []
    assert app.extensions["nacos"]["_atexit_registered"] is False
