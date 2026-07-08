"""Tests for service deregistration (auto via atexit and manual)."""

from flask_nacos import FlaskNacos


def test_manual_deregister(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_called_once()
    args, kwargs = fake_client.remove_naming_instance.call_args
    assert args[0] == "test-service"
    assert args[1] == "127.0.0.1"
    assert args[2] == 8000
    assert kwargs["group_name"] == "DEFAULT_GROUP"


def test_auto_deregister_registers_atexit(make_app, patched_create_client, monkeypatch):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )

    app = make_app({"NACOS_AUTO_DEREGISTER": True})
    FlaskNacos(app)

    assert len(registered) == 1


def test_atexit_callback_deregisters(make_app, patched_create_client, fake_client, monkeypatch):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )

    app = make_app({"NACOS_AUTO_DEREGISTER": True})
    FlaskNacos(app)

    registered[0]()
    fake_client.remove_naming_instance.assert_called_once()


def test_no_atexit_when_disabled(make_app, patched_create_client, monkeypatch):
    registered = []

    import flask_nacos.extension as extension_module

    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )

    app = make_app({"NACOS_AUTO_DEREGISTER": False})
    FlaskNacos(app)

    assert registered == []
