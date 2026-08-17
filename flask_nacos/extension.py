"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
import math
import os
import time
import weakref
from dataclasses import dataclass, field
from enum import Enum
from threading import Event, Lock, RLock, Thread, current_thread
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, has_app_context, request

from . import config as config_module
from . import config_center, discovery, lifecycle, naming
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
_REGISTRATION_VALID_KEY = "_registration_config_valid"
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


class _NamingResult(Enum):
    """Private result of one logical Naming SDK call."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


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
        registration_error = self._registration_config_error(cfg, connection_error)

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
            _REGISTRATION_VALID_KEY: registration_error is None,
            _REGISTRATION_ERROR_KEY: registration_error,
            _CONNECTION_ERROR_KEY: connection_error,
            _RUNTIME_STALE_KEY: False,
            _RUNTIME_REBUILD_LOCK_KEY: Lock(),
            _RUNTIME_REBUILD_PID_KEY: current_pid,
            _ATEXIT_REGISTERED_KEY: False,
            _FORK_HOOK_REGISTERED_KEY: False,
            _REQUEST_HOOK_REGISTERED_KEY: False,
        }

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
                self.register_instance(app)
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
            and cfg.get("NACOS_REGISTER_ENABLED", True)
            and cfg.get("NACOS_AUTO_REGISTER", True)
            and cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True)
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
        if not cfg.get("NACOS_ENABLED", True) or not cfg.get("NACOS_REGISTER_ENABLED", True):
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
        app, state, runtime = self._require_state(app)
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True):
            return None
        if not cfg.get("NACOS_REGISTER_ENABLED", True):
            return None

        thread, config_error = self._prepare_registration(
            app, state, runtime, explicit=True, consume_pending=False
        )
        self._start_registration_thread(app, state, runtime, thread)

        if config_error is not None and cfg.get("NACOS_FAIL_FAST", False):
            raise config_error
        return None

    def _prepare_registration(
        self,
        app,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        *,
        explicit: bool,
        consume_pending: bool,
    ) -> Tuple[Any, Optional[BaseException]]:
        """Run the sole atomic register preparation state transition."""
        with runtime.state_lock:
            return self._prepare_register_locked(
                app,
                state,
                runtime,
                explicit=explicit,
                consume_pending=consume_pending,
            )

    def _prepare_register_locked(
        self,
        app,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        *,
        explicit: bool,
        consume_pending: bool,
    ) -> Tuple[Any, Optional[BaseException]]:
        """Prepare one register Worker while ``runtime.state_lock`` is held."""
        del app  # the argument documents which app owns the prepared Worker
        cfg = state["config"]
        if not cfg.get("NACOS_ENABLED", True) or not cfg.get("NACOS_REGISTER_ENABLED", True):
            return None, None
        if runtime.shutting_down:
            return None, None

        if consume_pending:
            if not runtime.auto_register_pending:
                return None, None
            runtime.auto_register_pending = False
        elif explicit:
            runtime.auto_register_pending = False

        target_changed = not runtime.target_registered
        if target_changed:
            runtime.target_registered = True
            runtime.operation_generation += 1

        if runtime.registered:
            runtime.last_error = None
            return None, None

        registration_error = state.get(_REGISTRATION_ERROR_KEY)
        if registration_error is not None:
            runtime.last_error = type(registration_error).__name__
            return None, registration_error

        if runtime.operation_kind is not None:
            return None, None

        if explicit and not target_changed:
            # An explicit call retries an unmet idle target. Pure duplicate
            # calls while an operation is active never reach this branch.
            runtime.operation_generation += 1

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
        max_attempts = validate_retry_times(cfg.get("NACOS_RETRY_TIMES", 3)) if retry_enabled else 1
        retry_interval = (
            validate_retry_interval(cfg.get("NACOS_RETRY_INTERVAL", 1.0)) if retry_enabled else 0.0
        )
        direction: Optional[str] = None
        attempts = 0
        client: Any = None
        register_identity: Optional[Dict[str, Any]] = None

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
                    attempts = 0
                    if direction == "register":
                        register_identity = None

                # The first gate deliberately happens before client creation.
                if needed == "register":
                    with runtime.state_lock:
                        if (
                            runtime.operation_thread is not worker
                            or runtime.operation_kind != "register"
                            or runtime.shutting_down
                            or not runtime.target_registered
                            or runtime.registered
                        ):
                            continue

                try:
                    if client is None:
                        client = self._get_or_create_client(state, runtime)
                    if needed == "register" and register_identity is None:
                        register_identity = naming.resolve_instance_identity(cfg)
                except Exception as exc:
                    attempts += 1
                    self._record_worker_failure(runtime, needed, exc)
                    if not self._should_retry_worker(
                        runtime, worker, needed, attempts, max_attempts
                    ):
                        return
                    self._interruptible_retry_wait(runtime, worker, retry_interval)
                    continue

                result = self._execute_naming_rpc(
                    state,
                    runtime,
                    needed,
                    client,
                    identity=register_identity,
                    allow_during_shutdown=False,
                    record_lifecycle_error=True,
                )

                with runtime.state_lock:
                    if runtime.registered == runtime.target_registered:
                        runtime.last_error = None
                        return
                    if runtime.shutting_down:
                        return
                    latest_needed = "register" if runtime.target_registered else "deregister"

                if result is _NamingResult.FAILED and latest_needed == needed:
                    attempts += 1
                    if not self._should_retry_worker(
                        runtime, worker, needed, attempts, max_attempts
                    ):
                        return
                    self._interruptible_retry_wait(runtime, worker, retry_interval)
                    continue

                # SUCCEEDED or SKIPPED always causes a fresh target read. A
                # target change also resets the attempt budget for its direction.
                if latest_needed != needed:
                    direction = None
                    attempts = 0
                elif result is _NamingResult.SUCCEEDED:
                    attempts = 0
                if needed == "deregister" and result is _NamingResult.SUCCEEDED:
                    register_identity = None
        except Exception as exc:
            self._record_worker_failure(runtime, direction or "register", exc)
            logger.error(
                "Nacos registration Worker stopped (error_type=%s)",
                type(exc).__name__,
            )
        finally:
            with runtime.state_lock:
                if runtime.operation_thread is worker:
                    runtime.operation_thread = None
                    if runtime.operation_kind == "register":
                        runtime.operation_kind = None
                    if runtime.registered == runtime.target_registered:
                        runtime.last_error = None

    def _should_retry_worker(
        self,
        runtime: _AppRuntimeState,
        worker: Any,
        direction: str,
        attempts: int,
        max_attempts: int,
    ) -> bool:
        with runtime.state_lock:
            if (
                runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
                or runtime.shutting_down
                or runtime.registered == runtime.target_registered
            ):
                if runtime.registered == runtime.target_registered:
                    runtime.last_error = None
                return False
            latest = "register" if runtime.target_registered else "deregister"
            if latest != direction:
                return True
            return attempts < max_attempts

    @staticmethod
    def _interruptible_retry_wait(
        runtime: _AppRuntimeState, worker: Any, retry_interval: float
    ) -> None:
        """Wait without losing a concurrent target-change wakeup."""
        with runtime.state_lock:
            generation = runtime.operation_generation
            target = runtime.target_registered
            if (
                runtime.shutting_down
                or runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
            ):
                return

        runtime.operation_wakeup.clear()

        with runtime.state_lock:
            if (
                runtime.shutting_down
                or runtime.operation_thread is not worker
                or runtime.operation_kind != "register"
                or runtime.operation_generation != generation
                or runtime.target_registered != target
            ):
                return

        runtime.operation_wakeup.wait(retry_interval)

    @staticmethod
    def _record_worker_failure(
        runtime: _AppRuntimeState, direction: str, exc: BaseException
    ) -> None:
        error_type = type(exc).__name__
        with runtime.state_lock:
            if direction == "register":
                relevant = runtime.target_registered and not runtime.registered
            else:
                relevant = not runtime.target_registered and runtime.registered
            if relevant and not runtime.shutting_down:
                runtime.last_error = error_type
            elif runtime.registered == runtime.target_registered:
                runtime.last_error = None
        logger.warning(
            "Nacos lifecycle attempt failed (operation=%s, error_type=%s)",
            direction,
            error_type,
        )

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

        result = _NamingResult.FAILED
        try:
            result = self._execute_naming_rpc(
                state,
                runtime,
                "deregister",
                runtime.client,
                identity=None,
                allow_during_shutdown=False,
                record_lifecycle_error=True,
            )
        except Exception as exc:  # defensive: runtime errors never escape
            self._record_worker_failure(runtime, "deregister", exc)
            result = _NamingResult.FAILED
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
                thread, _ = self._prepare_registration(
                    app,
                    state,
                    runtime,
                    explicit=False,
                    consume_pending=False,
                )
                self._start_registration_thread(app, state, runtime, thread)

        return result is not _NamingResult.FAILED

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
    ) -> _NamingResult:
        """Execute at most one logical Naming RPC with tri-state semantics."""
        rpc_done: Any = None
        rpc_seq: Optional[int] = None
        result = _NamingResult.FAILED
        network_lock = runtime.network_operation_lock
        network_lock.acquire()
        try:
            with runtime.state_lock:
                gate = self._naming_rpc_gate_locked(runtime, rpc_type, allow_during_shutdown)
                if gate is _NamingResult.SKIPPED:
                    return gate

                actual_identity = identity
                if rpc_type == "deregister":
                    actual_identity = runtime.registered_identity

                if actual_identity is None:
                    missing_error_type = (
                        "MissingRegisteredIdentity"
                        if rpc_type == "deregister"
                        else "MissingRegistrationIdentity"
                    )
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(runtime, rpc_type, missing_error_type)
                    return _NamingResult.FAILED
                if client is None:
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(runtime, rpc_type, "ClientUnavailable")
                    return _NamingResult.FAILED

                try:
                    rpc_done = Event()
                except Exception as exc:
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(runtime, rpc_type, "NamingEventCreateError")
                    logger.error(
                        "Failed to create Naming RPC event (error_type=%s)",
                        type(exc).__name__,
                    )
                    return _NamingResult.FAILED

                runtime.naming_rpc_seq += 1
                rpc_seq = runtime.naming_rpc_seq
                runtime.naming_rpc_active = True
                runtime.naming_rpc_done = rpc_done
                runtime.naming_rpc_started_at = time.monotonic()
                runtime.naming_rpc_timeout = self._naming_timeout_seconds(state["config"])

            error_type: Optional[str] = None
            try:
                if rpc_type == "register":
                    naming.register_instance(client, state["config"], identity=actual_identity)
                elif rpc_type == "deregister":
                    naming.deregister_instance(client, state["config"], identity=actual_identity)
                else:
                    raise RuntimeError("UnsupportedNamingOperation")
                result = _NamingResult.SUCCEEDED
            except Exception as exc:
                result = _NamingResult.FAILED
                error_type = type(exc).__name__
                logger.warning(
                    "Nacos Naming RPC failed (operation=%s, error_type=%s)",
                    rpc_type,
                    error_type,
                )

            try:
                with runtime.state_lock:
                    if result is _NamingResult.SUCCEEDED:
                        if rpc_type == "register":
                            runtime.registered = True
                            runtime.registered_identity = dict(actual_identity)
                        else:
                            runtime.registered = False
                            runtime.registered_identity = None
                        runtime.last_error = None
                    elif record_lifecycle_error and error_type is not None:
                        self._record_rpc_error_locked(runtime, rpc_type, error_type)
            except Exception as exc:
                result = _NamingResult.FAILED
                with runtime.state_lock:
                    if record_lifecycle_error:
                        self._record_rpc_error_locked(runtime, rpc_type, "NamingResultCommitError")
                logger.error(
                    "Failed to commit Naming RPC result (error_type=%s)",
                    type(exc).__name__,
                )
            return result
        except Exception as exc:
            with runtime.state_lock:
                if record_lifecycle_error:
                    self._record_rpc_error_locked(runtime, rpc_type, type(exc).__name__)
            logger.error(
                "Naming RPC infrastructure failed (operation=%s, error_type=%s)",
                rpc_type,
                type(exc).__name__,
            )
            return _NamingResult.FAILED
        finally:
            network_lock.release()
            if rpc_done is not None:
                with runtime.state_lock:
                    if runtime.naming_rpc_seq == rpc_seq:
                        runtime.naming_rpc_active = False
                        runtime.naming_rpc_started_at = None
                        runtime.naming_rpc_timeout = None
                        runtime.naming_rpc_done = None
                rpc_done.set()

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
        thread, _ = self._prepare_registration(
            app,
            state,
            runtime,
            explicit=False,
            consume_pending=True,
        )
        self._start_registration_thread(app, state, runtime, thread)

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
        result = self._execute_naming_rpc(
            state,
            runtime,
            "deregister",
            runtime.client,
            identity=None,
            allow_during_shutdown=True,
            record_lifecycle_error=False,
        )
        if result is _NamingResult.FAILED:
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
