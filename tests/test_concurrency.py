"""Concurrency and post-fork lifecycle regression tests."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered, wait_until


def _run_together(operation):
    barrier = Barrier(2)

    def invoke():
        barrier.wait()
        return operation()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(lambda _: invoke(), range(2)))


def _submit_together(executor, count, operation):
    barrier = Barrier(count)

    def invoke():
        barrier.wait()
        return operation()

    return [executor.submit(invoke) for _ in range(count)]


def test_concurrent_registration_calls_sdk_once(make_app, patched_create_client, fake_client):
    def delayed_success(*args, **kwargs):
        time.sleep(0.02)
        return True

    fake_client.add_naming_instance.side_effect = delayed_success
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert _run_together(lambda: nacos.register_instance(app)) == [None, None]
    wait_registered(nacos, app)
    fake_client.add_naming_instance.assert_called_once()


def test_concurrent_deregistration_calls_sdk_once(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    def delayed_success(*args, **kwargs):
        time.sleep(0.02)
        return True

    fake_client.remove_naming_instance.side_effect = delayed_success

    assert _run_together(lambda: nacos.deregister_instance(app)) == [True, True]
    fake_client.remove_naming_instance.assert_called_once()


def test_one_hundred_concurrent_deregistrations_share_one_rpc(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)
    entered = Event()
    release = Event()

    def blocked_success(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.remove_naming_instance.side_effect = blocked_success
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = _submit_together(
            executor, 100, lambda: nacos.deregister_instance(app)
        )
        assert entered.wait(1.0)
        wait_until(lambda: sum(future.done() for future in futures) >= 99)
        release.set()
        results = [future.result(timeout=2.0) for future in futures]

    assert results == [True] * 100
    assert fake_client.remove_naming_instance.call_count == 1
    assert nacos.get_status(app)["registered"] is False


def test_status_remains_available_while_naming_rpc_is_blocked(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    entered = Event()
    release = Event()

    def blocked_success(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_success
    nacos.register_instance(app)
    assert entered.wait(1.0)

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            status = executor.submit(nacos.get_status, app).result(timeout=0.5)
        assert status["operation_running"] is True
        assert status["target_registered"] is True
        assert status["registered"] is False
    finally:
        release.set()

    wait_registered(nacos, app)


def test_pid_change_replaces_inherited_lock(
    make_app, patched_create_client, fake_client, monkeypatch
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    inherited_state_lock = runtime.state_lock
    inherited_client_lock = runtime.client_lock
    inherited_network_lock = runtime.network_operation_lock
    inherited_wakeup = runtime.operation_wakeup
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 424242)

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = _submit_together(executor, 100, lambda: nacos.register_instance(app))
        assert [future.result(timeout=2.0) for future in futures] == [None] * 100
    current_runtime = app.extensions["nacos"]["_runtime"]
    wait_registered(nacos, app)

    assert current_runtime.pid == 424242
    assert current_runtime is not runtime
    assert current_runtime.state_lock is not inherited_state_lock
    assert current_runtime.client_lock is not inherited_client_lock
    assert current_runtime.network_operation_lock is not inherited_network_lock
    assert current_runtime.operation_wakeup is not inherited_wakeup
    assert fake_client.add_naming_instance.call_count == 1
