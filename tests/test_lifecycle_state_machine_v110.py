"""Focused regression tests for the Flask-Nacos 1.1 lifecycle state machine."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError, NacosValidationError
from tests.helpers import wait_until

STATUS_KEYS = {
    "enabled",
    "pid",
    "client_created",
    "service_name",
    "group_name",
    "cluster_name",
    "service_ip",
    "service_port",
    "target_registered",
    "registered",
    "operation_running",
    "last_error",
    "heartbeat_state",
    "last_heartbeat_success_at",
    "last_heartbeat_failure_at",
    "heartbeat_error_type",
}


def _wait_settled(nacos, app, registered):
    wait_until(
        lambda: (
            nacos.get_status(app)["operation_running"] is False
            and nacos.get_status(app)["registered"] is registered
        )
    )


def test_public_state_requires_context_or_explicit_app(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    with pytest.raises(FlaskNacosError, match="context"):
        nacos.get_status()
    with pytest.raises(FlaskNacosError, match="context"):
        _ = nacos.client

    assert nacos.get_status(app)["service_name"] == "test-service"
    with app.app_context():
        assert nacos.app is app
        assert nacos.get_status()["service_name"] == "test-service"


def test_init_status_and_health_do_not_create_client(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    nacos = FlaskNacos(app)

    assert set(nacos.get_status(app)) == STATUS_KEYS
    assert nacos.get_status(app)["client_created"] is False
    assert patched_create_client["count"] == 0

    payload = app.test_client().get("/health/nacos").get_json()
    assert set(payload) == {
        "status",
        "enabled",
        "client_created",
        "target_registered",
        "registered",
        "operation_running",
        "last_error",
    }
    assert payload["status"] == "ok"
    assert patched_create_client["count"] == 0


def test_get_client_is_lazy_and_cached(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.get_status(app)["client_created"] is False
    assert nacos.get_client(app) is fake_client
    assert nacos.get_client(app) is fake_client
    assert patched_create_client["count"] == 1
    assert nacos.get_status(app)["client_created"] is True


def test_get_client_failure_is_safe_and_does_not_change_lifecycle(make_app, monkeypatch):
    app = make_app()
    nacos = FlaskNacos(app)

    def fail(_config):
        raise RuntimeError("secret-client-detail")

    monkeypatch.setattr(extension_module, "create_client", fail)
    with pytest.raises(FlaskNacosError, match="Failed to create Nacos client") as exc:
        nacos.get_client(app)

    assert isinstance(exc.value.__cause__, RuntimeError)
    status = nacos.get_status(app)
    assert status["target_registered"] is False
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] is None


def test_register_is_non_blocking_and_single_flight(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)
    entered = threading.Event()
    release = threading.Event()

    def blocked(*_args, **_kwargs):
        entered.set()
        assert release.wait(10.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(lambda _: nacos.register_instance(app), range(100)))

    assert results == [None] * 100
    assert time.monotonic() - started < 1.0
    assert entered.wait(1.0)
    assert nacos.get_status(app)["operation_running"] is True
    release.set()
    _wait_settled(nacos, app, True)
    assert fake_client.add_naming_instance.call_count == 1


def test_register_then_deregister_last_command_wins_before_rpc(
    make_app, patched_create_client, fake_client, monkeypatch
):
    app = make_app()
    nacos = FlaskNacos(app)
    original_worker = nacos._registration_worker
    entered = threading.Event()
    release = threading.Event()

    def delayed_worker(state, runtime):
        entered.set()
        assert release.wait(2.0)
        original_worker(state, runtime)

    monkeypatch.setattr(nacos, "_registration_worker", delayed_worker)
    nacos.register_instance(app)
    assert entered.wait(1.0)
    assert nacos.deregister_instance(app) is True
    release.set()
    _wait_settled(nacos, app, False)
    fake_client.add_naming_instance.assert_not_called()
    assert patched_create_client["count"] == 0


def test_register_deregister_register_last_command_wins_during_rpc(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    entered = threading.Event()
    release = threading.Event()

    def blocked(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked
    nacos.register_instance(app)
    assert entered.wait(1.0)
    assert nacos.deregister_instance(app) is True
    nacos.register_instance(app)
    release.set()

    _wait_settled(nacos, app, True)
    assert fake_client.add_naming_instance.call_count == 1
    fake_client.remove_naming_instance.assert_not_called()


def test_register_then_deregister_compensates_after_register_success(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    entered = threading.Event()
    release = threading.Event()

    def blocked(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.add_naming_instance.side_effect = blocked
    nacos.register_instance(app)
    assert entered.wait(1.0)
    assert nacos.deregister_instance(app) is True
    release.set()

    _wait_settled(nacos, app, False)
    fake_client.add_naming_instance.assert_called_once()
    fake_client.remove_naming_instance.assert_called_once()


@pytest.mark.parametrize("fail_fast", [False, True])
def test_thread_start_runtime_error_is_suppressed_and_retryable(
    make_app, patched_create_client, fake_client, monkeypatch, fail_fast
):
    app = make_app({"NACOS_FAIL_FAST": fail_fast})
    nacos = FlaskNacos(app)
    real_thread = extension_module.Thread

    class FailingThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("thread detail")

    monkeypatch.setattr(extension_module, "Thread", FailingThread)
    assert nacos.register_instance(app) is None
    status = nacos.get_status(app)
    assert status["target_registered"] is True
    assert status["operation_running"] is False
    assert status["last_error"] == "ThreadStartError"

    monkeypatch.setattr(extension_module, "Thread", real_thread)
    nacos.register_instance(app)
    _wait_settled(nacos, app, True)
    fake_client.add_naming_instance.assert_called_once()


def test_thread_construction_error_rolls_back_and_can_retry(
    make_app, patched_create_client, fake_client, monkeypatch
):
    app = make_app()
    nacos = FlaskNacos(app)
    real_thread = extension_module.Thread

    class BrokenThread:
        def __init__(self, **_kwargs):
            raise RuntimeError("cannot allocate thread")

    monkeypatch.setattr(extension_module, "Thread", BrokenThread)
    assert nacos.register_instance(app) is None
    runtime = app.extensions["nacos"]["_runtime"]
    first_generation = runtime.operation_generation
    assert nacos.get_status(app)["target_registered"] is True
    assert nacos.get_status(app)["operation_running"] is False
    assert nacos.get_status(app)["last_error"] == "ThreadCreateError"

    monkeypatch.setattr(extension_module, "Thread", real_thread)
    nacos.register_instance(app)
    _wait_settled(nacos, app, True)
    assert runtime.operation_generation == first_generation + 1
    fake_client.add_naming_instance.assert_called_once()


def test_sync_deregister_skips_obsolete_rpc_and_clears_error(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    _wait_settled(nacos, app, True)
    runtime = app.extensions["nacos"]["_runtime"]
    runtime.last_error = "OldLifecycleError"
    runtime.network_operation_lock.acquire()
    results = []

    worker = threading.Thread(target=lambda: results.append(nacos.deregister_instance(app)))
    worker.start()
    wait_until(lambda: runtime.operation_kind == "deregister")
    nacos.register_instance(app)
    runtime.network_operation_lock.release()
    worker.join(2.0)

    assert results == [True]
    assert runtime.registered is True
    assert runtime.target_registered is True
    assert runtime.operation_kind is None
    assert runtime.last_error is None
    fake_client.remove_naming_instance.assert_not_called()


def test_sync_deregister_schedules_register_when_newer_command_wins(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    _wait_settled(nacos, app, True)
    entered = threading.Event()
    release = threading.Event()

    def blocked_remove(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.remove_naming_instance.side_effect = blocked_remove
    results = []
    worker = threading.Thread(target=lambda: results.append(nacos.deregister_instance(app)))
    worker.start()
    assert entered.wait(1.0)
    nacos.register_instance(app)
    release.set()
    worker.join(2.0)
    _wait_settled(nacos, app, True)

    assert results == [True]
    assert fake_client.remove_naming_instance.call_count == 1
    assert fake_client.add_naming_instance.call_count == 2


def test_private_rpc_local_failures_are_failed_not_skipped(
    make_app, patched_create_client, fake_client, monkeypatch
):
    app = make_app()
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    runtime.target_registered = True

    outcome = nacos._execute_naming_rpc(
        state,
        runtime,
        "register",
        fake_client,
        identity=None,
        allow_during_shutdown=False,
        record_lifecycle_error=True,
    )
    assert outcome.result is extension_module._NamingResult.FAILED
    assert outcome.rpc_executed is False
    assert runtime.last_error == "MissingRegistrationIdentity"

    identity = {
        "service_name": "test-service",
        "ip": "127.0.0.1",
        "port": 8000,
        "cluster_name": "DEFAULT",
        "group_name": "DEFAULT_GROUP",
        "ephemeral": True,
    }
    outcome = nacos._execute_naming_rpc(
        state,
        runtime,
        "register",
        None,
        identity=identity,
        allow_during_shutdown=False,
        record_lifecycle_error=True,
    )
    assert outcome.result is extension_module._NamingResult.FAILED
    assert outcome.rpc_executed is False
    assert runtime.last_error == "ClientUnavailable"

    class BrokenEvent:
        def __init__(self):
            raise RuntimeError("event unavailable")

    monkeypatch.setattr(extension_module, "Event", BrokenEvent)
    outcome = nacos._execute_naming_rpc(
        state,
        runtime,
        "register",
        fake_client,
        identity=identity,
        allow_during_shutdown=False,
        record_lifecycle_error=True,
    )
    assert outcome.result is extension_module._NamingResult.FAILED
    assert outcome.rpc_executed is False
    assert runtime.last_error == "NamingEventCreateError"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, None),
        ("2.5", None),
        ("invalid", None),
        (float("inf"), None),
        (float("nan"), None),
        (-1, None),
        (0, None),
        (2.5, 2.5),
    ],
)
def test_naming_timeout_snapshot_uses_finite_positive_seconds(value, expected):
    client = SimpleNamespace(default_timeout=value)

    assert FlaskNacos._naming_timeout_seconds(client) == expected


def test_naming_timeout_snapshot_handles_missing_or_raising_attribute():
    class RaisingTimeout:
        @property
        def default_timeout(self):
            raise RuntimeError("unavailable")

    assert FlaskNacos._naming_timeout_seconds(SimpleNamespace()) is None
    assert FlaskNacos._naming_timeout_seconds(RaisingTimeout()) is None


def test_naming_rpc_snapshots_actual_client_timeout_not_config_timeout(
    make_app, patched_create_client, fake_client
):
    entered = threading.Event()
    release = threading.Event()

    def blocked_register(*_args, **_kwargs):
        entered.set()
        assert release.wait(2.0)
        return True

    fake_client.default_timeout = 2.5
    fake_client.add_naming_instance.side_effect = blocked_register
    app = make_app({"NACOS_REQUEST_TIMEOUT": 0.25})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]

    try:
        nacos.register_instance(app)
        assert entered.wait(1.0)
        assert runtime.naming_rpc_active is True
        assert runtime.naming_rpc_timeout == 2.5
        assert app.extensions["nacos"]["config"]["NACOS_REQUEST_TIMEOUT"] == 0.25
    finally:
        release.set()

    _wait_settled(nacos, app, True)
    assert runtime.naming_rpc_timeout is None


def test_cached_deterministic_error_obeys_fail_fast(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_SERVICE_NAME": None,
            "NACOS_AUTO_REGISTER": False,
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos(app)

    with pytest.raises(NacosValidationError):
        nacos.register_instance(app)

    status = nacos.get_status(app)
    assert status["target_registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] is None
    assert app.extensions["nacos"]["_runtime"].operation_generation == 0
    assert patched_create_client["count"] == 0


def test_disabled_snapshot_and_commands_are_side_effect_free(
    make_app, patched_create_client, monkeypatch
):
    app = make_app({"NACOS_ENABLED": False, "NACOS_HEALTH_CHECK_ENABLED": True})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    generation = runtime.operation_generation

    assert nacos.register_instance(app) is None
    assert nacos.deregister_instance(app) is True
    assert nacos.get_client(app) is None
    assert runtime.operation_generation == generation

    status = nacos.get_status(app)
    assert status["enabled"] is False
    assert status["client_created"] is False
    assert status["target_registered"] is False
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] is None
    assert app.test_client().get("/health/nacos").get_json()["status"] == "disabled"
    assert patched_create_client["count"] == 0


def test_missing_registered_identity_is_failed_not_skipped(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    runtime.client = fake_client
    runtime.registered = True
    runtime.registered_identity = None
    runtime.target_registered = True

    assert nacos.deregister_instance(app) is False
    assert runtime.registered is True
    assert runtime.last_error == "MissingRegisteredIdentity"
    fake_client.remove_naming_instance.assert_not_called()


def test_removed_registration_switch_does_not_block_register_or_cleanup(
    make_app, patched_create_client, fake_client
):
    removed_key = "NACOS_REGISTER_" + "ENABLED"
    app = make_app({removed_key: False})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]

    nacos.register_instance(app)
    wait_until(lambda: runtime.registered)
    assert runtime.target_registered is True
    assert patched_create_client["count"] == 1
    assert nacos.deregister_instance(app) is True
    fake_client.remove_naming_instance.assert_called_once()
