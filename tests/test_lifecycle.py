"""Tests for per-process registration lifecycle and atexit control."""

import flask_nacos.extension as extension_module
import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos


def test_repeated_register_same_process_registers_once(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True
    assert nacos.register_instance() is True
    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()


def test_register_records_pid(make_app, patched_create_client, monkeypatch):
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 4321)
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    nacos.register_instance()
    assert nacos._registered_pid == 4321


def test_pid_change_allows_reregister(make_app, patched_create_client, fake_client, monkeypatch):
    pids = iter([100, 200])
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: next(pids))

    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True  # pid 100, first register
    assert nacos.register_instance() is True  # pid 200, new process -> re-register
    assert fake_client.add_naming_instance.call_count == 2


def test_once_per_process_false_registers_each_time(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {"NACOS_AUTO_REGISTER": False, "NACOS_REGISTER_ONCE_PER_PROCESS": False}
    )
    nacos = FlaskNacos(app)

    nacos.register_instance()
    nacos.register_instance()
    assert fake_client.add_naming_instance.call_count == 2


def test_deregister_fresh_instance_no_error(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.deregister_instance() is True
    fake_client.remove_naming_instance.assert_called_once()


def test_deregister_skipped_on_pid_mismatch(
    make_app, patched_create_client, fake_client, monkeypatch
):
    pids = iter([100, 200])
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: next(pids))

    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True  # registered in pid 100
    # Now current pid is 200 -> mismatch -> skip, no client call.
    assert nacos.deregister_instance() is False
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
