"""Concurrency and post-fork lifecycle regression tests."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos


def _run_together(operation):
    barrier = Barrier(2)

    def invoke():
        barrier.wait()
        return operation()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(lambda _: invoke(), range(2)))


def test_concurrent_registration_calls_sdk_once(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = lambda *args, **kwargs: time.sleep(
        0.02
    )
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)

    assert _run_together(nacos.register_instance) == [True, True]
    fake_client.add_naming_instance.assert_called_once()


def test_concurrent_deregistration_calls_sdk_once(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    nacos.register_instance()
    fake_client.remove_naming_instance.side_effect = lambda *args, **kwargs: time.sleep(
        0.02
    )

    assert _run_together(nacos.deregister_instance) == [True, True]
    fake_client.remove_naming_instance.assert_called_once()


def test_pid_change_replaces_inherited_lock(
    make_app, patched_create_client, monkeypatch
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    inherited_lock = runtime.lock
    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 424242)

    assert nacos.register_instance() is True

    assert runtime.lock_pid == 424242
    assert runtime.lock is not inherited_lock
