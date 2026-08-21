"""Tests for PID Runtime rebuilding and process-exit lifecycle behavior."""

import gc
import threading
import weakref
from types import SimpleNamespace

import pytest

import flask_nacos.extension as extension_module
import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered, wait_until


def test_pid_change_rebuilds_all_process_local_resources_once(
    make_app, patched_create_client, monkeypatch
):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])
    app = make_app()
    nacos = FlaskNacos(app)
    parent = app.extensions["nacos"]["_runtime"]
    nacos.get_client(app)
    parent.registered = True
    parent.registered_identity = {"service_name": "parent"}
    parent.last_error = "ParentError"

    pid[0] = 200
    first = nacos.get_status(app)
    child = app.extensions["nacos"]["_runtime"]
    second = nacos.get_status(app)

    assert child is not parent
    assert app.extensions["nacos"]["_runtime"] is child
    assert first["pid"] == second["pid"] == 200
    assert child.client is None
    assert child.registered is False
    assert child.registered_identity is None
    assert child.last_error is None
    assert child.state_lock is not parent.state_lock
    assert child.client_lock is not parent.client_lock
    assert child.network_operation_lock is not parent.network_operation_lock
    assert child.operation_wakeup is not parent.operation_wakeup
    assert child.auto_register_pending is False


def test_fork_auto_register_pending_is_not_consumed_by_status_health_or_client_property(
    make_app, patched_create_client, fake_client, monkeypatch
):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )

    @app.route("/business")
    def business():
        return "ok"

    nacos = FlaskNacos(app)
    wait_registered(nacos, app)
    assert patched_create_client["count"] == 1

    pid[0] = 200
    assert nacos.get_status(app)["client_created"] is False
    child = app.extensions["nacos"]["_runtime"]
    assert child.auto_register_pending is True
    with app.app_context():
        assert nacos.client is None
    assert child.auto_register_pending is True

    app.test_client().get("/health/nacos")
    assert child.auto_register_pending is True
    assert patched_create_client["count"] == 1

    app.test_client().get("/business")
    wait_registered(nacos, app)
    assert child.auto_register_pending is False
    assert patched_create_client["count"] == 2
    assert fake_client.add_naming_instance.call_count == 2


def test_public_get_client_atomically_consumes_fork_pending(
    make_app, patched_create_client, monkeypatch
):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos(app)
    wait_registered(nacos, app)

    pid[0] = 200
    assert nacos.get_client(app) is not None
    child = app.extensions["nacos"]["_runtime"]
    assert child.auto_register_pending is False
    wait_registered(nacos, app)
    assert patched_create_client["count"] == 2


def test_fork_preserves_non_fail_fast_registration_config_error(
    make_app, patched_create_client, monkeypatch
):
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_AUTO_REGISTER": True,
            "NACOS_FAIL_FAST": False,
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    nacos = FlaskNacos(app)

    pid[0] = 200
    status = nacos.get_status(app)
    child = app.extensions["nacos"]["_runtime"]
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["last_error"] == "NacosValidationError"
    assert child.auto_register_pending is False
    assert app.test_client().get("/health/nacos").get_json()["status"] == "error"
    assert patched_create_client["count"] == 0


def test_atexit_callback_is_installed_once_when_enabled(
    make_app, patched_create_client, monkeypatch
):
    callbacks = []
    monkeypatch.setattr(
        extension_module,
        "atexit",
        SimpleNamespace(register=callbacks.append),
    )
    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    nacos.init_app(app)
    assert len(callbacks) == 1


def test_deregister_on_exit_uses_cached_identity(
    make_app, patched_create_client, fake_client, monkeypatch
):
    import flask_nacos.naming as naming_module

    monkeypatch.setattr(naming_module, "get_local_ip", lambda: "192.0.2.80")
    app = make_app({"NACOS_SERVICE_IP": None, "NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    nacos._atexit_handler(app)

    args, _ = fake_client.remove_naming_instance.call_args
    assert args[:3] == ("test-service", "192.0.2.80", 8000)
    runtime = app.extensions["nacos"]["_runtime"]
    assert runtime.registered is False
    assert runtime.registered_identity is None


def test_exit_waits_for_the_specific_active_rpc_then_deregisters(
    make_app, patched_create_client, fake_client
):
    entered = threading.Event()
    release = threading.Event()

    def blocked_register(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_register
    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    assert entered.wait(1.0)
    runtime = app.extensions["nacos"]["_runtime"]
    active_done = runtime.naming_rpc_done

    cleanup = threading.Thread(target=nacos._atexit_handler, args=(app,))
    cleanup.start()
    wait_until(lambda: runtime.shutting_down)
    assert cleanup.is_alive()
    release.set()
    cleanup.join(2.0)

    assert not cleanup.is_alive()
    assert active_done.is_set()
    fake_client.remove_naming_instance.assert_called_once()
    assert runtime.registered is False


def test_fork_callback_does_not_retain_application(make_app, patched_create_client, monkeypatch):
    callbacks = []
    monkeypatch.setattr(
        extension_module.os,
        "register_at_fork",
        lambda **kwargs: callbacks.append(kwargs["after_in_child"]),
        raising=False,
    )
    app = make_app()
    app_ref = weakref.ref(app)
    FlaskNacos(app)
    assert len(callbacks) == 1

    del app
    gc.collect()
    assert app_ref() is None
    callbacks[0]()


def test_live_fork_callback_marks_stale_and_rebuilds_once(
    make_app, patched_create_client, monkeypatch
):
    callbacks = []
    pid = [100]
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: pid[0])
    monkeypatch.setattr(
        extension_module.os,
        "register_at_fork",
        lambda **kwargs: callbacks.append(kwargs["after_in_child"]),
        raising=False,
    )
    app = make_app()
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    parent = state["_runtime"]
    old_rebuild_lock = state["_runtime_rebuild_lock"]

    pid[0] = 200
    callbacks[0]()
    assert state["_runtime_stale"] is True
    assert state["_runtime_rebuild_lock"] is not old_rebuild_lock

    runtime_ids = []
    with_threads = [
        threading.Thread(target=lambda: runtime_ids.append(id(nacos._require_state(app)[2])))
        for _ in range(50)
    ]
    for thread in with_threads:
        thread.start()
    for thread in with_threads:
        thread.join(2.0)

    assert len(set(runtime_ids)) == 1
    assert state["_runtime"] is not parent
    assert state["_runtime_stale"] is False


def test_exit_handles_incomplete_rpc_metadata_and_missing_identity(
    make_app, patched_create_client, fake_client, monkeypatch
):
    warnings = []
    monkeypatch.setattr(
        extension_module.logger,
        "warning",
        lambda message, *_args: warnings.append(message),
    )
    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    runtime.client = fake_client
    runtime.registered = True
    runtime.target_registered = True
    runtime.registered_identity = None
    runtime.naming_rpc_active = True
    runtime.naming_rpc_done = None

    nacos._atexit_handler(app)
    assert runtime.shutting_down is True
    fake_client.remove_naming_instance.assert_not_called()
    assert any("incomplete Naming RPC metadata" in message for message in warnings)

    runtime.shutting_down = False
    runtime.naming_rpc_active = False
    warnings.clear()
    nacos._atexit_handler(app)
    assert runtime.registered is True
    fake_client.remove_naming_instance.assert_not_called()
    assert any("registered identity is missing" in message for message in warnings)


@pytest.mark.parametrize(
    ("rpc_timeout", "started_at", "expected_wait"),
    [
        (None, None, 3.25),
        (4.0, 98.0, 2.25),
        (10.0, 100.0, 5.0),
    ],
)
def test_exit_wait_timeout_is_bounded_and_does_not_race_rpc(
    make_app,
    patched_create_client,
    fake_client,
    monkeypatch,
    rpc_timeout,
    started_at,
    expected_wait,
):
    app = make_app({"NACOS_DEREGISTER_ON_EXIT": True})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    waits = []
    warnings = []
    monkeypatch.setattr(
        extension_module.logger,
        "warning",
        lambda message, *_args: warnings.append(message),
    )

    class NeverDone:
        def wait(self, timeout):
            waits.append(timeout)
            return False

    runtime.client = fake_client
    runtime.registered = True
    runtime.target_registered = True
    runtime.registered_identity = {
        "service_name": "test-service",
        "ip": "127.0.0.1",
        "port": 8000,
        "cluster_name": "DEFAULT",
        "group_name": "DEFAULT_GROUP",
        "ephemeral": True,
    }
    runtime.naming_rpc_active = True
    runtime.naming_rpc_done = NeverDone()
    runtime.naming_rpc_started_at = started_at
    runtime.naming_rpc_timeout = rpc_timeout
    monkeypatch.setattr(extension_module.time, "monotonic", lambda: 100.0)

    nacos._atexit_handler(app)
    assert waits == [expected_wait]
    fake_client.remove_naming_instance.assert_not_called()
    assert any("timed out" in message for message in warnings)
