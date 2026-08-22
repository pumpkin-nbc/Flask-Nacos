"""Registration-source, lazy-validation, and pending arbitration regressions."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields

import pytest

import flask_nacos.extension as extension_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosValidationError


class _DormantThread:
    """Thread-shaped object that records publication without running a Worker."""

    def __init__(self, *, target, args, name, daemon):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def test_registration_sources_and_call_local_values_are_minimal_and_frozen():
    source_type = extension_module._RegistrationSource
    assert list(source_type.__members__) == [
        "EXPLICIT_REGISTER",
        "AUTO_REGISTER",
        "PENDING_RECOVERY",
    ]

    context = extension_module._RegisterContext(source=source_type.EXPLICIT_REGISTER)
    policy = FlaskNacos._registration_policy(context)

    assert [item.name for item in fields(context)] == ["source"]
    assert [item.name for item in fields(policy)] == [
        "propagate_config_error",
        "consume_pending",
        "log_label",
    ]
    assert policy.propagate_config_error is True
    assert policy.consume_pending is False
    assert policy.log_label == "explicit_register"
    with pytest.raises(FrozenInstanceError):
        context.source = source_type.AUTO_REGISTER
    with pytest.raises(FrozenInstanceError):
        policy.consume_pending = True


def test_registration_policy_is_pure_and_contains_no_lifecycle_plan(
    make_app, patched_create_client, monkeypatch
):
    app = make_app()
    nacos = FlaskNacos(app)
    runtime = app.extensions["nacos"]["_runtime"]
    before = dict(runtime.__dict__)

    for method_name in ("debug", "info", "warning", "error", "critical"):
        monkeypatch.setattr(
            extension_module.logger,
            method_name,
            lambda *args, **kwargs: pytest.fail("registration policy emitted a log"),
        )
    policy = nacos._registration_policy(
        extension_module._RegisterContext(
            source=extension_module._RegistrationSource.PENDING_RECOVERY
        )
    )

    assert runtime.__dict__ == before
    assert patched_create_client["count"] == 0
    assert set(vars(policy)) == {
        "propagate_config_error",
        "consume_pending",
        "log_label",
    }
    forbidden = {"target", "generation", "operation", "worker", "runtime"}
    assert forbidden.isdisjoint(vars(policy))


def test_init_auto_registration_sets_and_resets_call_source(make_app, monkeypatch):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos()
    observed = []

    def _observe_register(target_app=None):
        observed.append(extension_module._REGISTRATION_SOURCE_CONTEXT.get())
        assert target_app is app

    monkeypatch.setattr(nacos, "register_instance", _observe_register)
    nacos.init_app(app)

    assert observed == [extension_module._RegistrationSource.AUTO_REGISTER]
    assert (
        extension_module._REGISTRATION_SOURCE_CONTEXT.get()
        is extension_module._RegistrationSource.EXPLICIT_REGISTER
    )


def test_init_auto_registration_resets_call_source_after_exception(make_app, monkeypatch):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos()

    def _fail_register(_app=None):
        assert (
            extension_module._REGISTRATION_SOURCE_CONTEXT.get()
            is extension_module._RegistrationSource.AUTO_REGISTER
        )
        raise RuntimeError("registration entry failed")

    monkeypatch.setattr(nacos, "register_instance", _fail_register)
    with pytest.raises(RuntimeError, match="registration entry failed"):
        nacos.init_app(app)

    assert (
        extension_module._REGISTRATION_SOURCE_CONTEXT.get()
        is extension_module._RegistrationSource.EXPLICIT_REGISTER
    )
    assert "nacos" not in app.extensions


@pytest.mark.parametrize(
    "source",
    list(extension_module._RegistrationSource),
)
def test_all_sources_use_the_same_lifecycle_transition(
    make_app, patched_create_client, monkeypatch, source
):
    monkeypatch.setattr(extension_module, "Thread", _DormantThread)
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    runtime.auto_register_pending = True

    nacos._prepare_registration(
        app,
        extension_module._RegisterContext(source=source),
        new_command=True,
    )

    assert runtime.auto_register_pending is False
    assert runtime.target_registered is True
    assert runtime.registered is False
    assert runtime.operation_generation == 1
    assert runtime.operation_kind == "register"
    assert isinstance(runtime.operation_thread, _DormantThread)
    assert runtime.operation_thread.started is True
    assert runtime.operation_thread.args == (state, runtime)
    assert patched_create_client["count"] == 0
    assert not any(
        isinstance(value, extension_module._RegisterContext)
        for value in runtime.__dict__.values()
    )
    assert not any(
        isinstance(value, extension_module._RegistrationPolicy)
        for value in state.values()
    )


def test_auto_register_off_defers_registration_validation_until_explicit_intent(
    make_app, patched_create_client
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_SERVICE_NAME": None,
        }
    )
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]

    assert extension_module._REGISTRATION_ERROR_KEY not in state
    assert nacos.get_status(app)["last_error"] is None
    with pytest.raises(NacosValidationError):
        nacos.register_instance(app)

    assert isinstance(state[extension_module._REGISTRATION_ERROR_KEY], NacosValidationError)
    status = nacos.get_status(app)
    assert status["target_registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] is None
    assert patched_create_client["count"] == 0


def test_pending_recovery_keeps_local_config_error_as_async_lifecycle_state(
    make_app, patched_create_client
):
    app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_SERVICE_NAME": None,
        }
    )
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    runtime.auto_register_pending = True

    nacos._prepare_registration(
        app,
        extension_module._RegisterContext(
            source=extension_module._RegistrationSource.PENDING_RECOVERY
        ),
        new_command=True,
    )

    status = nacos.get_status(app)
    assert runtime.auto_register_pending is False
    assert status["target_registered"] is True
    assert status["registered"] is False
    assert status["operation_running"] is False
    assert status["last_error"] == "NacosValidationError"
    assert patched_create_client["count"] == 0


def test_validation_cache_compare_and_set_is_immutable(
    make_app, patched_create_client, monkeypatch
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    barrier = threading.Barrier(2)
    candidates = {
        "candidate-a": None,
        "candidate-b": NacosValidationError("deterministic"),
    }

    def _validate(_cfg, _connection_error):
        barrier.wait(timeout=2)
        return candidates[threading.current_thread().name]

    monkeypatch.setattr(nacos, "_registration_config_error", _validate)
    monkeypatch.setattr(extension_module, "Thread", _DormantThread)

    def _register(name):
        threading.current_thread().name = name
        try:
            nacos.register_instance(app)
        except NacosValidationError as exc:
            return exc
        return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_register, "candidate-a"),
            executor.submit(_register, "candidate-b"),
        ]
        results = [future.result(timeout=3) for future in futures]

    committed = state[extension_module._REGISTRATION_ERROR_KEY]
    assert committed is candidates["candidate-a"] or committed is candidates["candidate-b"]
    if committed is None:
        assert results == [None, None]
        nacos.register_instance(app)
    else:
        assert all(result is committed for result in results)
        with pytest.raises(NacosValidationError) as raised:
            nacos.register_instance(app)
        assert raised.value is committed
    assert state[extension_module._REGISTRATION_ERROR_KEY] is committed
    assert patched_create_client["count"] == 0


def test_pending_cancel_during_validation_keeps_cache_but_discards_lifecycle(
    make_app, patched_create_client, monkeypatch
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    runtime.auto_register_pending = True
    entered = threading.Event()
    release = threading.Event()

    def _validate(_cfg, _connection_error):
        entered.set()
        assert release.wait(2)
        return None

    monkeypatch.setattr(nacos, "_registration_config_error", _validate)
    worker = threading.Thread(
        target=lambda: nacos._resume_auto_register_if_pending(app, state, runtime)
    )
    worker.start()
    assert entered.wait(2)
    generation = runtime.operation_generation
    assert nacos.deregister_instance(app) is True
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert extension_module._REGISTRATION_ERROR_KEY in state
    assert state[extension_module._REGISTRATION_ERROR_KEY] is None
    assert runtime.auto_register_pending is False
    assert runtime.target_registered is False
    assert runtime.operation_generation == generation
    assert runtime.operation_kind is None
    assert patched_create_client["count"] == 0


def test_runtime_replacement_during_validation_restarts_on_current_runtime(
    make_app, patched_create_client, monkeypatch
):
    monkeypatch.setattr(extension_module, "Thread", _DormantThread)
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    old_runtime = state["_runtime"]
    entered = threading.Event()
    release = threading.Event()
    calls = {"count": 0}

    def _validate(_cfg, _connection_error):
        calls["count"] += 1
        if calls["count"] == 1:
            entered.set()
            assert release.wait(2)
        return None

    monkeypatch.setattr(nacos, "_registration_config_error", _validate)
    worker = threading.Thread(target=lambda: nacos.register_instance(app))
    worker.start()
    assert entered.wait(2)
    new_runtime = extension_module._AppRuntimeState(pid=nacos._current_pid())
    state["_runtime"] = new_runtime
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert calls["count"] == 2
    assert old_runtime.target_registered is False
    assert old_runtime.operation_kind is None
    assert new_runtime.target_registered is True
    assert new_runtime.operation_generation == 1
    assert new_runtime.operation_kind == "register"
    assert patched_create_client["count"] == 0


def test_app_state_and_config_replacement_discards_old_validation_candidate(
    make_app, patched_create_client, monkeypatch
):
    monkeypatch.setattr(extension_module, "Thread", _DormantThread)
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    old_state = app.extensions["nacos"]
    old_runtime = old_state["_runtime"]
    entered = threading.Event()
    release = threading.Event()
    calls = {"count": 0}

    def _validate(_cfg, _connection_error):
        calls["count"] += 1
        if calls["count"] == 1:
            entered.set()
            assert release.wait(2)
        return None

    monkeypatch.setattr(nacos, "_registration_config_error", _validate)
    worker = threading.Thread(target=lambda: nacos.register_instance(app))
    worker.start()
    assert entered.wait(2)

    new_state = dict(old_state)
    new_runtime = extension_module._AppRuntimeState(pid=nacos._current_pid())
    new_state["config"] = dict(old_state["config"])
    new_state["_runtime"] = new_runtime
    new_state["_runtime_rebuild_lock"] = threading.Lock()
    new_state.pop(extension_module._REGISTRATION_ERROR_KEY, None)
    app.extensions["nacos"] = new_state
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert calls["count"] == 2
    assert extension_module._REGISTRATION_ERROR_KEY not in old_state
    assert new_state[extension_module._REGISTRATION_ERROR_KEY] is None
    assert old_runtime.target_registered is False
    assert new_runtime.target_registered is True
    assert new_runtime.operation_kind == "register"
    assert patched_create_client["count"] == 0


def test_shutdown_during_lazy_validation_commits_only_configuration_cache(
    make_app, patched_create_client, monkeypatch
):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    state = app.extensions["nacos"]
    runtime = state["_runtime"]
    entered = threading.Event()
    release = threading.Event()

    def _validate(_cfg, _connection_error):
        entered.set()
        assert release.wait(2)
        return None

    monkeypatch.setattr(nacos, "_registration_config_error", _validate)
    worker = threading.Thread(target=lambda: nacos.register_instance(app))
    worker.start()
    assert entered.wait(2)
    with runtime.state_lock:
        runtime.shutting_down = True
    release.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert state[extension_module._REGISTRATION_ERROR_KEY] is None
    assert runtime.target_registered is False
    assert runtime.operation_generation == 0
    assert runtime.operation_kind is None
    assert patched_create_client["count"] == 0


def test_registration_validation_cache_is_isolated_per_application(
    make_app, patched_create_client
):
    valid_app = make_app({"NACOS_AUTO_REGISTER": False})
    invalid_app = make_app(
        {
            "NACOS_AUTO_REGISTER": False,
            "NACOS_SERVICE_NAME": None,
        }
    )
    valid_nacos = FlaskNacos(valid_app)
    invalid_nacos = FlaskNacos(invalid_app)

    valid_nacos.register_instance(valid_app)
    with pytest.raises(NacosValidationError):
        invalid_nacos.register_instance(invalid_app)

    valid_cache = valid_app.extensions["nacos"][extension_module._REGISTRATION_ERROR_KEY]
    invalid_cache = invalid_app.extensions["nacos"][extension_module._REGISTRATION_ERROR_KEY]
    assert valid_cache is None
    assert isinstance(invalid_cache, NacosValidationError)
