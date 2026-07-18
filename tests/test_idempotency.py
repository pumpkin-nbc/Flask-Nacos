"""Tests for idempotent registration and deregistration."""

from flask_nacos import FlaskNacos


def test_repeated_register_calls_client_once(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True
    assert nacos.register_instance() is True
    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()


def test_auto_register_then_manual_register_no_duplicate(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos(app)

    # Auto-registered once during init_app; manual call should be a no-op.
    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()


def test_deregister_on_fresh_instance_no_error(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    # Never registered; deregister must not raise.
    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_called_once()


def test_repeated_deregister_calls_client_once(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.deregister_instance() is True
    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_called_once()


def test_reregister_after_deregister(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True
    assert nacos.deregister_instance() is True
    assert nacos.register_instance() is True

    assert fake_client.add_naming_instance.call_count == 2
    assert fake_client.remove_naming_instance.call_count == 1
