"""Concurrency and post-fork lifecycle regression tests."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered


def _run_together(operation):
    barrier = Barrier(2)

    def invoke():
        barrier.wait()
        return operation()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(lambda _: invoke(), range(2)))


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


def test_pid_change_replaces_inherited_lock(make_app, patched_create_client, monkeypatch):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    inherited_state_lock = runtime.state_lock
    inherited_client_lock = runtime.client_lock
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 424242)

    assert nacos.register_instance(app) is None
    current_runtime = app.extensions["nacos"]["_runtime"]
    wait_registered(nacos, app)

    assert current_runtime.pid == 424242
    assert current_runtime is not runtime
    assert current_runtime.state_lock is not inherited_state_lock
    assert current_runtime.client_lock is not inherited_client_lock
