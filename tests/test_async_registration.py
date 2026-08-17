"""Tests for the non-blocking registration lifecycle introduced in 1.1.0."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import flask_nacos.extension as extension_module
import flask_nacos.lifecycle as lifecycle_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not reached before timeout")


def test_register_is_no_argument_non_blocking_command(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    nacos = FlaskNacos(make_app())

    started = time.monotonic()
    assert nacos.register_instance() is None
    assert time.monotonic() - started < 0.2
    assert entered.wait(1.0)
    assert nacos.get_status()["registration_in_progress"] is True

    with pytest.raises(TypeError):
        nacos.register_instance(False)

    release.set()
    _wait_until(lambda: nacos.get_status()["registered"] is True)
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)


def test_registered_process_is_idempotent_without_new_thread(
    make_app, patched_create_client, fake_client, monkeypatch
):
    nacos = FlaskNacos(make_app())
    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registered"] is True)

    def unexpected_thread(*args, **kwargs):
        raise AssertionError("no background thread should be created")

    monkeypatch.setattr(extension_module, "Thread", unexpected_thread)
    assert nacos.register_instance() is None
    fake_client.add_naming_instance.assert_called_once()


def test_concurrent_commands_schedule_one_registration(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    nacos = FlaskNacos(make_app())
    assert nacos.register_instance() is None
    assert entered.wait(1.0)

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(lambda _: nacos.register_instance(), range(100)))

    assert results == [None] * 100
    fake_client.add_naming_instance.assert_called_once()
    release.set()
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)


def test_failed_registration_requires_explicit_retry(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = [False, True]
    nacos = FlaskNacos(make_app({"NACOS_RETRY_ENABLED": False}))

    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    status = nacos.get_status()
    assert status["registered"] is False
    assert status["last_registration_error_type"] == "NacosRegistrationError"

    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registered"] is True)
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    assert nacos.get_status()["last_registration_error_type"] is None
    assert fake_client.add_naming_instance.call_count == 2


def test_background_exception_is_sanitized(
    make_app, patched_create_client, monkeypatch, caplog
):
    secret = "do-not-log-this-registration-secret"
    nacos = FlaskNacos(make_app({"NACOS_LOG_ENABLED": True}))

    def fail_registration(app, state, runtime):
        raise ValueError(secret)

    monkeypatch.setattr(nacos, "_register_instance_for", fail_registration)
    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)

    assert nacos.get_status()["last_registration_error_type"] == "ValueError"
    assert secret not in caplog.text


@pytest.mark.parametrize("fail_fast", [False, True])
def test_thread_start_failure_rolls_back_transient_state(
    make_app, patched_create_client, monkeypatch, fail_fast
):
    created = []

    class FailingThread:
        def __init__(self, *, target, args, name, daemon):
            created.append((target, args, name, daemon))

        def start(self):
            raise RuntimeError("thread unavailable")

    monkeypatch.setattr(extension_module, "Thread", FailingThread)
    nacos = FlaskNacos(make_app({"NACOS_FAIL_FAST": fail_fast}))

    if fail_fast:
        with pytest.raises(RuntimeError, match="thread unavailable"):
            nacos.register_instance()
    else:
        assert nacos.register_instance() is None

    status = nacos.get_status()
    assert status["registration_in_progress"] is False
    assert status["last_registration_error_type"] == "RuntimeError"
    assert created[0][2:] == ("flask-nacos-registration", True)


def test_auto_registration_thread_failure_keeps_committed_state(
    make_app, patched_create_client, monkeypatch
):
    class FailingThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise RuntimeError("thread unavailable")

    monkeypatch.setattr(extension_module, "Thread", FailingThread)
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_AUTO_REGISTER_ON_INIT": True,
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos()

    with pytest.raises(RuntimeError, match="thread unavailable"):
        nacos.init_app(app)

    assert app.extensions["nacos"]["client"] is not None
    assert nacos.get_status()["last_registration_error_type"] == "RuntimeError"


def test_explicit_init_time_registration_is_non_blocking(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_AUTO_REGISTER_ON_INIT": True,
        }
    )

    started = time.monotonic()
    nacos = FlaskNacos(app)
    assert time.monotonic() - started < 0.2
    assert entered.wait(1.0)
    assert nacos.get_status()["registration_in_progress"] is True

    release.set()
    _wait_until(lambda: nacos.get_status()["registered"] is True)


@pytest.mark.parametrize("fail_fast", [False, True])
def test_client_unavailable_follows_fail_fast_without_thread(
    make_app, monkeypatch, fail_fast
):
    def unexpected_thread(*args, **kwargs):
        raise AssertionError("no background thread should be created")

    monkeypatch.setattr(extension_module, "Thread", unexpected_thread)
    nacos = FlaskNacos(
        make_app({"NACOS_ENABLED": False, "NACOS_FAIL_FAST": fail_fast})
    )

    if fail_fast:
        with pytest.raises(FlaskNacosError, match="client is not available"):
            nacos.register_instance()
    else:
        assert nacos.register_instance() is None
        assert nacos.get_status()["last_registration_error_type"] == "ClientUnavailable"
    assert nacos.get_status()["registration_in_progress"] is False


def test_fork_resets_complete_local_lifecycle_state(
    make_app, patched_create_client, monkeypatch
):
    app = make_app()
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    inherited_lifecycle_lock = runtime.lifecycle_lock
    inherited_operation_lock = runtime.lock
    runtime.registered = True
    runtime.registered_pid = runtime.lifecycle_lock_pid
    runtime.registered_identity = {"service_name": "parent"}
    runtime.registration_in_progress = True
    runtime.last_registration_error_type = "ParentFailure"
    runtime.deregistration_requested = True
    runtime.registration_desired = True

    monkeypatch.setattr(lifecycle_module, "current_pid", lambda: 424242)
    status = nacos.get_status()
    nacos._process_lock(runtime, 424242)

    assert runtime.lifecycle_lock is not inherited_lifecycle_lock
    assert runtime.lock is not inherited_operation_lock
    assert runtime.lifecycle_lock_pid == 424242
    assert runtime.lock_pid == 424242
    assert status["registered"] is False
    assert status["registration_in_progress"] is False
    assert status["last_registration_error_type"] is None
    assert status["deregistration_requested"] is False
    assert runtime.registration_desired is False
    assert runtime.registered_identity is None


def test_lifecycle_state_is_isolated_between_apps(make_app, monkeypatch):
    clients = iter([object(), object()])
    monkeypatch.setattr(extension_module, "create_client", lambda config: next(clients))
    created = []

    class CapturedThread:
        def __init__(self, *, target, args, name, daemon):
            created.append(self)

        def start(self):
            return None

    monkeypatch.setattr(extension_module, "Thread", CapturedThread)
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    with app_a.app_context():
        nacos.register_instance()
    with app_b.app_context():
        assert nacos.get_status()["registration_in_progress"] is False
        nacos.register_instance()

    assert len(created) == 2
    with app_a.app_context():
        assert nacos.get_status()["registration_in_progress"] is True
    with app_b.app_context():
        assert nacos.get_status()["registration_in_progress"] is True


def test_register_then_deregister_runs_delayed_cleanup(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    nacos = FlaskNacos(make_app())
    nacos.register_instance()
    assert entered.wait(1.0)

    assert nacos.deregister_instance() is True
    assert nacos.get_status()["deregistration_requested"] is True
    release.set()

    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    _wait_until(lambda: nacos.get_status()["deregistration_requested"] is False)
    assert nacos.get_status()["registered"] is False
    fake_client.remove_naming_instance.assert_called_once()


def test_register_deregister_register_last_command_wins(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    nacos = FlaskNacos(make_app())
    nacos.register_instance()
    assert entered.wait(1.0)
    assert nacos.deregister_instance() is True
    assert nacos.register_instance() is None
    release.set()

    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    assert nacos.get_status()["registered"] is True
    assert nacos.get_status()["deregistration_requested"] is False
    fake_client.remove_naming_instance.assert_not_called()


def test_register_during_deregistration_is_automatically_reconciled(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(make_app())
    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registered"] is True)

    entered = Event()
    release = Event()

    def blocked_deregistration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.remove_naming_instance.side_effect = blocked_deregistration
    with ThreadPoolExecutor(max_workers=1) as executor:
        deregistration = executor.submit(nacos.deregister_instance)
        assert entered.wait(1.0)
        assert nacos.register_instance() is None
        assert nacos.get_status()["registration_in_progress"] is True
        release.set()
        assert deregistration.result(timeout=2.0) is True

    _wait_until(lambda: nacos.get_status()["registered"] is True)
    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    assert fake_client.add_naming_instance.call_count == 2
    fake_client.remove_naming_instance.assert_called_once()


def test_failed_deregistration_stays_pending_and_explicit_call_retries(
    make_app, patched_create_client, fake_client
):
    fake_client.remove_naming_instance.side_effect = [False, True]
    nacos = FlaskNacos(make_app({"NACOS_RETRY_ENABLED": False}))
    nacos.register_instance()
    _wait_until(lambda: nacos.get_status()["registered"] is True)

    assert nacos.deregister_instance() is False
    status = nacos.get_status()
    assert status["registered"] is True
    assert status["deregistration_requested"] is True
    assert status["last_registration_error_type"] == "NacosDeregistrationError"

    assert nacos.deregister_instance() is True
    assert nacos.get_status()["registered"] is False
    assert nacos.get_status()["deregistration_requested"] is False


def test_failed_delayed_deregistration_stays_pending_for_retry(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    fake_client.remove_naming_instance.side_effect = [False, True]
    nacos = FlaskNacos(make_app({"NACOS_RETRY_ENABLED": False}))
    nacos.register_instance()
    assert entered.wait(1.0)
    assert nacos.deregister_instance() is True
    release.set()

    _wait_until(lambda: nacos.get_status()["registration_in_progress"] is False)
    _wait_until(lambda: nacos.get_status()["deregistration_requested"] is True)
    assert nacos.get_status()["registered"] is True
    assert nacos.deregister_instance() is True
    assert nacos.get_status()["deregistration_requested"] is False


def test_atexit_waits_for_registration_and_cleans_up(
    make_app, patched_create_client, fake_client
):
    entered = Event()
    release = Event()

    def blocked_registration(*args, **kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked_registration
    nacos = FlaskNacos(make_app())
    nacos.register_instance()
    assert entered.wait(1.0)

    with ThreadPoolExecutor(max_workers=1) as executor:
        shutdown = executor.submit(nacos._atexit_handler)
        time.sleep(0.02)
        assert shutdown.done() is False
        release.set()
        shutdown.result(timeout=2.0)

    _wait_until(lambda: nacos.get_status()["registered"] is False)
    fake_client.remove_naming_instance.assert_called_once()


def test_status_is_local_and_has_no_thread_or_sdk_side_effect(
    make_app, patched_create_client, fake_client, monkeypatch
):
    def unexpected_thread(*args, **kwargs):
        raise AssertionError("get_status must not schedule registration")

    monkeypatch.setattr(extension_module, "Thread", unexpected_thread)
    nacos = FlaskNacos(make_app())
    fake_client.reset_mock()

    status = nacos.get_status()

    assert status["registration_in_progress"] is False
    assert status["deregistration_requested"] is False
    assert status["last_registration_error_type"] is None
    assert not any("Thread" in type(value).__name__ for value in status.values())
    assert not any("lock" in type(value).__name__.lower() for value in status.values())
    fake_client.assert_not_called()
