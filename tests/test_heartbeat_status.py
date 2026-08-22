"""Runtime heartbeat observation without lifecycle coupling."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import flask_nacos.client as client_module
import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from tests.helpers import wait_registered, wait_until


class _HeartbeatClient:
    def __init__(self):
        self.default_timeout = 3.0
        self.heartbeat_outcome = True
        self.block_next_heartbeat = False
        self.heartbeat_started = threading.Event()
        self.heartbeat_release = threading.Event()

    def add_naming_instance(self, *_args, **_kwargs):
        return True

    def remove_naming_instance(self, *_args, **_kwargs):
        return True

    def send_heartbeat(self, *_args, **_kwargs):
        if self.block_next_heartbeat:
            self.block_next_heartbeat = False
            self.heartbeat_started.set()
            if not self.heartbeat_release.wait(2.0):
                raise TimeoutError("test heartbeat release timed out")
        outcome = self.heartbeat_outcome
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _heartbeat(client, service_name="test-service"):
    return client.send_heartbeat(
        service_name=service_name,
        ip="127.0.0.1",
        port=8000,
        cluster_name=None,
        group_name="DEFAULT_GROUP",
    )


def _wait_for_new_observation_tick(app):
    runtime = app.extensions["nacos"]["_runtime"]
    boundary = (
        runtime.last_heartbeat_observed_monotonic
        if runtime.last_heartbeat_observed_monotonic is not None
        else runtime.heartbeat_cycle_started_monotonic
    )
    wait_until(
        lambda: extension_module.time.monotonic() > boundary
    )


def test_status_observes_heartbeat_success_failure_and_recovery(
    make_app, monkeypatch
):
    client = _HeartbeatClient()
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: client)
    app = make_app({"NACOS_LOG_ENABLED": False})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_registered(nacos, app)

    status = nacos.get_status(app)
    assert status["heartbeat_state"] == "unknown"
    assert status["last_heartbeat_success_at"] is None
    assert status["last_heartbeat_failure_at"] is None
    assert status["heartbeat_error_type"] is None
    lifecycle_before = (
        status["target_registered"],
        status["registered"],
        app.extensions["nacos"]["_runtime"].operation_generation,
        status["operation_running"],
    )

    _wait_for_new_observation_tick(app)
    assert _heartbeat(client) is True
    healthy = nacos.get_status(app)
    assert healthy["heartbeat_state"] == "healthy"
    assert isinstance(healthy["last_heartbeat_success_at"], float)
    assert healthy["last_heartbeat_failure_at"] is None
    assert healthy["heartbeat_error_type"] is None

    _wait_for_new_observation_tick(app)
    client.heartbeat_outcome = RuntimeError("credential-must-not-be-stored")
    with pytest.raises(RuntimeError, match="credential-must-not-be-stored"):
        _heartbeat(client)
    failing = nacos.get_status(app)
    assert failing["heartbeat_state"] == "failing"
    assert failing["last_heartbeat_success_at"] == healthy["last_heartbeat_success_at"]
    assert isinstance(failing["last_heartbeat_failure_at"], float)
    assert failing["heartbeat_error_type"] == "RuntimeError"
    assert "credential-must-not-be-stored" not in str(failing)

    _wait_for_new_observation_tick(app)
    client.heartbeat_outcome = True
    assert _heartbeat(client) is True
    recovered = nacos.get_status(app)
    assert recovered["heartbeat_state"] == "healthy"
    assert recovered["last_heartbeat_failure_at"] == failing["last_heartbeat_failure_at"]
    assert recovered["heartbeat_error_type"] is None
    assert (
        recovered["target_registered"],
        recovered["registered"],
        app.extensions["nacos"]["_runtime"].operation_generation,
        recovered["operation_running"],
    ) == lifecycle_before

    assert nacos.deregister_instance(app) is True
    cleared = nacos.get_status(app)
    assert cleared["heartbeat_state"] == "not_applicable"
    assert cleared["last_heartbeat_success_at"] is None
    assert cleared["last_heartbeat_failure_at"] is None
    assert cleared["heartbeat_error_type"] is None


def test_persistent_or_nonmatching_heartbeat_is_not_applicable(
    make_app, monkeypatch
):
    client = _HeartbeatClient()
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: client)
    app = make_app({"NACOS_SERVICE_EPHEMERAL": False})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_registered(nacos, app)
    assert nacos.get_status(app)["heartbeat_state"] == "not_applicable"
    assert _heartbeat(client) is True
    assert nacos.get_status(app)["heartbeat_state"] == "not_applicable"
    assert nacos.deregister_instance(app) is True


def test_other_or_unidentifiable_heartbeat_does_not_update_status(
    make_app, monkeypatch
):
    class ComplexIdentity:
        def __str__(self):
            raise AssertionError("identity must not be stringified")

    client = _HeartbeatClient()
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: client)
    app = make_app()
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_registered(nacos, app)
    assert _heartbeat(client, service_name="another-service") is True
    assert client.send_heartbeat(ComplexIdentity(), "127.0.0.1", 8000) is True

    status = nacos.get_status(app)
    assert status["heartbeat_state"] == "unknown"
    assert status["last_heartbeat_success_at"] is None
    assert nacos.deregister_instance(app) is True


def test_observation_uses_cycle_and_monotonic_order_not_wall_clock(make_app):
    app = make_app()
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    identity = {
        "service_name": "test-service",
        "group_name": "DEFAULT_GROUP",
        "cluster_name": "DEFAULT",
        "ip": "127.0.0.1",
        "port": 8000,
        "ephemeral": True,
    }
    heartbeat_identity = (
        "test-service",
        "DEFAULT_GROUP",
        None,
        "127.0.0.1",
        8000,
    )
    with runtime.state_lock:
        runtime.registered = True
        runtime.registered_identity = identity
        runtime.heartbeat_state = "unknown"
        runtime.heartbeat_cycle_started_monotonic = 100.0

    # An event that began in a previous registration cycle is ignored.
    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=False,
        started_monotonic=99.0,
        observed_monotonic=120.0,
        observed_at=1200.0,
        error_type="RuntimeError",
    )
    assert nacos.get_status(app)["heartbeat_state"] == "unknown"

    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=True,
        started_monotonic=101.0,
        observed_monotonic=130.0,
        observed_at=1000.0,
        error_type=None,
    )
    assert nacos.get_status(app)["heartbeat_state"] == "healthy"

    # A later callback for an older completion cannot overwrite the newer one.
    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=False,
        started_monotonic=102.0,
        observed_monotonic=129.0,
        observed_at=2000.0,
        error_type="ValueError",
    )
    assert nacos.get_status(app)["heartbeat_state"] == "healthy"

    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=False,
        started_monotonic=102.5,
        observed_monotonic=130.0,
        observed_at=2100.0,
        error_type="ValueError",
    )
    equal_tick = nacos.get_status(app)
    assert equal_tick["heartbeat_state"] == "failing"
    assert equal_tick["last_heartbeat_failure_at"] == 2100.0
    assert equal_tick["heartbeat_error_type"] == "ValueError"

    # Wall-clock rollback is visible publicly but does not define event order.
    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=False,
        started_monotonic=103.0,
        observed_monotonic=131.0,
        observed_at=900.0,
        error_type="ConnectionError",
    )
    status = nacos.get_status(app)
    assert status["heartbeat_state"] == "failing"
    assert status["last_heartbeat_failure_at"] == 900.0
    assert status["heartbeat_error_type"] == "ConnectionError"

    with runtime.state_lock:
        runtime.shutting_down = True
    nacos._record_heartbeat_observation(
        app,
        runtime,
        heartbeat_identity,
        succeeded=True,
        started_monotonic=104.0,
        observed_monotonic=132.0,
        observed_at=1100.0,
        error_type=None,
    )
    assert nacos.get_status(app)["heartbeat_state"] == "failing"


def test_same_identity_heartbeat_from_previous_cycle_is_ignored(
    make_app, monkeypatch
):
    client = _HeartbeatClient()
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: client)
    app = make_app()
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)

    instrumentation = client_module._heartbeat_instrumentation(client)
    assert instrumentation is not None
    runtime_observer = instrumentation.observer
    assert runtime_observer is not None
    heartbeat_events = []

    def _observe_and_record(*event):
        heartbeat_events.append(event)
        runtime_observer(*event)

    instrumentation.observer = _observe_and_record

    client.block_next_heartbeat = True
    client.heartbeat_outcome = RuntimeError("old-cycle")
    observed = []

    def _old_heartbeat():
        try:
            _heartbeat(client)
        except Exception as exc:
            observed.append(type(exc).__name__)

    thread = threading.Thread(target=_old_heartbeat)
    thread.start()
    assert client.heartbeat_started.wait(1.0)

    # Ensure the new registration cycle begins after the blocked heartbeat's
    # start even on coarse monotonic clocks used by older Windows runtimes.
    old_cycle_tick = extension_module.time.monotonic()
    wait_until(lambda: extension_module.time.monotonic() > old_cycle_tick)

    assert nacos.deregister_instance(app) is True
    client.heartbeat_outcome = True
    nacos.register_instance(app)
    wait_registered(nacos, app)
    assert nacos.get_status(app)["heartbeat_state"] == "unknown"

    client.heartbeat_outcome = RuntimeError("old-cycle")
    client.heartbeat_release.set()
    thread.join(2.0)
    assert not thread.is_alive()
    assert observed == ["RuntimeError"]
    status = nacos.get_status(app)
    runtime = app.extensions["nacos"]["_runtime"]
    assert len(heartbeat_events) == 1
    assert heartbeat_events[0][2] <= runtime.heartbeat_cycle_started_monotonic
    assert status["heartbeat_state"] == "unknown"
    assert status["last_heartbeat_success_at"] is None
    assert status["last_heartbeat_failure_at"] is None
    assert status["heartbeat_error_type"] is None
    assert nacos.deregister_instance(app) is True


def test_runtime_heartbeat_observation_is_isolated_between_apps(
    make_app, monkeypatch
):
    client_a = _HeartbeatClient()
    client_b = _HeartbeatClient()
    clients = iter((client_a, client_b))
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: next(clients))
    app_a = make_app({"NACOS_SERVICE_NAME": "service-a"})
    app_b = make_app({"NACOS_SERVICE_NAME": "service-b"})
    nacos = FlaskNacos(app_a)
    nacos.init_app(app_b)

    nacos.register_instance(app_a)
    nacos.register_instance(app_b)
    wait_registered(nacos, app_a)
    wait_registered(nacos, app_b)

    _wait_for_new_observation_tick(app_a)
    _wait_for_new_observation_tick(app_b)

    client_a.heartbeat_outcome = RuntimeError("private-a")
    with pytest.raises(RuntimeError):
        _heartbeat(client_a, service_name="service-a")
    assert _heartbeat(client_b, service_name="service-b") is True

    status_a = nacos.get_status(app_a)
    status_b = nacos.get_status(app_b)
    assert status_a["heartbeat_state"] == "failing"
    assert status_a["heartbeat_error_type"] == "RuntimeError"
    assert status_b["heartbeat_state"] == "healthy"
    assert status_b["heartbeat_error_type"] is None
    assert nacos.deregister_instance(app_a) is True
    assert nacos.deregister_instance(app_b) is True


def test_concurrent_heartbeat_and_status_reads_are_atomic(make_app, monkeypatch):
    client = _HeartbeatClient()
    monkeypatch.setattr(extension_module, "create_client", lambda _cfg: client)
    app = make_app()
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)
    _wait_for_new_observation_tick(app)

    with ThreadPoolExecutor(max_workers=16) as executor:
        heartbeat_futures = [executor.submit(_heartbeat, client) for _ in range(30)]
        status_futures = [executor.submit(nacos.get_status, app) for _ in range(70)]

    assert all(future.result() is True for future in heartbeat_futures)
    snapshots = [future.result() for future in status_futures]
    for status in snapshots:
        assert status["heartbeat_state"] in {"unknown", "healthy"}
        if status["heartbeat_state"] == "healthy":
            assert isinstance(status["last_heartbeat_success_at"], float)
            assert status["heartbeat_error_type"] is None

    assert nacos.get_status(app)["heartbeat_state"] == "healthy"
    assert nacos.deregister_instance(app) is True
