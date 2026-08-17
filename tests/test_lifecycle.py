"""Tests for per-process registration lifecycle and atexit control."""

import flask_nacos.extension as extension_module
import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered


def test_repeated_register_same_process_registers_once(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is None
    wait_registered(nacos)
    assert nacos.register_instance() is None
    assert nacos.register_instance() is None
    fake_client.add_naming_instance.assert_called_once()


def test_register_records_pid(make_app, patched_create_client, monkeypatch):
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 4321)
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    nacos.register_instance()
    wait_registered(nacos)
    assert nacos._registered_pid == 4321


def test_pid_change_allows_reregister(make_app, patched_create_client, fake_client, monkeypatch):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])

    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is None  # pid 100, first register
    wait_registered(nacos)
    pid[0] = 200
    assert nacos.register_instance() is None  # pid 200, fresh child state
    wait_registered(nacos)
    assert fake_client.add_naming_instance.call_count == 2


def test_registration_is_always_idempotent_per_process(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {"NACOS_AUTO_REGISTER": False}
    )
    nacos = FlaskNacos(app)

    nacos.register_instance()
    wait_registered(nacos)
    nacos.register_instance()
    assert fake_client.add_naming_instance.call_count == 1


def test_deregister_fresh_instance_no_error(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_not_called()


def test_forked_child_does_not_deregister_parent_instance(
    make_app, patched_create_client, fake_client, monkeypatch
):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])

    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is None  # registered in pid 100
    wait_registered(nacos)
    pid[0] = 200
    # The child resets inherited ownership and treats deregistration as a no-op.
    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_not_called()


def test_atexit_registered_when_deregister_on_exit_true(
    make_app, patched_create_client, monkeypatch
):
    registered = []
    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )
    app = make_app({"NACOS_AUTO_DEREGISTER": True, "NACOS_DEREGISTER_ON_EXIT": True})
    FlaskNacos(app)

    assert len(registered) == 1


def test_atexit_not_registered_when_deregister_on_exit_false(
    make_app, patched_create_client, monkeypatch
):
    registered = []
    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )
    app = make_app({"NACOS_AUTO_DEREGISTER": True, "NACOS_DEREGISTER_ON_EXIT": False})
    FlaskNacos(app)

    assert registered == []


def test_repeated_init_app_does_not_double_register_atexit(
    make_app, patched_create_client, monkeypatch
):
    registered = []
    monkeypatch.setattr(
        extension_module.atexit, "register", lambda fn: registered.append(fn)
    )
    app = make_app({"NACOS_AUTO_DEREGISTER": True, "NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos()
    nacos.init_app(app)
    nacos.init_app(app)

    assert len(registered) == 1


def test_atexit_skips_deregister_when_extension_never_registered(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    nacos._atexit_handler()

    fake_client.remove_naming_instance.assert_not_called()


def test_atexit_deregisters_instance_registered_by_extension(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    nacos.register_instance()
    wait_registered(nacos)

    nacos._atexit_handler()

    fake_client.remove_naming_instance.assert_called_once()
    assert nacos.get_status()["registered"] is False
