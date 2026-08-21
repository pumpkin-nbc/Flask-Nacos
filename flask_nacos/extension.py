"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
import math
import os
import random
import time
import weakref
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from threading import Event, Lock, RLock, Thread, current_thread
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, has_app_context, request

from . import config as config_module
from . import config_center, discovery, lifecycle, naming
from ._recovery import (
    _classify_lifecycle_failure,
    _LifecycleFailure,
    _LifecycleFailureClass,
    _LifecycleFailureStage,
    _synthetic_lifecycle_failure,
)
from .client import create_client
from .exceptions import FlaskNacosError, NacosConfigError
from .health import HEALTH_ENDPOINT, register_health_route
from .logging import (
    cleanup_sdk_default_handlers,
    configure_logger,
    validate_logging_config,
)
from .retry import run_with_retry
from .utils import validate_retry_interval, validate_retry_times

logger = logging.getLogger("flask_nacos")

EXTENSION_KEY = "nacos"
_OWNER_KEY = "_extension"
_RUNTIME_KEY = "_runtime"
_AUTO_REGISTER_KEY = "_auto_register_enabled"
_REGISTRATION_ERROR_KEY = "_registration_config_error"
_CONNECTION_ERROR_KEY = "_connection_config_error"
_RUNTIME_STALE_KEY = "_runtime_stale"
_RUNTIME_REBUILD_LOCK_KEY = "_runtime_rebuild_lock"
_RUNTIME_REBUILD_PID_KEY = "_runtime_rebuild_pid"
_ATEXIT_REGISTERED_KEY = "_atexit_registered"
_FORK_HOOK_REGISTERED_KEY = "_fork_hook_registered"
_REQUEST_HOOK_REGISTERED_KEY = "_request_hook_registered"

_INIT_LOCK = RLock()
_NAMING_RPC_TIMEOUT_FALLBACK = 3.0
_EXIT_RPC_WAIT_MAX = 5.0
_EXIT_RPC_SCHEDULING_GRACE = 0.25
_LIFECYCLE_RECOVERY_MIN_INTERVAL = 1.0
_LIFECYCLE_RECOVERY_PRIVATE_CAP = 30.0
_LIFECYCLE_WARNING_INTERVAL = 60.0


class _NamingResult(Enum):
    """Private result of one logical Naming SDK call."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class _RegistrationSource(Enum):
    """Identity of the call that entered registration orchestration."""

    EXPLICIT_REGISTER = "explicit_register"
    AUTO_REGISTER = "auto_register"
    PENDING_RECOVERY = "pending_recovery"


_REGISTRATION_SOURCE_CONTEXT: ContextVar[_RegistrationSource] = ContextVar(
    "flask_nacos_registration_source",
    default=_RegistrationSource.EXPLICIT_REGISTER,
)


@dataclass(frozen=True)
class _RegisterContext:
    """Immutable call-local registration metadata."""

    source: _RegistrationSource


@dataclass(frozen=True)
class _RegistrationPolicy:
    """Pure, call-local decisions derived from a registration source."""

    propagate_config_error: bool
    consume_pending: bool
    log_label: str


@dataclass(frozen=True)
class _NamingOutcome:
    """Sanitized result of at most one logical Naming SDK call."""

    result: _NamingResult
    failure: Optional[_LifecycleFailure]
    rpc_executed: bool
    stage: _LifecycleFailureStage


@dataclass
class _WorkerLogState:
    """Worker-local warning throttle; never exposed through Runtime state."""

    direction: Optional[str] = None
    error_type: Optional[str] = None
    last_warning_at: Optional[float] = None
    recovery_announced: bool = False
    recovery_active: bool = False


@dataclass
class _AppRuntimeState:
    """Mutable process-local state for one initialized Flask application."""

    pid: int = field(default_factory=os.getpid)

    client: Any = None
    client_lock: Any = field(default_factory=Lock)

    state_lock: Any = field(default_factory=RLock)
    network_operation_lock: Any = field(default_factory=Lock)

    target_registered: bool = False
    registered: bool = False

    operation_generation: int = 0
    operation_kind: Optional[str] = None
    operation_thread: Any = None
    operation_wakeup: Any = field(default_factory=Event)

    registered_identity: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    shutting_down: bool = False
    auto_register_pending: bool = False

    naming_rpc_active: bool = False
    naming_rpc_seq: int = 0
    naming_rpc_started_at: Optional[float] = None
    naming_rpc_timeout: Optional[float] = None
    naming_rpc_done: Any = None


@dataclass(frozen=True)
class _PendingRegistrationSnapshot:
    """Call-local proof that one PID's pending recovery is still current."""

    runtime: _AppRuntimeState
    pid: int
    generation: int
    target_registered: bool
    operation_kind: Optional[str]
    operation_thread: Any
    shutting_down: bool


class FlaskNacos:
    """Flask extension integrating Nacos discovery and configuration.

    Every initialized application owns an independent state object. Public
    methods use an explicitly supplied application or the current Flask
    context; the extension never falls back to a recently initialized app.
    """

    def __init__(self, app=None) -> None:
        if app is not None:
            self.init_app(app)

    # -- Context-bound properties -----------------------------------------

    @property
    def app(self):
        """Return the current initialized Flask application."""
        app, _, _ = self._require_state()
        return app

    @property
    def client(self) -> Any:
        """Return the current PID's cached client without creating one."""
        _, _, runtime = self._require_state()
        return runtime.client

    @property
    def config(self) -> Dict[str, Any]:
        """Return the current application's immutable configuration snapshot."""
        _, state, _ = self._require_state()
        return state["config"]

    # -- Initialization ----------------------------------------------------

    def init_app(self, app) -> None:
        """Initialize Flask-Nacos for ``app`` without constructing a client."""
        with _INIT_LOCK:
            self._init_app_locked(app)

    def _init_app_locked(self, app) -> None:
        existing = app.extensions.get(EXTENSION_KEY)
        if existing is not None:
            if self._is_owned_state(existing):
                logger.info("FlaskNacos is already initialized for this app; reusing state")
                return
            raise FlaskNacosError('app.extensions["nacos"] is already owned by another extension')

        cfg = config_module.load_config(app)
        validate_logging_config(cfg)

        auto_register_enabled = self._should_auto_register(cfg)
        connection_error = self._connection_config_error(cfg)
        registration_error = (
            self._registration_config_error(cfg, connection_error)
            if auto_register_enabled
            else None
        )

        if connection_error is not None and cfg.get("NACOS_FAIL_FAST", False):
            raise connection_error
        if (
            auto_register_enabled
            and registration_error is not None
            and cfg.get("NACOS_FAIL_FAST", False)
        ):
            raise registration_error

        configure_logger(app, cfg)

        if auto_register_enabled and registration_error is not None:
            logger.error(
                "Automatic Nacos registration is unavailable (error_type=%s, field=%s)",
                type(registration_error).__name__,
                self._registration_error_field(registration_error),
            )

        runtime = self._create_runtime(
            cfg,
            auto_register_enabled=auto_register_enabled,
            registration_error=registration_error,
            fork_rebuild=False,
        )
        current_pid = self._current_pid()
        state: Dict[str, Any] = {
            "config": cfg,
            _OWNER_KEY: self,
            _RUNTIME_KEY: runtime,
            _AUTO_REGISTER_KEY: auto_register_enabled,
            _CONNECTION_ERROR_KEY: connection_error,
            _RUNTIME_STALE_KEY: False,
            _RUNTIME_REBUILD_LOCK_KEY: Lock(),
            _RUNTIME_REBUILD_PID_KEY: current_pid,
            _ATEXIT_REGISTERED_KEY: False,
            _FORK_HOOK_REGISTERED_KEY: False,
            _REQUEST_HOOK_REGISTERED_KEY: False,
        }
        if auto_register_enabled:
            # Key presence is the private three-state cache: absent means not
            # validated, ``None`` means valid, and an exception means invalid.
            state[_REGISTRATION_ERROR_KEY] = registration_error

        try:
            app.extensions[EXTENSION_KEY] = state

            if cfg.get("NACOS_HEALTH_CHECK_ENABLED"):
                register_health_route(app, self)

            self._register_request_recovery_hook(app, state)
            self._register_fork_hook(app, state)
            self._register_atexit(app, state)

            if auto_register_enabled:
                # Automatic and explicit registration intentionally share the
                # same public entry point and atomic preparation logic.
                token = _REGISTRATION_SOURCE_CONTEXT.set(
                    _RegistrationSource.AUTO_REGISTER
                )
                try:
                    self.register_instance(app)
                finally:
                    _REGISTRATION_SOURCE_CONTEXT.reset(token)
        except Exception:
            installed = app.extensions.get(EXTENSION_KEY)
            if installed is state:
                app.extensions.pop(EXTENSION_KEY, None)
            raise

        if not cfg.get("NACOS_ENABLED", True):
            logger.info("Nacos is disabled (NACOS_ENABLED=False)")
        elif not auto_register_enabled:
            logger.info("Automatic Nacos registration on initialization is disabled")

    @staticmethod
    def _should_auto_register(cfg: Dict[str, Any]) -> bool:
        return bool(
            cfg.get("NACOS_ENABLED", True)
            and cfg.get("NACOS_AUTO_REGISTER", True)
        )

    @staticmethod
    def _connection_config_error(cfg: Dict[str, Any]) -> Optional[NacosConfigError]:
        if not cfg.get("NACOS_ENABLED", True):
            return None
        try:
            config_module.validate_connection_config(cfg)
        except NacosConfigError as exc:
            logger.error(
                "Nacos connection configuration is invalid (error_type=%s)",
                type(exc).__name__,
            )
            return exc
        return None

    @staticmethod
    def _registration_config_error(
        cfg: Dict[str, Any], connection_error: Optional[NacosConfigError]
    ) -> Optional[NacosConfigError]:
        if not cfg.get("NACOS_ENABLED", True):
            return None
        if connection_error is not None:
            return connection_error
        try:
            config_module.validate_registration_config(cfg)
            if cfg.get("NACOS_RETRY_ENABLED", True):
                validate_retry_times(cfg.get("NACOS_RETRY_TIMES", 3))
                validate_retry_interval(cfg.get("NACOS_RETRY_INTERVAL", 1.0))
        except NacosConfigError as exc:
            logger.error("Nacos registration configuration is invalid: %s", exc)
            return exc
        return None

    @staticmethod
    def _registration_error_field(error: BaseException) -> str:
        """Return a safe configuration field label for diagnostics."""
        message = str(error)
        for field_name in (
            "NACOS_SERVICE_NAME",
            "NACOS_SERVICE_PORT",
            "NACOS_SERVICE_WEIGHT",
            "NACOS_SERVICE_METADATA",
            "NACOS_SERVICE_EPHEMERAL",
            "NACOS_SERVICE_HEARTBEAT_INTERVAL",
            "NACOS_RETRY_TIMES",
            "NACOS_RETRY_INTERVAL",
            "NACOS_SERVER_ADDR",
            "NACOS_USERNAME",
            "NACOS_PASSWORD",
            "NACOS_ACCESS_KEY",
            "NACOS_SECRET_KEY",
        ):
            if field_name in message:
                return field_name
        return "registration_config"

    def _create_runtime(
        self,
        cfg: Dict[str, Any],
        *,
        auto_register_enabled: bool,
        registration_error: Optional[BaseException],
        fork_rebuild: bool,
    ) -> _AppRuntimeState:
        runtime = _AppRuntimeState(pid=self._current_pid())
        if not cfg.get("NACOS_ENABLED", True):
            return runtime

        if fork_rebuild and auto_register_enabled:
            if registration_error is None:
                runtime.auto_register_pending = True
            else:
                runtime.target_registered = True
                runtime.last_error = type(registration_error).__name__
        return runtime

    # -- Lazy client -------------------------------------------------------

    def get_client(self, app=None) -> Any:
        """Return a usable current-PID client, creating it when necessary."""
        app, state, runtime = self._require_state(app)
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return None

        self._resume_auto_register_if_pending(app, state, runtime)
        try:
            return self._get_or_create_client(state, runtime)
        except Exception as exc:
            logger.error("Failed to create Nacos client (error_type=%s)", type(exc).__name__)
            raise FlaskNacosError("Failed to create Nacos client") from exc

    def _get_or_create_client(self, state: Dict[str, Any], runtime: _AppRuntimeState) -> Any:
        """Create and cache one client without consuming auto-register pending."""
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return None
        if runtime.client is not None:
            return runtime.client

        with runtime.client_lock:
            if runtime.client is not None:
                return runtime.client
            connection_error = state.get(_CONNECTION_ERROR_KEY)
            if connection_error is not None:
                raise connection_error
            config_module.validate_connection_config(cfg)
            client = create_client(cfg)
            cleanup_sdk_default_handlers(cfg)
            runtime.client = client
            return client

    def _client_for_operation(self, app, state: Dict[str, Any], runtime: _AppRuntimeState) -> Any:
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return None
        self._resume_auto_register_if_pending(app, state, runtime)
        try:
            return self._get_or_create_client(state, runtime)
        except Exception as exc:
            logger.error("Nacos client is unavailable (error_type=%s)", type(exc).__name__)
            if cfg.get("NACOS_FAIL_FAST", False):
                raise FlaskNacosError("Failed to create Nacos client") from exc
            return None

    # -- Registration lifecycle ------------------------------------------

    def register_instance(self, app=None) -> None:
        """Set the registration target and start non-blocking convergence."""
        source = _REGISTRATION_SOURCE_CONTEXT.get()
        context = _RegisterContext(source=source)
        self._prepare_registration(app, context, new_command=True)
        return None

    def _prepare_registration(
        self,
        app,
        context: _RegisterContext,
        *,
        new_command: bool,
    ) -> None:
        """Validate, arbitrate, and enter the sole register state transition."""
        while True:
            target_app, state, runtime = self._require_state(app)
            cfg = state["config"]
            if not cfg.get("NACOS_ENABLED", True):
                return

            pending_snapshot: Optional[_PendingRegistrationSnapshot] = None
            with runtime.state_lock:
                if runtime.shutting_down:
                    return
                if context.source is _RegistrationSource.PENDING_RECOVERY:
                    pending_snapshot = self._pending_snapshot_locked(runtime)
                    if pending_snapshot is None:
                        return
                cache_present = _REGISTRATION_ERROR_KEY in state
                registration_error = state.get(_REGISTRATION_ERROR_KEY)

            if not cache_present:
                # This is intentionally outside the lifecycle lock. Validation
                # is deterministic and local: it creates no client or Worker
                # and performs no SDK or network operation.
                candidate = self._registration_config_error(
                    cfg,
                    state.get(_CONNECTION_ERROR_KEY),
                )
                current_app, current_state, current_runtime = self._require_state(
                    target_app
                )
                if (
                    current_state is not state
                    or current_state.get("config") is not cfg
                    or current_runtime is not runtime
                ):
                    continue

                restart = False
                with current_runtime.state_lock:
                    if not self._registration_state_is_current(
                        current_app,
                        current_state,
                        cfg,
                        current_runtime,
                    ):
                        restart = True
                    else:
                        # Compare-and-set: the first completed candidate owns
                        # this app state's immutable validation result.
                        if _REGISTRATION_ERROR_KEY not in current_state:
                            current_state[_REGISTRATION_ERROR_KEY] = candidate
                        registration_error = current_state[_REGISTRATION_ERROR_KEY]
                if restart:
                    continue

            policy = self._registration_policy(context, cfg)
            current_app, current_state, current_runtime = self._require_state(target_app)
            if (
                current_state is not state
                or current_state.get("config") is not cfg
                or current_runtime is not runtime
            ):
                continue

            restart = False
            thread = None
            error_to_raise: Optional[BaseException] = None
            with current_runtime.state_lock:
                if not self._registration_state_is_current(
                    current_app,
                    current_state,
                    cfg,
                    current_runtime,
                ):
                    restart = True
                elif current_runtime.shutting_down:
                    return
                elif policy.consume_pending and not self._pending_snapshot_matches_locked(
                    current_runtime,
                    pending_snapshot,
                ):
                    # The deterministic cache may remain, but a stale pending
                    # recovery must not submit lifecycle state.
                    return
                elif registration_error is not None and policy.propagate_config_error:
                    error_to_raise = registration_error
                else:
                    # Pending handling is source policy, not part of the
                    # lifecycle transition. Both branches finish before the
                    # source-blind state machine is entered.
                    current_runtime.auto_register_pending = False
                    thread, _ = self._prepare_register_locked(
                        current_state,
                        current_runtime,
                        new_command=new_command,
                    )

            if restart:
                continue
            if error_to_raise is not None:
                raise error_to_raise
            self._start_registration_thread(
                current_app,
                current_state,
                current_runtime,
                thread,
            )
            return

    @staticmethod
    def _registration_policy(
        context: _RegisterContext,
        cfg: Dict[str, Any],
    ) -> _RegistrationPolicy:
        """Return immutable entry behavior without touching lifecycle state."""
        source = context.source
        return _RegistrationPolicy(
            propagate_config_error=bool(
                cfg.get("NACOS_FAIL_FAST", False)
                and source is not _RegistrationSource.PENDING_RECOVERY
            ),
            consume_pending=source is _RegistrationSource.PENDING_RECOVERY,
            log_label=source.value,
        )

    def _registration_state_is_current(
        self,
        app,
        state: Dict[str, Any],
        cfg: Dict[str, Any],
        runtime: _AppRuntimeState,
    ) -> bool:
        """Return whether call-local objects still own the current app/PID."""
        return bool(
            app.extensions.get(EXTENSION_KEY) is state
            and state.get(_OWNER_KEY) is self
            and state.get("config") is cfg
            and state.get(_RUNTIME_KEY) is runtime
            and not state.get(_RUNTIME_STALE_KEY, False)
            and runtime.pid == self._current_pid()
        )

    @staticmethod
    def _pending_snapshot_locked(
        runtime: _AppRuntimeState,
    ) -> Optional[_PendingRegistrationSnapshot]:
        if runtime.shutting_down or not runtime.auto_register_pending:
            return None
        return _PendingRegistrationSnapshot(
            runtime=runtime,
            pid=runtime.pid,
            generation=runtime.operation_generation,
            target_registered=runtime.target_registered,
            operation_kind=runtime.operation_kind,
            operation_thread=runtime.operation_thread,
            shutting_down=runtime.shutting_down,
        )

    @staticmethod
    def _pending_snapshot_matches_locked(
        runtime: _AppRuntimeState,
        snapshot: Optional[_PendingRegistrationSnapshot],
    ) -> bool:
        return bool(
            snapshot is not None
            and snapshot.runtime is runtime
            and snapshot.pid == runtime.pid
            and snapshot.generation == runtime.operation_generation
            and snapshot.target_registered == runtime.target_registered
            and snapshot.operation_kind == runtime.operation_kind
            and snapshot.operation_thread is runtime.operation_thread
            and snapshot.shutting_down == runtime.shutting_down
            and not runtime.shutting_down
            and runtime.auto_register_pending
        )

    def _prepare_register_locked(
        self,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        *,
        new_command: bool,
    ) -> Tuple[Any, Optional[BaseException]]:
        """Prepare one register Worker while ``runtime.state_lock`` is held."""
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return None, None
        if runtime.shutting_down:
            return None, None

        target_changed = not runtime.target_registered
        if target_changed:
            runtime.target_registered = True
            runtime.operation_generation += 1
            runtime.operation_wakeup.set()

        if runtime.registered:
            runtime.last_error = None
            return None, None

        registration_error = state.get(_REGISTRATION_ERROR_KEY)
        if registration_error is not None:
            runtime.last_error = type(registration_error).__name__
            return None, registration_error

        if runtime.operation_kind is not None:
            return None, None

        if new_command and not target_changed:
            # Any new registration command retries an unmet idle target. The
            # transition is deliberately identical for all call sources.
            runtime.operation_generation += 1
            runtime.operation_wakeup.set()

        try:
            thread = Thread(
                target=self._registration_worker,
                args=(state, runtime),
                name="flask-nacos-registration",
                daemon=True,
            )
        except Exception as exc:
            if runtime.target_registered and not runtime.registered:
                runtime.last_error = "ThreadCreateError"
            logger.error(
                "Failed to create Nacos registration thread (error_type=%s)",
                type(exc).__name__,
            )
            return None, None

        runtime.operation_kind = "register"
        runtime.operation_thread = thread
        runtime.last_error = None
        return thread, None

    def _start_registration_thread(
        self,
        app,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        thread: Any,
    ) -> None:
        del app, state
        if thread is None:
            return
        try:
            thread.start()
        except Exception as exc:
            with runtime.state_lock:
                if runtime.operation_thread is thread:
                    runtime.operation_thread = None
                    if runtime.operation_kind == "register":
                        runtime.operation_kind = None
                    if (
                        runtime.target_registered
                        and not runtime.registered
                        and not runtime.shutting_down
                    ):
                        runtime.last_error = "ThreadStartError"
                    elif runtime.registered == runtime.target_registered:
                        runtime.last_error = None
            logger.error(
                "Failed to start Nacos registration thread (error_type=%s)",
                type(exc).__name__,
            )

    def _registration_worker(self, state: Dict[str, Any], runtime: _AppRuntimeState) -> None:
        """Converge ``registered`` toward the latest target, then exit."""
        worker = current_thread()
        cfg = state["config"]
        retry_enabled = bool(cfg.get("NACOS_RETRY_ENABLED", True))
        max_attempts = (
            validate_retry_times(cfg.get("NACOS_RETRY_TIMES", 3)) if retry_enabled else 1
        )
        retry_interval = (
            validate_retry_interval(cfg.get("NACOS_RETRY_INTERVAL", 1.0))
            if retry_enabled
            else 0.0
        )
        direction: Optional[str] = None
        finite_attempts = 0
        recovery_round = 0
        client: Any = None
        register_identity: Optional[Dict[str, Any]] = None
        log_state = _WorkerLogState()

        try:
            while True:
                with runtime.state_lock:
                    owns_operation = bool(
                        runtime.operation_kind == "register" and runtime.operation_thread is worker
                    )
                    if not owns_operation or runtime.shutting_down:
                        return
                    if runtime.registered == runtime.target_registered:
                        runtime.last_error = None
                        return
                    needed = "register" if runtime.target_registered else "deregister"

                if direction != needed:
                    direction = needed
                    finite_attempts = 0
                    recovery_round = 0
                    log_state = _WorkerLogState(direction=needed)
                    if direction == "register":
                        register_identity = None

                if recovery_round > 0:
                    recovery_delay = self._lifecycle_recovery_delay(
                        retry_interval, recovery_round
                    )
                    if not self._interruptible_retry_wait(
                        runtime, worker, recovery_delay
                    ):
                        continue
                    with runtime.state_lock:
                        if (
                            runtime.operation_thread is not worker
                            or runtime.operation_kind != "register"
                            or runtime.shutting_down
                            or runtime.registered == runtime.target_registered
                        ):
                            if runtime.registered == runtime.target_registered:
                                runtime.last_error = None
                            continue
                        latest_needed = (
                            "register" if runtime.target_registered else "deregister"
                        )
                    if latest_needed != needed:
                        continue

                # The first gate deliberately happens before client creation.
                with runtime.state_lock:
                    if (
                        runtime.operation_thread is not worker
                        or runtime.operation_kind != "register"
                        or runtime.shutting_down
                        or runtime.registered == runtime.target_registered
                        or (needed == "register" and not runtime.target_registered)
                        or (needed == "deregister" and runtime.target_registered)
                    ):
                        if runtime.registered == runtime.target_registered:
                            runtime.last_error = None
                        continue

                client_attempted = False
                failure_stage = _LifecycleFailureStage.CLIENT_CREATE
                try:
                    if client is None:
                        client_attempted = True
                        client = self._get_or_create_client(state, runtime)
                    if needed == "register" and register_identity is None:
                        failure_stage = _LifecycleFailureStage.REGISTRATION_PREPARE
                        register_identity = naming.resolve_instance_identity(cfg)
                except Exception as exc:
                    failure = self._classify_lifecycle_failure(
                        exc,
                        stage=failure_stage,
                        direction=needed,
                    )
                    action, finite_attempts, recovery_round = self._handle_worker_failure(
                        runtime,
                        worker,
                        needed,
                        failure,
                        finite_attempts=finite_attempts,
                        recovery_round=recovery_round,
                        retry_enabled=retry_enabled,
                        max_attempts=max_attempts,
                        real_recovery_attempt=bool(
                            client_attempted
                            and failure_stage is _LifecycleFailureStage.CLIENT_CREATE
                        ),
                        log_state=log_state,
                    )
                    if action == "stop":
                        return
                    if action == "finite_wait":
                        self._interruptible_retry_wait(runtime, worker, retry_interval)
                    continue

                stage = (
                    _LifecycleFailureStage.REGISTER_RPC
                    if needed == "register"
                    else _LifecycleFailureStage.COMPENSATING_DEREGISTER_RPC
                )
                outcome = self._execute_naming_rpc(
                    state,
                    runtime,
                    needed,
                    client,
                    identity=register_identity,
                    allow_during_shutdown=False,
                    record_lifecycle_error=True,
                    stage=stage,
                    log_failure=False,
                )

                with runtime.state_lock:
                    converged = runtime.registered == runtime.target_registered
                    if converged:
                        runtime.last_error = None
                    shutting_down = runtime.shutting_down
                    latest_needed = "register" if runtime.target_registered else "deregister"

                if converged:
                    if outcome.result is _NamingResult.SUCCEEDED and recovery_round > 0:
                        self._log_worker_recovered(needed, log_state)
                    return
                if shutting_down:
                    return

                if outcome.result is _NamingResult.FAILED and latest_needed == needed:
                    failure = outcome.failure or _synthetic_lifecycle_failure(
                        "NamingFailure"
                    )
                    action, finite_attempts, recovery_round = self._handle_worker_failure(
                        runtime,
                        worker,
                        needed,
                        failure,
                        finite_attempts=finite_attempts,
                        recovery_round=recovery_round,
                        retry_enabled=retry_enabled,
                        max_attempts=max_attempts,
                        real_recovery_attempt=outcome.rpc_executed,
                        log_state=log_state,
                    )
                    if action == "stop":
                        return
                    if action == "finite_wait":
                        self._interruptible_retry_wait(runtime, worker, retry_interval)
                    continue

                # SUCCEEDED or SKIPPED always causes a fresh target read. A
                # target change also resets the attempt budget for its direction.
                if latest_needed != needed:
                    direction = None
                elif outcome.result is _NamingResult.SUCCEEDED:
                    finite_attempts = 0
                    recovery_round = 0
                if needed == "deregister" and outcome.result is _NamingResult.SUCCEEDED:
                    register_identity = None
        except Exception as exc:
            failure = self._classify_lifecycle_failure(
                exc,
                stage=_LifecycleFailureStage.REGISTRATION_PREPARE,
                direction=direction or "register",
            )
            self._record_lifecycle_failure(runtime, direction or "register", failure)
            logger.error(
                "Nacos registration Worker stopped (error_type=%s)",
                failure.safe_error_type,
            )
        finally:
            with runtime.state_lock:
                if runtime.operation_thread is worker:
                    runtime.operation_thread = None
                    if runtime.operation_kind == "register":
                        runtime.operation_kind = None
                    if runtime.registered == runtime.target_registered:
                        runtime.last_error = None

    def _handle_worker_failure(
        self,
        runtime: _AppRuntimeState,
        worker: Any,
        direction: str,
        failure: _LifecycleFailure,
        *,
        finite_attempts: int,
        recovery_round: int,
        retry_enabled: bool,
        max_attempts: int,
        real_recovery_attempt: bool,
        log_state: _WorkerLogState,
    ) -> Tuple[str, int, int]:
        """Apply one classified failure to the direction-local retry phase."""
        self._record_lifecycle_failure(runtime, direction, failure)
        with runtime.state_lock:
            if (
                runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
                or runtime.shutting_down
                or runtime.registered == runtime.target_registered
            ):
                if runtime.registered == runtime.target_registered:
                    runtime.last_error = None
                return "stop", finite_attempts, recovery_round
            latest = "register" if runtime.target_registered else "deregister"
            if latest != direction:
                return "reevaluate", finite_attempts, recovery_round

        if recovery_round > 0:
            if failure.failure_class is not _LifecycleFailureClass.TRANSIENT:
                self._log_worker_failure(
                    direction, failure, log_state, entering_recovery=False
                )
                return "stop", finite_attempts, recovery_round
            if real_recovery_attempt:
                recovery_round += 1
            self._log_worker_failure(
                direction, failure, log_state, entering_recovery=False
            )
            return "recovery", finite_attempts, recovery_round

        finite_attempts += 1
        if failure.failure_class is _LifecycleFailureClass.DETERMINISTIC:
            self._log_worker_failure(
                direction, failure, log_state, entering_recovery=False
            )
            return "stop", finite_attempts, recovery_round
        if not retry_enabled:
            self._log_worker_failure(
                direction, failure, log_state, entering_recovery=False
            )
            return "stop", finite_attempts, recovery_round
        if finite_attempts < max_attempts:
            self._log_worker_failure(
                direction, failure, log_state, entering_recovery=False
            )
            return "finite_wait", finite_attempts, recovery_round
        if failure.failure_class is _LifecycleFailureClass.TRANSIENT:
            recovery_round = 1
            log_state.recovery_active = True
            self._log_worker_failure(
                direction, failure, log_state, entering_recovery=True
            )
            return "recovery", finite_attempts, recovery_round

        self._log_worker_failure(direction, failure, log_state, entering_recovery=False)
        return "stop", finite_attempts, recovery_round

    @staticmethod
    def _lifecycle_recovery_delay(retry_interval: float, recovery_round: int) -> float:
        base = max(retry_interval, _LIFECYCLE_RECOVERY_MIN_INTERVAL)
        if base < _LIFECYCLE_RECOVERY_PRIVATE_CAP:
            raw = min(
                base * (2 ** min(recovery_round, 5)),
                _LIFECYCLE_RECOVERY_PRIVATE_CAP,
            )
            lower = max(base, raw * 0.8)
            return random.uniform(lower, raw)
        return random.uniform(base, base * 1.2)

    @staticmethod
    def _interruptible_retry_wait(
        runtime: _AppRuntimeState, worker: Any, retry_interval: float
    ) -> bool:
        """Wait without losing wakeups; return true only after a full timeout."""
        with runtime.state_lock:
            generation = runtime.operation_generation
            target = runtime.target_registered
            if (
                runtime.shutting_down
                or runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
            ):
                return False

        runtime.operation_wakeup.clear()

        with runtime.state_lock:
            if (
                runtime.shutting_down
                or runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
                or runtime.operation_generation != generation
                or runtime.target_registered != target
            ):
                return False

        return not runtime.operation_wakeup.wait(retry_interval)

    @staticmethod
    def _record_lifecycle_failure(
        runtime: _AppRuntimeState, direction: str, failure: _LifecycleFailure
    ) -> None:
        with runtime.state_lock:
            if direction == "register":
                relevant = runtime.target_registered and not runtime.registered
            else:
                relevant = not runtime.target_registered and runtime.registered
            if relevant and not runtime.shutting_down:
                runtime.last_error = failure.safe_error_type
            elif runtime.registered == runtime.target_registered:
                runtime.last_error = None

    @staticmethod
    def _log_worker_failure(
        direction: str,
        failure: _LifecycleFailure,
        log_state: _WorkerLogState,
        *,
        entering_recovery: bool,
    ) -> None:
        now = time.monotonic()
        changed = bool(
            log_state.direction != direction
            or log_state.error_type != failure.safe_error_type
        )
        interval_elapsed = bool(
            log_state.last_warning_at is None
            or now - log_state.last_warning_at >= _LIFECYCLE_WARNING_INTERVAL
        )
        warning_due = changed or interval_elapsed or (
            entering_recovery and not log_state.recovery_announced
        )
        if warning_due:
            phase = "recovery" if entering_recovery or log_state.recovery_active else "finite"
            logger.warning(
                "Nacos lifecycle attempt failed "
                "(operation=%s, error_type=%s, failure_class=%s, phase=%s)",
                direction,
                failure.safe_error_type,
                failure.failure_class.value,
                phase,
            )
            log_state.last_warning_at = now
        else:
            logger.debug(
                "Nacos lifecycle attempt still failing "
                "(operation=%s, error_type=%s, failure_class=%s)",
                direction,
                failure.safe_error_type,
                failure.failure_class.value,
            )
        log_state.direction = direction
        log_state.error_type = failure.safe_error_type
        if entering_recovery:
            log_state.recovery_announced = True

    @staticmethod
    def _log_worker_recovered(direction: str, log_state: _WorkerLogState) -> None:
        if not log_state.recovery_active:
            return
        logger.info(
            "Nacos lifecycle recovered after transient failures (operation=%s)",
            direction,
        )
        log_state.recovery_active = False

    @staticmethod
    def _classify_lifecycle_failure(
        exc: BaseException,
        *,
        stage: _LifecycleFailureStage,
        direction: str,
    ) -> _LifecycleFailure:
        return _classify_lifecycle_failure(exc, stage=stage, direction=direction)

    # -- Deregistration lifecycle ----------------------------------------

    def deregister_instance(self, app=None) -> bool:
        """Set the unregistered target and synchronously clean an idle instance."""
        app, state, runtime = self._require_state(app)
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return True

        wake_worker = False
        with runtime.state_lock:
            runtime.auto_register_pending = False
            if runtime.shutting_down:
                return True

            if runtime.target_registered:
                runtime.target_registered = False
                runtime.operation_generation += 1
                wake_worker = True

            if runtime.operation_kind is not None:
                accepted = True
                run_sync = False
            elif not runtime.registered:
                runtime.last_error = None
                accepted = True
                run_sync = False
            else:
                runtime.operation_kind = "deregister"
                runtime.operation_thread = None
                accepted = False
                run_sync = True

        if wake_worker:
            runtime.operation_wakeup.set()
        if not run_sync:
            return accepted

        outcome = _NamingOutcome(
            _NamingResult.FAILED,
            _synthetic_lifecycle_failure("DeregisterRuntimeError"),
            False,
            _LifecycleFailureStage.SYNC_DEREGISTER_RPC,
        )
        try:
            outcome = self._execute_naming_rpc(
                state,
                runtime,
                "deregister",
                runtime.client,
                identity=None,
                allow_during_shutdown=False,
                record_lifecycle_error=True,
                stage=_LifecycleFailureStage.SYNC_DEREGISTER_RPC,
                log_failure=True,
            )
        except Exception as exc:  # defensive: runtime errors never escape
            failure = self._classify_lifecycle_failure(
                exc,
                stage=_LifecycleFailureStage.SYNC_DEREGISTER_RPC,
                direction="deregister",
            )
            self._record_lifecycle_failure(runtime, "deregister", failure)
            outcome = _NamingOutcome(
                _NamingResult.FAILED,
                failure,
                False,
                _LifecycleFailureStage.SYNC_DEREGISTER_RPC,
            )
        finally:
            schedule_register = False
            with runtime.state_lock:
                if runtime.operation_kind == "deregister" and runtime.operation_thread is None:
                    runtime.operation_kind = None
                if runtime.registered == runtime.target_registered:
                    runtime.last_error = None
                schedule_register = bool(
                    not runtime.shutting_down
                    and runtime.target_registered
                    and not runtime.registered
                    and runtime.operation_kind is None
                )

            if schedule_register:
                with runtime.state_lock:
                    thread, _ = self._prepare_register_locked(
                        state,
                        runtime,
                        new_command=False,
                    )
                self._start_registration_thread(app, state, runtime, thread)

        return outcome.result is not _NamingResult.FAILED

    # -- Unified Naming RPC infrastructure --------------------------------

    def _execute_naming_rpc(
        self,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        rpc_type: str,
        client: Any,
        *,
        identity: Optional[Dict[str, Any]],
        allow_during_shutdown: bool,
        record_lifecycle_error: bool,
        stage: Optional[_LifecycleFailureStage] = None,
        log_failure: bool = True,
    ) -> _NamingOutcome:
        """Execute at most one logical Naming RPC with tri-state semantics."""
        if stage is None:
            stage = self._default_naming_stage(rpc_type, allow_during_shutdown)
        rpc_done: Any = None
        rpc_seq: Optional[int] = None
        rpc_executed = False
        lock_acquired = False
        outcome = _NamingOutcome(
            _NamingResult.FAILED,
            _synthetic_lifecycle_failure("NamingInfrastructureError"),
            False,
            stage,
        )
        network_lock = runtime.network_operation_lock
        try:
            network_lock.acquire()
            lock_acquired = True
            with runtime.state_lock:
                gate = self._naming_rpc_gate_locked(runtime, rpc_type, allow_during_shutdown)
                if gate is _NamingResult.SKIPPED:
                    return _NamingOutcome(gate, None, False, stage)

                actual_identity = identity
                if rpc_type == "deregister":
                    actual_identity = runtime.registered_identity

                if actual_identity is None:
                    missing_error_type = (
                        "MissingRegisteredIdentity"
                        if rpc_type == "deregister"
                        else "MissingRegistrationIdentity"
                    )
                    failure = _synthetic_lifecycle_failure(
                        missing_error_type,
                        _LifecycleFailureClass.DETERMINISTIC,
                    )
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(
                            runtime, rpc_type, failure.safe_error_type
                        )
                    return _NamingOutcome(_NamingResult.FAILED, failure, False, stage)
                if client is None:
                    failure = _synthetic_lifecycle_failure(
                        "ClientUnavailable",
                        _LifecycleFailureClass.DETERMINISTIC,
                    )
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(
                            runtime, rpc_type, failure.safe_error_type
                        )
                    return _NamingOutcome(_NamingResult.FAILED, failure, False, stage)

            try:
                rpc_done = Event()
            except Exception as exc:
                classified = self._classify_lifecycle_failure(
                    exc,
                    stage=stage,
                    direction=rpc_type,
                )
                failure = _synthetic_lifecycle_failure(
                    "NamingEventCreateError", classified.failure_class
                )
                with runtime.state_lock:
                    gate = self._naming_rpc_gate_locked(
                        runtime, rpc_type, allow_during_shutdown
                    )
                    if gate is _NamingResult.SKIPPED:
                        return _NamingOutcome(gate, None, False, stage)
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(
                            runtime, rpc_type, failure.safe_error_type
                        )
                logger.error(
                    "Failed to create Naming RPC event (error_type=%s)",
                    classified.safe_error_type,
                )
                return _NamingOutcome(_NamingResult.FAILED, failure, False, stage)

            with runtime.state_lock:
                gate = self._naming_rpc_gate_locked(runtime, rpc_type, allow_during_shutdown)
                if gate is _NamingResult.SKIPPED:
                    return _NamingOutcome(gate, None, False, stage)
                runtime.naming_rpc_seq += 1
                rpc_seq = runtime.naming_rpc_seq
                runtime.naming_rpc_active = True
                runtime.naming_rpc_done = rpc_done
                runtime.naming_rpc_started_at = time.monotonic()
                runtime.naming_rpc_timeout = self._naming_timeout_seconds(state["config"])

            rpc_failure: Optional[_LifecycleFailure] = None
            try:
                rpc_executed = True
                if rpc_type == "register":
                    naming.register_instance(client, state["config"], identity=actual_identity)
                elif rpc_type == "deregister":
                    naming.deregister_instance(client, state["config"], identity=actual_identity)
                else:
                    raise RuntimeError("UnsupportedNamingOperation")
                outcome = _NamingOutcome(_NamingResult.SUCCEEDED, None, True, stage)
            except Exception as exc:
                rpc_failure = self._classify_lifecycle_failure(
                    exc,
                    stage=stage,
                    direction=rpc_type,
                )
                outcome = _NamingOutcome(
                    _NamingResult.FAILED,
                    rpc_failure,
                    rpc_executed,
                    stage,
                )
                if log_failure:
                    logger.warning(
                        "Nacos Naming RPC failed "
                        "(operation=%s, error_type=%s, failure_class=%s)",
                        rpc_type,
                        rpc_failure.safe_error_type,
                        rpc_failure.failure_class.value,
                    )

            try:
                with runtime.state_lock:
                    if outcome.result is _NamingResult.SUCCEEDED:
                        if rpc_type == "register":
                            committed_identity = dict(actual_identity)
                            runtime.registered_identity = committed_identity
                            runtime.registered = True
                        else:
                            runtime.registered = False
                            runtime.registered_identity = None
                        runtime.last_error = None
                    elif record_lifecycle_error and rpc_failure is not None:
                        self._record_rpc_error_locked(
                            runtime, rpc_type, rpc_failure.safe_error_type
                        )
            except Exception as exc:
                commit_failure = _synthetic_lifecycle_failure("NamingResultCommitError")
                outcome = _NamingOutcome(
                    _NamingResult.FAILED,
                    commit_failure,
                    rpc_executed,
                    stage,
                )
                with runtime.state_lock:
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(
                            runtime, rpc_type, commit_failure.safe_error_type
                        )
                logger.error(
                    "Failed to commit Naming RPC result (error_type=%s)",
                    type(exc).__name__,
                )
            return outcome
        except Exception as exc:
            failure = self._classify_lifecycle_failure(
                exc,
                stage=stage,
                direction=rpc_type,
            )
            with runtime.state_lock:
                if record_lifecycle_error:
                    self._record_rpc_error_locked(
                        runtime, rpc_type, failure.safe_error_type
                    )
            logger.error(
                "Naming RPC infrastructure failed (operation=%s, error_type=%s)",
                rpc_type,
                failure.safe_error_type,
            )
            return _NamingOutcome(
                _NamingResult.FAILED,
                failure,
                rpc_executed,
                stage,
            )
        finally:
            try:
                if lock_acquired:
                    network_lock.release()
            finally:
                if rpc_done is not None:
                    try:
                        with runtime.state_lock:
                            if runtime.naming_rpc_seq == rpc_seq:
                                runtime.naming_rpc_active = False
                                runtime.naming_rpc_started_at = None
                                runtime.naming_rpc_timeout = None
                                runtime.naming_rpc_done = None
                    finally:
                        rpc_done.set()

    @staticmethod
    def _default_naming_stage(
        rpc_type: str, allow_during_shutdown: bool
    ) -> _LifecycleFailureStage:
        if rpc_type == "register":
            return _LifecycleFailureStage.REGISTER_RPC
        if allow_during_shutdown:
            return _LifecycleFailureStage.EXIT_DEREGISTER_RPC
        return _LifecycleFailureStage.SYNC_DEREGISTER_RPC

    @staticmethod
    def _naming_rpc_gate_locked(
        runtime: _AppRuntimeState, rpc_type: str, allow_during_shutdown: bool
    ) -> _NamingResult:
        if rpc_type == "register":
            needed = bool(
                not runtime.shutting_down and runtime.target_registered and not runtime.registered
            )
        elif rpc_type == "deregister" and allow_during_shutdown:
            needed = bool(runtime.shutting_down and runtime.registered)
        elif rpc_type == "deregister":
            needed = bool(
                not runtime.shutting_down and not runtime.target_registered and runtime.registered
            )
        else:
            needed = False
        return _NamingResult.FAILED if needed else _NamingResult.SKIPPED

    @staticmethod
    def _record_rpc_error_locked(runtime: _AppRuntimeState, rpc_type: str, error_type: str) -> None:
        if rpc_type == "register":
            relevant = runtime.target_registered and not runtime.registered
        else:
            relevant = not runtime.target_registered and runtime.registered
        if relevant and not runtime.shutting_down:
            runtime.last_error = error_type
        elif runtime.registered == runtime.target_registered:
            runtime.last_error = None

    @staticmethod
    def _naming_timeout_seconds(cfg: Dict[str, Any]) -> Optional[float]:
        value = cfg.get("NACOS_REQUEST_TIMEOUT")
        if value is None or isinstance(value, bool):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(parsed) or parsed <= 0:
            return None
        return parsed

    # -- Discovery and configuration center -------------------------------

    def list_instances(
        self,
        service_name: str,
        group: Optional[str] = None,
        healthy_only: bool = True,
        cluster: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return instances for ``service_name`` using the current app."""
        app, state, runtime = self._require_state()
        cfg = state["config"]
        client = self._client_for_operation(app, state, runtime)
        if client is None:
            return []
        if cluster is None:
            cluster = cfg.get("NACOS_DISCOVERY_CLUSTER")
        if metadata is None:
            metadata = cfg.get("NACOS_DISCOVERY_METADATA") or {}
        result = self._safe(
            lambda: naming.list_instances(
                client,
                cfg,
                service_name,
                group=group,
                healthy_only=healthy_only,
                cluster=cluster,
                metadata=metadata,
            ),
            cfg,
            "Service discovery failed",
            default=[],
        )
        return result if result is not None else []

    def get_one_healthy_instance(
        self,
        service_name: str,
        group: Optional[str] = None,
        strategy: Optional[str] = None,
        cluster: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return one healthy instance using the configured strategy."""
        _, state, _ = self._require_state()
        cfg = state["config"]
        instances = self.list_instances(
            service_name,
            group=group,
            healthy_only=True,
            cluster=cluster,
            metadata=metadata,
        )
        strategy_name = strategy or cfg.get("NACOS_DISCOVERY_STRATEGY", "first")
        return self._safe(
            lambda: discovery.select_instance(instances, strategy_name),
            cfg,
            "Failed to select a healthy instance",
            default=None,
            retry=False,
        )

    def normalize_instance(self, instance: Any) -> Optional[Dict[str, Any]]:
        """Convert a Nacos SDK instance into a standard dict (or ``None``)."""
        try:
            return discovery.normalize_instance(instance)
        except Exception as exc:
            logger.warning("Instance normalization failed (error_type=%s)", type(exc).__name__)
            return None

    def get_config(
        self, data_id: Optional[str] = None, group: Optional[str] = None
    ) -> Optional[str]:
        """Fetch raw configuration content for the current application."""
        app, state, runtime = self._require_state()
        cfg = state["config"]
        if not cfg.get("NACOS_CONFIG_ENABLED", True):
            logger.info("Nacos config center is disabled (NACOS_CONFIG_ENABLED=False)")
            return None
        client = self._client_for_operation(app, state, runtime)
        if client is None:
            return None
        effective_data_id = data_id or cfg.get("NACOS_CONFIG_DATA_ID")
        return self._safe(
            lambda: config_center.get_config(client, cfg, effective_data_id, group=group),
            cfg,
            "Failed to get config from Nacos",
            default=None,
        )

    # -- Local status and health support ----------------------------------

    def get_status(self, app=None) -> Dict[str, Any]:
        """Return the fixed local lifecycle snapshot without SDK side effects."""
        _, state, runtime = self._require_state(app)
        cfg = state["config"]
        with runtime.state_lock:
            enabled = bool(cfg.get("NACOS_ENABLED", True))
            identity = (
                dict(runtime.registered_identity)
                if runtime.registered and runtime.registered_identity is not None
                else None
            )
            target_registered = runtime.target_registered if enabled else False
            registered = runtime.registered if enabled else False
            operation_running = bool(runtime.operation_kind is not None) if enabled else False
            last_error = runtime.last_error if enabled else None
            pid = runtime.pid
            client_created = bool(runtime.client is not None) if enabled else False

        if identity is None:
            service_name = cfg.get("NACOS_SERVICE_NAME")
            group_name = cfg.get("NACOS_SERVICE_GROUP") or "DEFAULT_GROUP"
            cluster_name = cfg.get("NACOS_SERVICE_CLUSTER") or "DEFAULT"
            service_ip = cfg.get("NACOS_SERVICE_IP")
            service_port = cfg.get("NACOS_SERVICE_PORT")
        else:
            service_name = identity.get("service_name")
            group_name = identity.get("group_name")
            cluster_name = identity.get("cluster_name")
            service_ip = identity.get("ip")
            service_port = identity.get("port")

        return {
            "enabled": enabled,
            "pid": pid,
            "client_created": client_created,
            "service_name": service_name,
            "group_name": group_name,
            "cluster_name": cluster_name,
            "service_ip": service_ip,
            "service_port": service_port,
            "target_registered": target_registered,
            "registered": registered,
            "operation_running": operation_running,
            "last_error": last_error,
        }

    # -- Fork recovery -----------------------------------------------------

    def _register_fork_hook(self, app, state: Dict[str, Any]) -> None:
        if state.get(_FORK_HOOK_REGISTERED_KEY):
            return
        register_at_fork = getattr(os, "register_at_fork", None)
        if register_at_fork is None:
            return

        extension_ref = weakref.ref(self)
        app_ref = weakref.ref(app)

        def _after_in_child() -> None:
            extension = extension_ref()
            target_app = app_ref()
            if extension is None or target_app is None:
                return
            target_state = target_app.extensions.get(EXTENSION_KEY)
            if not extension._is_owned_state(target_state):
                return
            target_state[_RUNTIME_STALE_KEY] = True
            target_state[_RUNTIME_REBUILD_LOCK_KEY] = Lock()
            target_state[_RUNTIME_REBUILD_PID_KEY] = extension._current_pid()

        register_at_fork(after_in_child=_after_in_child)
        state[_FORK_HOOK_REGISTERED_KEY] = True

    def _ensure_current_runtime(self, state: Dict[str, Any]) -> _AppRuntimeState:
        current_pid = self._current_pid()
        runtime = state[_RUNTIME_KEY]
        if not state.get(_RUNTIME_STALE_KEY, False) and runtime.pid == current_pid:
            return runtime

        # The child hook replaces this lock before any child thread can use it.
        # The fallback covers PID simulation and platforms without fork hooks.
        if state.get(_RUNTIME_REBUILD_PID_KEY) != current_pid:
            # A real fork uses the child hook above and never touches an
            # inherited lock. This guarded fallback covers PID simulation and
            # platforms where a process cannot fork.
            with _INIT_LOCK:
                if state.get(_RUNTIME_REBUILD_PID_KEY) != current_pid:
                    state[_RUNTIME_REBUILD_LOCK_KEY] = Lock()
                    state[_RUNTIME_REBUILD_PID_KEY] = current_pid
        rebuild_lock = state[_RUNTIME_REBUILD_LOCK_KEY]
        with rebuild_lock:
            runtime = state[_RUNTIME_KEY]
            if state.get(_RUNTIME_STALE_KEY, False) or runtime.pid != current_pid:
                runtime = self._create_runtime(
                    state["config"],
                    auto_register_enabled=state[_AUTO_REGISTER_KEY],
                    registration_error=state.get(_REGISTRATION_ERROR_KEY),
                    fork_rebuild=True,
                )
                state[_RUNTIME_KEY] = runtime
                state[_RUNTIME_STALE_KEY] = False
            return runtime

    def _resume_auto_register_if_pending(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> None:
        del state
        with runtime.state_lock:
            if runtime.shutting_down or not runtime.auto_register_pending:
                return
        self._prepare_registration(
            app,
            _RegisterContext(source=_RegistrationSource.PENDING_RECOVERY),
            new_command=True,
        )

    def _register_request_recovery_hook(self, app, state: Dict[str, Any]) -> None:
        if state.get(_REQUEST_HOOK_REGISTERED_KEY):
            return
        extension_ref = weakref.ref(self)

        def _resume_after_fork_request():
            extension = extension_ref()
            if extension is None:
                return None
            target_app = current_app._get_current_object()
            target_state = target_app.extensions.get(EXTENSION_KEY)
            if not extension._is_owned_state(target_state):
                return None
            runtime = extension._ensure_current_runtime(target_state)
            if request.endpoint == HEALTH_ENDPOINT:
                return None
            extension._resume_auto_register_if_pending(target_app, target_state, runtime)
            return None

        app.before_request(_resume_after_fork_request)
        state[_REQUEST_HOOK_REGISTERED_KEY] = True

    # -- Process exit ------------------------------------------------------

    def _register_atexit(self, app, state: Dict[str, Any]) -> None:
        if state.get(_ATEXIT_REGISTERED_KEY):
            return
        extension_ref = weakref.ref(self)
        app_ref = weakref.ref(app)

        def _handler() -> None:
            extension = extension_ref()
            target_app = app_ref()
            if extension is None or target_app is None:
                return
            target_state = target_app.extensions.get(EXTENSION_KEY)
            if not extension._is_owned_state(target_state):
                return
            runtime = extension._ensure_current_runtime(target_state)
            extension._atexit_handler_for(target_app, target_state, runtime)

        atexit.register(_handler)
        state[_ATEXIT_REGISTERED_KEY] = True

    def _atexit_handler(self, app=None) -> None:
        """Run best-effort exit cleanup for an explicit/current application."""
        try:
            app, state, runtime = self._require_state(app)
        except FlaskNacosError:
            return
        self._atexit_handler_for(app, state, runtime)

    def _atexit_handler_for(self, app, state: Dict[str, Any], runtime: _AppRuntimeState) -> None:
        del app
        if runtime.pid != self._current_pid():
            return

        with runtime.state_lock:
            if runtime.shutting_down:
                return
            runtime.shutting_down = True
            rpc_active = runtime.naming_rpc_active
            rpc_seq = runtime.naming_rpc_seq
            rpc_done = runtime.naming_rpc_done
            rpc_started_at = runtime.naming_rpc_started_at
            rpc_timeout = runtime.naming_rpc_timeout
            registered = runtime.registered
            registered_identity = runtime.registered_identity

        # These values form the atomic snapshot required for shutdown. The
        # specific Event is intentionally retained even if a later RPC
        # replaces the shared metadata.
        del rpc_seq, registered_identity

        runtime.operation_wakeup.set()
        if not state["config"].get("NACOS_AUTO_DEREGISTER", True):
            return

        if rpc_active:
            if rpc_done is None:
                logger.warning("Exit cleanup found incomplete Naming RPC metadata")
                return
            started_at = rpc_started_at if rpc_started_at is not None else time.monotonic()
            timeout = rpc_timeout if rpc_timeout is not None else _NAMING_RPC_TIMEOUT_FALLBACK
            elapsed = max(0.0, time.monotonic() - started_at)
            wait_timeout = min(
                max(0.0, timeout - elapsed) + _EXIT_RPC_SCHEDULING_GRACE,
                _EXIT_RPC_WAIT_MAX,
            )
            if not rpc_done.wait(wait_timeout):
                logger.warning("Exit cleanup timed out waiting for the active Naming RPC")
                return

        with runtime.state_lock:
            registered = runtime.registered
        if registered:
            self._deregister_on_exit(state, runtime)

    def _deregister_on_exit(self, state: Dict[str, Any], runtime: _AppRuntimeState) -> None:
        outcome = self._execute_naming_rpc(
            state,
            runtime,
            "deregister",
            runtime.client,
            identity=None,
            allow_during_shutdown=True,
            record_lifecycle_error=False,
            stage=_LifecycleFailureStage.EXIT_DEREGISTER_RPC,
            log_failure=False,
        )
        if outcome.result is _NamingResult.FAILED:
            with runtime.state_lock:
                missing_identity = bool(runtime.registered and runtime.registered_identity is None)
            if missing_identity:
                logger.warning("Exit deregistration skipped because registered identity is missing")
            else:
                logger.warning("Exit deregistration failed")

    # -- Application resolution -------------------------------------------

    def _resolve_app(self, app=None):
        if app is not None:
            return app
        if not has_app_context():
            raise FlaskNacosError("A Flask application or active app/request context is required")
        return current_app._get_current_object()

    def _require_state(self, app=None) -> Tuple[Any, Dict[str, Any], _AppRuntimeState]:
        target_app = self._resolve_app(app)
        state = target_app.extensions.get(EXTENSION_KEY)
        if state is None:
            raise FlaskNacosError("FlaskNacos is not initialized for the selected Flask app")
        if not self._is_owned_state(state):
            raise FlaskNacosError(
                'app.extensions["nacos"] is not owned by this FlaskNacos instance'
            )
        runtime = self._ensure_current_runtime(state)
        return target_app, state, runtime

    def _is_owned_state(self, state: Any) -> bool:
        return (
            isinstance(state, dict)
            and state.get(_OWNER_KEY) is self
            and isinstance(state.get(_RUNTIME_KEY), _AppRuntimeState)
        )

    def _require_client(self, app=None):
        """Private compatibility helper returning a lazy client and config."""
        target_app, state, _ = self._require_state(app)
        client = self.get_client(target_app)
        if client is None:
            raise FlaskNacosError("Nacos client is disabled")
        return client, state["config"]

    @staticmethod
    def _current_pid() -> int:
        return lifecycle.current_pid()

    def _safe(
        self,
        func,
        cfg: Dict[str, Any],
        message: str,
        default: Any = None,
        retry: bool = True,
    ) -> Any:
        """Run non-lifecycle SDK work with the existing fail-fast contract."""
        try:
            if retry:
                return run_with_retry(func, message, cfg)
            return func()
        except Exception as exc:
            logger.error("%s (error_type=%s)", message, type(exc).__name__)
            if cfg.get("NACOS_FAIL_FAST", False):
                raise
            return default


__all__ = ["FlaskNacos", "EXTENSION_KEY"]
