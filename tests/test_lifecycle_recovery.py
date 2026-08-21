"""Registration lifecycle transient-failure recovery tests."""

import errno
import socket
import threading
import time
from unittest.mock import MagicMock

import pytest

import flask_nacos._recovery as recovery_module
import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import (
    NacosClientError,
    NacosRegistrationError,
    NacosValidationError,
)
from tests.helpers import wait_until

FailureClass = recovery_module._LifecycleFailureClass
FailureStage = recovery_module._LifecycleFailureStage


def _classify(exc, stage=FailureStage.REGISTER_RPC, direction="register"):
    return recovery_module._classify_lifecycle_failure(
        exc,
        stage=stage,
        direction=direction,
    )


def _bare_sdk_exception_type_or_skip():
    nacos_exception = pytest.importorskip("nacos.exception")
    try:
        return nacos_exception.NacosRequestException
    except AttributeError:
        pytest.skip("this supported SDK uses a different exception system")


def _verified_client_create_sdk_or_skip():
    if recovery_module._installed_sdk_version() != "2.0.11":
        pytest.skip("CLIENT_CREATE bare-exception recovery is verified for SDK 2.0.11")
    return pytest.importorskip("nacos"), _bare_sdk_exception_type_or_skip()


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError(),
        ConnectionRefusedError(),
        ConnectionResetError(),
        OSError(errno.ENETUNREACH, "not logged"),
        socket.gaierror(socket.EAI_AGAIN, "not logged"),
    ],
)
def test_structured_transport_failures_are_transient(exc):
    assert _classify(exc).failure_class is FailureClass.TRANSIENT


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("503 connection refused must not be parsed"),
        OSError(errno.EINVAL, "not a network errno"),
        socket.gaierror(socket.EAI_NONAME, "name does not exist"),
    ],
)
def test_unproven_failures_are_unknown(exc):
    assert _classify(exc).failure_class is FailureClass.UNKNOWN


@pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504, "503"])
def test_structured_transient_http_statuses(status):
    class StructuredHttpError(Exception):
        status_code = status

    assert _classify(StructuredHttpError()).failure_class is FailureClass.TRANSIENT


def test_structured_codes_and_deterministic_evidence_have_safe_priority():
    class DisconnectError(Exception):
        error_code = "CLIENT_DISCONNECT"

    class AuthError(Exception):
        error_code = "AUTH_FAILED"

    transient = DisconnectError()
    deterministic = AuthError()
    deterministic.__cause__ = transient

    assert _classify(transient).failure_class is FailureClass.TRANSIENT
    assert _classify(deterministic).failure_class is FailureClass.DETERMINISTIC
    assert _classify(PermissionError()).failure_class is FailureClass.DETERMINISTIC
    assert _classify(NacosValidationError("invalid")).failure_class is FailureClass.DETERMINISTIC


def test_classifier_handles_cycles_and_hostile_attributes_without_escaping():
    first = RuntimeError("first")
    second = RuntimeError("second")
    first.__cause__ = second
    second.__cause__ = first
    assert _classify(first).failure_class is FailureClass.UNKNOWN

    class HostileError(Exception):
        def __getattribute__(self, name):
            if name in {
                "errno",
                "status_code",
                "http_status",
                "http_status_code",
                "status",
                "code",
                "response",
                "error_code",
                "__cause__",
                "__context__",
            }:
                raise RuntimeError("hostile attribute")
            return super().__getattribute__(name)

    result = _classify(HostileError("secret"))
    assert result.failure_class is FailureClass.UNKNOWN
    assert result.safe_error_type == "HostileError"

    chain = [RuntimeError(str(index)) for index in range(20)]
    for current, following in zip(chain, chain[1:]):
        current.__cause__ = following
    assert _classify(chain[0]).failure_class is FailureClass.UNKNOWN


@pytest.mark.parametrize(
    ("version", "client_create_class"),
    [
        ("2.0.0", FailureClass.UNKNOWN),
        ("2.0.11", FailureClass.TRANSIENT),
    ],
)
def test_verified_bare_sdk_exception_whitelist_is_stage_and_direction_bound(
    monkeypatch, version, client_create_class
):
    exc = _bare_sdk_exception_type_or_skip()("must not be logged")
    monkeypatch.setattr(recovery_module, "_installed_sdk_version", lambda: version)

    assert _classify(exc).failure_class is FailureClass.TRANSIENT
    assert (
        _classify(
            exc,
            stage=FailureStage.COMPENSATING_DEREGISTER_RPC,
            direction="deregister",
        ).failure_class
        is FailureClass.TRANSIENT
    )
    assert _classify(exc, stage=FailureStage.CLIENT_CREATE).failure_class is client_create_class
    assert (
        _classify(
            exc,
            stage=FailureStage.CLIENT_CREATE,
            direction="deregister",
        ).failure_class
        is FailureClass.UNKNOWN
    )
    assert (
        _classify(
            exc,
            stage=FailureStage.SYNC_DEREGISTER_RPC,
            direction="deregister",
        ).failure_class
        is FailureClass.UNKNOWN
    )
    assert (
        _classify(
            exc,
            stage=FailureStage.COMPENSATING_DEREGISTER_RPC,
            direction="register",
        ).failure_class
        is FailureClass.UNKNOWN
    )


def test_bare_sdk_whitelist_rejects_unknown_version(monkeypatch):
    bare_exception_type = _bare_sdk_exception_type_or_skip()
    monkeypatch.setattr(recovery_module, "_installed_sdk_version", lambda: "2.0.12")
    assert _classify(bare_exception_type()).failure_class is FailureClass.UNKNOWN


def test_bare_sdk_whitelist_rejects_same_named_fake_on_every_sdk(monkeypatch):
    fake_type = type(
        "NacosRequestException",
        (Exception,),
        {"__module__": "nacos.exception"},
    )
    monkeypatch.setattr(recovery_module, "_installed_sdk_version", lambda: "2.0.11")
    assert _classify(fake_type()).failure_class is FailureClass.UNKNOWN


def test_sdk_metadata_failure_is_fail_safe_unknown(monkeypatch):
    bare_exception_type = _bare_sdk_exception_type_or_skip()

    def broken_version(_distribution):
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(recovery_module.importlib_metadata, "version", broken_version)
    assert _classify(bare_exception_type()).failure_class is FailureClass.UNKNOWN


@pytest.mark.parametrize("status", [401, 403])
def test_deterministic_auth_status_wins_over_client_create_whitelist(monkeypatch, status):
    bare_exception_type = _bare_sdk_exception_type_or_skip()
    monkeypatch.setattr(recovery_module, "_installed_sdk_version", lambda: "2.0.11")

    class StructuredAuthError(Exception):
        status_code = status

    request_error = bare_exception_type()
    request_error.__cause__ = StructuredAuthError()
    client_error = NacosClientError("Failed to construct the Nacos SDK client")
    client_error.__cause__ = request_error

    result = _classify(client_error, stage=FailureStage.CLIENT_CREATE)

    assert result.failure_class is FailureClass.DETERMINISTIC
    assert result.safe_error_type == NacosClientError.__name__


def test_deterministic_failure_stops_before_consuming_finite_budget(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = NacosValidationError("invalid")
    app = make_app(
        {
            "NACOS_RETRY_ENABLED": True,
            "NACOS_RETRY_TIMES": 5,
            "NACOS_RETRY_INTERVAL": 0,
        }
    )
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert fake_client.add_naming_instance.call_count == 1
    assert nacos.get_status(app)["last_error"] == NacosRegistrationError.__name__


def test_retry_disabled_transient_failure_runs_once(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = ConnectionRefusedError("private detail")
    app = make_app({"NACOS_RETRY_ENABLED": False, "NACOS_RETRY_TIMES": 9})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])
    status = nacos.get_status(app)

    assert fake_client.add_naming_instance.call_count == 1
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == NacosRegistrationError.__name__


def test_authenticated_client_creation_self_recovers_without_external_trigger(
    make_app, fake_client, monkeypatch
):
    sdk_module, request_exception_type = _verified_client_create_sdk_or_skip()
    server_available = threading.Event()
    recovery_attempted = threading.Event()
    attempts_lock = threading.Lock()
    attempt_count = 0

    def construct_client(*_args, **_kwargs):
        nonlocal attempt_count
        with attempts_lock:
            attempt_count += 1
            current_attempt = attempt_count
        if current_attempt > 2:
            recovery_attempted.set()
        if not server_available.is_set():
            raise request_exception_type()
        return fake_client

    constructor = MagicMock(side_effect=construct_client)
    monkeypatch.setattr(sdk_module, "NacosClient", constructor)
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, _round: 0.01),
    )
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_USERNAME": "recovery-user",
            "NACOS_PASSWORD": "test-password",
            "NACOS_RETRY_ENABLED": True,
            "NACOS_RETRY_TIMES": 2,
            "NACOS_RETRY_INTERVAL": 0,
        }
    )

    started = time.monotonic()
    nacos = FlaskNacos(app)
    init_elapsed = time.monotonic() - started
    runtime = app.extensions["nacos"]["_runtime"]

    try:
        assert init_elapsed < 1.0
        assert recovery_attempted.wait(2.0)

        status = nacos.get_status(app)
        assert status["target_registered"] is True
        assert status["registered"] is False
        assert status["operation_running"] is True
        assert runtime.operation_kind == "register"
        assert runtime.naming_rpc_seq == 0
        assert runtime.naming_rpc_active is False
        assert runtime.naming_rpc_done is None

        server_available.set()
        wait_until(lambda: nacos.get_status(app)["registered"], timeout=3.0)
        wait_until(lambda: not nacos.get_status(app)["operation_running"], timeout=3.0)
        status = nacos.get_status(app)

        assert constructor.call_count > 2
        assert fake_client.add_naming_instance.call_count == 1
        assert runtime.naming_rpc_seq == 1
        assert runtime.naming_rpc_active is False
        assert runtime.naming_rpc_done is None
        assert status["target_registered"] is True
        assert status["registered"] is True
        assert status["operation_running"] is False
        assert status["last_error"] is None

        _, constructor_kwargs = constructor.call_args
        assert constructor_kwargs["username"] == "recovery-user"
        assert constructor_kwargs["password"] == "test-password"
    finally:
        server_available.set()
        nacos.deregister_instance(app)
        wait_until(lambda: not nacos.get_status(app)["operation_running"], timeout=3.0)


def test_retry_disabled_authenticated_client_transient_failure_runs_once(
    make_app, monkeypatch
):
    sdk_module, request_exception_type = _verified_client_create_sdk_or_skip()
    constructor = MagicMock(side_effect=request_exception_type())
    monkeypatch.setattr(sdk_module, "NacosClient", constructor)
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_USERNAME": "recovery-user",
            "NACOS_PASSWORD": "test-password",
            "NACOS_RETRY_ENABLED": False,
            "NACOS_RETRY_TIMES": 9,
        }
    )

    nacos = FlaskNacos(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])
    runtime = app.extensions["nacos"]["_runtime"]
    status = nacos.get_status(app)

    assert constructor.call_count == 1
    assert runtime.naming_rpc_seq == 0
    assert runtime.naming_rpc_active is False
    assert runtime.naming_rpc_done is None
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == NacosClientError.__name__


@pytest.mark.parametrize("status_code", [401, 403])
def test_authenticated_client_http_auth_failure_is_deterministic(
    make_app, monkeypatch, status_code
):
    sdk_module, request_exception_type = _verified_client_create_sdk_or_skip()

    class StructuredAuthError(Exception):
        pass

    StructuredAuthError.status_code = status_code
    request_error = request_exception_type()
    request_error.__cause__ = StructuredAuthError()

    constructor = MagicMock(side_effect=request_error)
    monkeypatch.setattr(sdk_module, "NacosClient", constructor)
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_USERNAME": "recovery-user",
            "NACOS_PASSWORD": "test-password",
            "NACOS_RETRY_ENABLED": True,
            "NACOS_RETRY_TIMES": 5,
            "NACOS_RETRY_INTERVAL": 0,
        }
    )

    nacos = FlaskNacos(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])
    status = nacos.get_status(app)

    assert constructor.call_count == 1
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == NacosClientError.__name__


def test_worker_self_recovers_without_external_registration_trigger(
    make_app, patched_create_client, fake_client, monkeypatch
):
    fake_client.add_naming_instance.side_effect = [
        ConnectionRefusedError("private detail"),
        ConnectionResetError("private detail"),
        True,
    ]
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, _round: 0.01),
    )
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_RETRY_TIMES": 2,
            "NACOS_RETRY_INTERVAL": 0,
        }
    )

    nacos = FlaskNacos(app)
    wait_until(
        lambda: (
            nacos.get_status(app)["registered"]
            and not nacos.get_status(app)["operation_running"]
        ),
        timeout=3.0,
    )
    status = nacos.get_status(app)

    assert fake_client.add_naming_instance.call_count == 3
    assert fake_client.add_naming_instance.call_count > 2
    assert status["target_registered"] is True
    assert status["registered"] is True
    assert status["operation_running"] is False
    assert status["last_error"] is None


@pytest.mark.parametrize(
    "final_failure",
    [False, NacosValidationError("deterministic")],
)
def test_recovery_stops_when_a_later_failure_is_not_transient(
    make_app, patched_create_client, fake_client, monkeypatch, final_failure
):
    fake_client.add_naming_instance.side_effect = [
        ConnectionRefusedError("private detail"),
        final_failure,
    ]
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, _round: 0),
    )
    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert fake_client.add_naming_instance.call_count == 2
    assert nacos.get_status(app)["registered"] is False


def test_recovery_round_includes_transient_client_creation_failures(
    make_app, fake_client, monkeypatch
):
    create_attempts = []
    outcomes = [
        ConnectionRefusedError("private detail"),
        ConnectionResetError("private detail"),
        fake_client,
    ]

    def create(_config):
        create_attempts.append(True)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    rounds = []
    monkeypatch.setattr(extension_module, "create_client", create)
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, round_number: rounds.append(round_number) or 0),
    )
    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]

    nacos.register_instance(app)
    wait_until(lambda: nacos.get_status(app)["registered"])
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert len(create_attempts) == 3
    assert rounds[:2] == [1, 2]
    assert runtime.naming_rpc_seq == 1
    assert runtime.naming_rpc_active is False
    assert runtime.naming_rpc_done is None


def test_recovery_round_includes_executed_transient_naming_failures(
    make_app, patched_create_client, fake_client, monkeypatch
):
    fake_client.add_naming_instance.side_effect = [
        ConnectionRefusedError("private detail"),
        ConnectionResetError("private detail"),
        True,
    ]
    rounds = []
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, round_number: rounds.append(round_number) or 0),
    )
    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: nacos.get_status(app)["registered"])
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert rounds[:2] == [1, 2]
    assert fake_client.add_naming_instance.call_count == 3


def test_direction_change_starts_a_fresh_recovery_phase(
    make_app, patched_create_client, fake_client, monkeypatch
):
    register_recovery_entered = threading.Event()
    release_register = threading.Event()

    def recovered_register(*_args, **_kwargs):
        register_recovery_entered.set()
        assert release_register.wait(2.0)
        return True

    register_calls = []

    def register_side_effect(*args, **kwargs):
        register_calls.append(True)
        if len(register_calls) == 1:
            raise ConnectionRefusedError()
        return recovered_register(*args, **kwargs)

    fake_client.add_naming_instance.side_effect = register_side_effect
    fake_client.remove_naming_instance.side_effect = [ConnectionResetError(), True]
    rounds = []
    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, round_number: rounds.append(round_number) or 0),
    )
    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)

    try:
        nacos.register_instance(app)
        assert register_recovery_entered.wait(1.0)
        assert nacos.deregister_instance(app) is True
        release_register.set()
        wait_until(lambda: not nacos.get_status(app)["operation_running"])

        assert rounds[:2] == [1, 1]
        assert fake_client.add_naming_instance.call_count == 2
        assert fake_client.remove_naming_instance.call_count == 2
        assert nacos.get_status(app)["registered"] is False
    finally:
        release_register.set()
        nacos.deregister_instance(app)


def test_generation_change_without_direction_change_preserves_recovery_round(
    make_app, patched_create_client, fake_client, monkeypatch
):
    fake_client.add_naming_instance.side_effect = [
        ConnectionRefusedError(),
        ConnectionResetError(),
        True,
    ]
    first_wait = threading.Event()
    release_wait = threading.Event()
    rounds = []
    waits = []

    monkeypatch.setattr(
        FlaskNacos,
        "_lifecycle_recovery_delay",
        staticmethod(lambda _interval, round_number: rounds.append(round_number) or 0),
    )

    def controlled_wait(_runtime, _worker, _delay):
        waits.append(True)
        if len(waits) == 1:
            first_wait.set()
            assert release_wait.wait(2.0)
        return True

    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)
    monkeypatch.setattr(nacos, "_interruptible_retry_wait", controlled_wait)

    try:
        nacos.register_instance(app)
        assert first_wait.wait(1.0)
        assert nacos.deregister_instance(app) is True
        nacos.register_instance(app)
        release_wait.set()
        wait_until(lambda: not nacos.get_status(app)["operation_running"])

        assert rounds[:2] == [1, 2]
        assert fake_client.add_naming_instance.call_count == 3
        assert nacos.get_status(app)["registered"] is True
    finally:
        release_wait.set()
        nacos.deregister_instance(app)


def test_unexecuted_transient_failure_does_not_increment_recovery_round(
    make_app, patched_create_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    worker = threading.current_thread()
    runtime.target_registered = True
    runtime.operation_kind = "register"
    runtime.operation_thread = worker
    failure = recovery_module._LifecycleFailure(
        FailureClass.TRANSIENT,
        "SyntheticTransient",
    )

    action, _, recovery_round = nacos._handle_worker_failure(
        runtime,
        worker,
        "register",
        failure,
        finite_attempts=1,
        recovery_round=1,
        retry_enabled=True,
        max_attempts=1,
        real_recovery_attempt=False,
        log_state=extension_module._WorkerLogState(direction="register"),
    )

    assert action == "recovery"
    assert recovery_round == 1
    runtime.operation_kind = None
    runtime.operation_thread = None


@pytest.mark.parametrize(
    ("interval", "round_number", "expected_bounds"),
    [
        (0, 1, (1.6, 2.0)),
        (5, 1, (8.0, 10.0)),
        (20, 1, (24.0, 30.0)),
        (60, 1, (60.0, 72.0)),
    ],
)
def test_recovery_delay_has_first_round_jitter_and_safe_floor(
    monkeypatch, interval, round_number, expected_bounds
):
    observed = []

    def uniform(lower, upper):
        observed.append((lower, upper))
        return (lower + upper) / 2

    monkeypatch.setattr(extension_module.random, "uniform", uniform)
    delay = FlaskNacos._lifecycle_recovery_delay(interval, round_number)

    assert observed == [expected_bounds]
    assert delay >= max(interval, 1.0)


def test_recovery_wait_happens_before_first_extra_attempt(
    make_app, patched_create_client, fake_client, monkeypatch
):
    fake_client.add_naming_instance.side_effect = [ConnectionRefusedError(), True]
    app = make_app({"NACOS_RETRY_TIMES": 1, "NACOS_RETRY_INTERVAL": 0})
    nacos = FlaskNacos(app)
    waits = []

    monkeypatch.setattr(
        nacos,
        "_lifecycle_recovery_delay",
        lambda _interval, round_number: 1.75 if round_number == 1 else 2.0,
    )

    def complete_wait(_runtime, _worker, delay):
        waits.append((fake_client.add_naming_instance.call_count, delay))
        return True

    monkeypatch.setattr(nacos, "_interruptible_retry_wait", complete_wait)
    nacos.register_instance(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert waits[0] == (1, 1.75)
    assert fake_client.add_naming_instance.call_count == 2


def test_shutdown_immediately_interrupts_long_recovery_wait(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = ConnectionRefusedError()
    app = make_app(
        {
            "NACOS_RETRY_TIMES": 1,
            "NACOS_RETRY_INTERVAL": 100,
            "NACOS_AUTO_DEREGISTER": False,
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_until(lambda: fake_client.add_naming_instance.call_count == 1)

    started = time.monotonic()
    nacos._atexit_handler(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert time.monotonic() - started < 1.0
    assert fake_client.add_naming_instance.call_count == 1


def test_naming_outcome_distinguishes_executed_failure_and_skipped(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    identity = {
        "service_name": "test-service",
        "ip": "127.0.0.1",
        "port": 8000,
        "cluster_name": "DEFAULT",
        "group_name": "DEFAULT_GROUP",
        "ephemeral": True,
    }
    runtime.target_registered = True
    fake_client.add_naming_instance.return_value = False

    failed = nacos._execute_naming_rpc(
        state,
        runtime,
        "register",
        fake_client,
        identity=identity,
        allow_during_shutdown=False,
        record_lifecycle_error=True,
        stage=FailureStage.REGISTER_RPC,
    )
    assert failed.result is extension_module._NamingResult.FAILED
    assert failed.rpc_executed is True
    assert failed.failure is not None
    assert failed.failure.failure_class is FailureClass.UNKNOWN

    runtime.target_registered = False
    skipped = nacos._execute_naming_rpc(
        state,
        runtime,
        "register",
        fake_client,
        identity=identity,
        allow_during_shutdown=False,
        record_lifecycle_error=True,
        stage=FailureStage.REGISTER_RPC,
    )
    assert skipped.result is extension_module._NamingResult.SKIPPED
    assert skipped.rpc_executed is False
    assert skipped.failure is None
    assert fake_client.add_naming_instance.call_count == 1


def test_client_failure_never_publishes_naming_rpc_metadata(
    make_app, monkeypatch
):
    def fail_client(_config):
        raise RuntimeError("private detail")

    monkeypatch.setattr(extension_module, "create_client", fail_client)
    app = make_app({"NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]

    nacos.register_instance(app)
    wait_until(lambda: not nacos.get_status(app)["operation_running"])

    assert runtime.naming_rpc_seq == 0
    assert runtime.naming_rpc_active is False
    assert runtime.naming_rpc_done is None


def test_worker_warning_is_rate_limited_and_recovery_is_announced(monkeypatch):
    moments = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(extension_module.time, "monotonic", lambda: next(moments))
    warnings = []
    debug_records = []
    monkeypatch.setattr(
        extension_module.logger,
        "warning",
        lambda message, *args: warnings.append((message, args)),
    )
    monkeypatch.setattr(
        extension_module.logger,
        "debug",
        lambda message, *args: debug_records.append((message, args)),
    )
    state = extension_module._WorkerLogState(direction="register")
    failure = recovery_module._LifecycleFailure(FailureClass.TRANSIENT, "SafeFailure")

    FlaskNacos._log_worker_failure(
        "register", failure, state, entering_recovery=False
    )
    FlaskNacos._log_worker_failure(
        "register", failure, state, entering_recovery=False
    )
    state.recovery_active = True
    FlaskNacos._log_worker_failure(
        "register", failure, state, entering_recovery=True
    )

    assert len(warnings) == 2
    assert len(debug_records) == 1
    assert "private" not in repr(warnings + debug_records)
