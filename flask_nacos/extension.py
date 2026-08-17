"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
import os
import weakref
from dataclasses import dataclass, field
from threading import RLock, Thread
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, has_app_context

from . import config as config_module
from . import config_center, discovery, lifecycle, naming
from .client import create_client
from .exceptions import FlaskNacosError, NacosClientError, NacosConfigError
from .health import register_health_route
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
_INIT_LOCK = RLock()


@dataclass
class _AppRuntimeState:
    """Private mutable lifecycle state owned by one Flask application."""

    registered: bool = False
    deregistered: bool = False
    registered_pid: Optional[int] = None
    lock: Any = field(default_factory=RLock)
    lock_pid: Optional[int] = field(default_factory=os.getpid)
    atexit_registered: bool = False
    registered_identity: Optional[Dict[str, Any]] = None
    registration_in_progress: bool = False
    last_registration_error_type: Optional[str] = None
    deregistration_requested: bool = False
    registration_desired: bool = False
    lifecycle_lock: Any = field(default_factory=RLock)
    lifecycle_lock_pid: Optional[int] = field(default_factory=os.getpid)


class FlaskNacos:
    """Flask extension integrating Nacos discovery and configuration.

    Supports both the direct ``FlaskNacos(app)`` style and the application
    factory ``init_app(app)`` style. Each application's state is stored in
    ``app.extensions["nacos"]``. Inside an application or request context,
    public operations use that application; outside a context they use the
    most recently initialized application for backward compatibility.
    """

    def __init__(self, app=None) -> None:
        self._app = None
        # These mirrors preserve the existing private attributes for callers
        # that inspect the most recently initialized application's state.
        self._client: Any = None
        self._config: Optional[Dict[str, Any]] = None
        self._registered = False
        self._deregistered = False
        self._registered_pid: Optional[int] = None
        self._atexit_registered = False
        if app is not None:
            self.init_app(app)

    # -- Properties ---------------------------------------------------------

    @property
    def app(self):
        return self._selected_app()

    @property
    def client(self) -> Any:
        state = self._selected_state()
        return state.get("client") if state is not None else None

    @property
    def config(self) -> Optional[Dict[str, Any]]:
        state = self._selected_state()
        return state.get("config") if state is not None else None

    # -- Initialization -----------------------------------------------------

    def init_app(self, app) -> None:
        """Initialize the extension for the given Flask ``app``.

        Re-initializing the same app with the same extension object is a no-op.
        An existing ``nacos`` extension slot owned by another object is rejected
        explicitly instead of silently replacing its client and lifecycle state.
        """
        with _INIT_LOCK:
            self._init_app_locked(app)

    def _init_app_locked(self, app) -> None:
        """Initialize one app while serializing process-global logger changes."""
        if EXTENSION_KEY in app.extensions:
            existing = app.extensions[EXTENSION_KEY]
            if self._is_owned_state(existing):
                self._app = app
                self._sync_legacy_state(existing)
                logger.info("FlaskNacos is already initialized for this app; reusing state")
                return
            raise FlaskNacosError(
                'app.extensions["nacos"] is already owned by another extension'
            )

        previous_app = self._app
        previous_state = None
        if previous_app is not None:
            candidate = previous_app.extensions.get(EXTENSION_KEY)
            if self._is_owned_state(candidate):
                previous_state = candidate

        cfg = config_module.load_config(app)
        validate_logging_config(cfg)

        should_auto_register = bool(
            cfg["NACOS_ENABLED"]
            and cfg["NACOS_REGISTER_ENABLED"]
            and cfg["NACOS_AUTO_REGISTER"]
            and cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True)
        )
        registration_config_valid = True

        runtime = _AppRuntimeState()
        state = {
            "config": cfg,
            "client": None,
            _OWNER_KEY: self,
            _RUNTIME_KEY: runtime,
        }
        logging_configured = False
        try:
            self._configure_logging(app, cfg)
            logging_configured = True

            if should_auto_register:
                registration_config_valid = self._preflight_auto_registration(cfg)

            if cfg["NACOS_ENABLED"]:
                state["client"] = self._init_client(cfg)
                cleanup_sdk_default_handlers(cfg)

                if (
                    state["client"] is not None
                    and cfg["NACOS_REGISTER_ENABLED"]
                    and cfg["NACOS_AUTO_REGISTER"]
                    and not cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True)
                ):
                    logger.info(
                        "Auto registration on init disabled by configuration "
                        "(NACOS_AUTO_REGISTER_ON_INIT=False)"
                    )
            else:
                logger.info(
                    "Nacos is disabled (NACOS_ENABLED=False); skipping initialization"
                )

            # Commit application state only after fail-fast configuration and
            # client initialization have completed successfully. Registration
            # itself is a background lifecycle command in 1.1.0.
            app.extensions[EXTENSION_KEY] = state
            self._app = app
            self._sync_legacy_state(state)

            if cfg.get("NACOS_HEALTH_CHECK_ENABLED"):
                self._safe(
                    lambda: register_health_route(app, self),
                    cfg,
                    "Failed to register health check route",
                    retry=False,
                )

            if state["client"] is None:
                return

            if cfg["NACOS_AUTO_DEREGISTER"] and cfg.get(
                "NACOS_DEREGISTER_ON_EXIT", True
            ):
                self._register_atexit(app, state, runtime)
            else:
                logger.info(
                    "atexit auto-deregister disabled by configuration "
                    "(NACOS_AUTO_DEREGISTER=%s, NACOS_DEREGISTER_ON_EXIT=%s)",
                    cfg["NACOS_AUTO_DEREGISTER"],
                    cfg.get("NACOS_DEREGISTER_ON_EXIT", True),
                )
        except Exception:
            installed = app.extensions.get(EXTENSION_KEY)
            if self._is_owned_state(installed) and installed is state:
                app.extensions.pop(EXTENSION_KEY, None)
            if runtime.registered and state["client"] is not None:
                try:
                    naming.deregister_instance(
                        state["client"], cfg, identity=runtime.registered_identity
                    )
                except Exception:
                    logger.warning(
                        "Failed to roll back service registration after init failure"
                    )
            self._restore_previous_state(previous_app, previous_state)
            if logging_configured:
                if previous_state is not None:
                    configure_logger(previous_app, previous_state["config"])
                else:
                    configure_logger(None, config_module.DEFAULTS)
            raise

        # Thread startup happens after the state commit by design. A thread
        # construction/start failure may be raised in fail-fast mode, but the
        # otherwise valid extension state remains installed so callers can
        # inspect it and retry the lifecycle command.
        if (
            state["client"] is not None
            and should_auto_register
            and registration_config_valid
        ):
            self._schedule_registration_for(app, state, runtime)

    def _configure_logging(self, app, cfg: Dict[str, Any]) -> None:
        """Configure safe extension logs and isolate raw SDK logs."""
        configure_logger(app, cfg)

    def _preflight_auto_registration(self, cfg: Dict[str, Any]) -> bool:
        """Validate active init-time registration before creating a client."""
        try:
            config_module.validate_registration_config(cfg)
            if cfg.get("NACOS_RETRY_ENABLED", True):
                validate_retry_times(cfg.get("NACOS_RETRY_TIMES", 3))
                validate_retry_interval(cfg.get("NACOS_RETRY_INTERVAL", 1.0))
        except NacosConfigError as exc:
            if cfg["NACOS_FAIL_FAST"]:
                raise
            logger.error("Automatic registration skipped: %s", exc)
            return False
        return True

    def _init_client(self, cfg: Dict[str, Any]) -> Any:
        try:
            config_module.validate_connection_config(cfg)
            return create_client(cfg)
        except NacosConfigError:
            logger.error("Failed to initialize Nacos client")
            if cfg["NACOS_FAIL_FAST"]:
                raise
            return None
        except NacosClientError:
            logger.error("Failed to initialize Nacos client")
            if cfg["NACOS_FAIL_FAST"]:
                raise
            return None
        except Exception as exc:
            error = NacosClientError("Failed to initialize Nacos client")
            logger.error(str(error))
            if cfg["NACOS_FAIL_FAST"]:
                raise error from exc
            logger.debug(
                "Nacos client init error suppressed (%s)", type(exc).__name__
            )
            return None

    def _atexit_handler(self) -> None:
        """Best-effort shutdown handler for the currently selected app."""
        try:
            app, state, runtime = self._require_state()
        except FlaskNacosError:
            return
        self._atexit_handler_for(app, state, runtime)

    def _atexit_handler_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> None:
        current = lifecycle.current_pid()
        state_lock = self._lifecycle_process_lock(runtime, current)
        with state_lock:
            runtime.registration_desired = False
            runtime.deregistration_requested = True
            has_local_work = bool(
                runtime.registration_in_progress
                or (runtime.registered and runtime.registered_pid == current)
            )
            if not has_local_work:
                runtime.deregistration_requested = False
                runtime.deregistered = True
                self._sync_legacy_if_latest(app, state)
                logger.info(
                    "No service instance registered by this extension; "
                    "skipping exit deregistration"
                )
                return

        try:
            # Waiting for the operation lock also waits for an in-flight daemon
            # registration. The re-entrant lock lets the helper reuse the same
            # unique deregistration implementation once the operation settles.
            operation_lock = self._process_lock(runtime, current)
            with operation_lock:
                result = self._deregister_instance_for(app, state, runtime)
            error_type = None
            if not result:
                state_lock = self._lifecycle_process_lock(runtime, current)
                with state_lock:
                    error_type = (
                        runtime.last_registration_error_type
                        or "DeregistrationReturnedFalse"
                    )
            self._finish_deregistration_request(
                app,
                state,
                runtime,
                result=result,
                error_type=error_type,
            )
        except Exception:  # pragma: no cover - best effort on shutdown
            logger.warning("Failed to deregister service instance on exit")

    def _register_atexit(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> None:
        if runtime.atexit_registered:
            logger.info("atexit deregister handler already registered; skipping")
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
            target_runtime = target_state[_RUNTIME_KEY]
            extension._atexit_handler_for(target_app, target_state, target_runtime)

        atexit.register(_handler)
        runtime.atexit_registered = True
        self._sync_legacy_if_latest(app, state)
        logger.info("atexit deregister handler registered")

    # -- Public API ---------------------------------------------------------

    def get_client(self) -> Any:
        """Return the underlying Nacos client (may be ``None`` if disabled)."""
        return self.client

    def register_instance(self) -> None:
        """Request non-blocking registration of the current service instance.

        Client availability and deterministic registration settings are checked
        synchronously. Nacos network I/O, retries, and heartbeat startup run in
        at most one daemon thread per app and process. Observe completion with
        :meth:`get_status`; this lifecycle command intentionally returns
        ``None``.
        """
        app, state, runtime = self._require_state()
        self._schedule_registration_for(app, state, runtime)
        return None

    def _schedule_registration_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> None:
        """Validate and schedule a single-flight registration command."""
        cfg = state["config"]
        current = lifecycle.current_pid()
        lock = self._lifecycle_process_lock(runtime, current)

        if not self._client_available(state):
            with lock:
                runtime.registration_desired = True
                runtime.deregistration_requested = False
                runtime.last_registration_error_type = "ClientUnavailable"
                self._sync_legacy_if_latest(app, state)
            return None

        try:
            config_module.validate_registration_config(cfg)
            if cfg.get("NACOS_RETRY_ENABLED", True):
                validate_retry_times(cfg.get("NACOS_RETRY_TIMES", 3))
                validate_retry_interval(cfg.get("NACOS_RETRY_INTERVAL", 1.0))
        except NacosConfigError as exc:
            with lock:
                runtime.registration_desired = True
                runtime.deregistration_requested = False
                runtime.last_registration_error_type = type(exc).__name__
                self._sync_legacy_if_latest(app, state)
            logger.error(
                "Nacos registration command rejected (error_type=%s)",
                type(exc).__name__,
            )
            if cfg.get("NACOS_FAIL_FAST", False):
                raise
            return None

        with lock:
            deregistration_was_requested = runtime.deregistration_requested
            runtime.registration_desired = True
            runtime.deregistration_requested = False
            runtime.last_registration_error_type = None
            if runtime.registration_in_progress:
                self._sync_legacy_if_latest(app, state)
                return None
            if (
                runtime.registered
                and runtime.registered_pid == current
                and not deregistration_was_requested
            ):
                self._sync_legacy_if_latest(app, state)
                return None
            runtime.registration_in_progress = True
            self._sync_legacy_if_latest(app, state)

        try:
            thread = Thread(
                target=self._background_register,
                args=(app, state, runtime),
                name="flask-nacos-registration",
                daemon=True,
            )
            thread.start()
        except Exception as exc:
            current = lifecycle.current_pid()
            lock = self._lifecycle_process_lock(runtime, current)
            with lock:
                runtime.registration_in_progress = False
                if (
                    runtime.registered
                    and runtime.registered_pid == current
                    and runtime.registration_desired
                ):
                    runtime.last_registration_error_type = None
                else:
                    runtime.last_registration_error_type = type(exc).__name__
                if not runtime.registration_desired and not runtime.registered:
                    runtime.deregistration_requested = False
                    runtime.deregistered = True
                self._sync_legacy_if_latest(app, state)
            logger.error(
                "Failed to start asynchronous Nacos registration "
                "(error_type=%s)",
                type(exc).__name__,
            )
            if state["config"].get("NACOS_FAIL_FAST", False):
                raise
        return None

    def _background_register(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> None:
        """Run the existing registration state machine in a daemon thread."""
        error_type = None
        try:
            if not self._register_instance_for(app, state, runtime):
                current = lifecycle.current_pid()
                lock = self._lifecycle_process_lock(runtime, current)
                with lock:
                    error_type = (
                        runtime.last_registration_error_type
                        or "RegistrationReturnedFalse"
                    )
        except Exception as exc:
            error_type = type(exc).__name__
            logger.error(
                "Asynchronous Nacos registration failed (error_type=%s)",
                error_type,
            )
        finally:
            current = lifecycle.current_pid()
            lock = self._lifecycle_process_lock(runtime, current)
            should_deregister = False
            with lock:
                if runtime.registered and runtime.registered_pid == current:
                    error_type = None
                runtime.registration_in_progress = False
                runtime.last_registration_error_type = error_type
                if not runtime.registration_desired:
                    if runtime.registered and runtime.registered_pid == current:
                        runtime.deregistration_requested = True
                        should_deregister = True
                    else:
                        runtime.deregistration_requested = False
                        runtime.deregistered = True
                self._sync_legacy_if_latest(app, state)

            if should_deregister:
                try:
                    self._run_requested_deregistration(app, state, runtime)
                except Exception as exc:
                    # Background failures cannot be delivered to the original
                    # caller. Keep the daemon quiet and expose only a safe type.
                    logger.error(
                        "Deferred Nacos deregistration failed (error_type=%s)",
                        type(exc).__name__,
                    )

    def _register_instance_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> bool:
        client = state["client"]
        cfg = state["config"]
        current = lifecycle.current_pid()
        lock = self._process_lock(runtime, current)

        with lock:
            state_lock = self._lifecycle_process_lock(runtime, current)
            with state_lock:
                skip_registration = lifecycle.should_skip_register(
                    runtime.registered,
                    runtime.registered_pid,
                    current,
                )
                previous_pid = runtime.registered_pid

            if skip_registration:
                logger.info(
                    "Service instance already registered in process %s; "
                    "skipping re-registration",
                    current,
                )
                return True

            if runtime.registered and previous_pid != current:
                logger.info(
                    "Process id changed (registered_pid=%s, current_pid=%s); "
                    "re-registering service instance",
                    previous_pid,
                    current,
                )

            try:
                identity = naming.resolve_instance_identity(cfg)
            except Exception as exc:
                self._publish_lifecycle_error(app, state, runtime, exc)
                logger.error("Failed to resolve service instance identity")
                if cfg.get("NACOS_FAIL_FAST", False):
                    raise
                return False

            logger.info("Process %s registering service instance", current)
            try:
                result = run_with_retry(
                    lambda: naming.register_instance(client, cfg, identity=identity),
                    "Failed to register service instance",
                    cfg,
                )
            except Exception as exc:
                self._publish_lifecycle_error(app, state, runtime, exc)
                logger.error("Failed to register service instance")
                if cfg.get("NACOS_FAIL_FAST", False):
                    raise
                return False
            if result:
                state_lock = self._lifecycle_process_lock(runtime, current)
                with state_lock:
                    runtime.registered = True
                    runtime.registered_pid = current
                    runtime.deregistered = False
                    runtime.registered_identity = dict(identity)
                    runtime.last_registration_error_type = None
                    self._sync_legacy_if_latest(app, state)
                logger.info("Process %s registered service instance", current)
                return True
            return False

    def deregister_instance(self) -> bool:
        """Request deregistration, synchronously when an instance is registered.

        During registration, the request is accepted immediately and executed
        after that operation completes. An already absent local instance is an
        idempotent success and does not call the SDK.
        """
        app, state, runtime = self._require_state()
        current = lifecycle.current_pid()
        state_lock = self._lifecycle_process_lock(runtime, current)
        with state_lock:
            runtime.registration_desired = False
            runtime.deregistration_requested = True
            if runtime.registration_in_progress:
                self._sync_legacy_if_latest(app, state)
                return True
            if not runtime.registered or runtime.registered_pid != current:
                runtime.deregistration_requested = False
                runtime.deregistered = True
                runtime.registered = False
                runtime.registered_pid = None
                runtime.registered_identity = None
                self._sync_legacy_if_latest(app, state)
                return True

        if not self._client_available(state):
            return False
        return self._run_requested_deregistration(app, state, runtime)

    def _run_requested_deregistration(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> bool:
        """Execute and reconcile a previously accepted deregistration request."""
        error_type = None
        try:
            result = self._deregister_instance_for(app, state, runtime)
            if not result:
                current = lifecycle.current_pid()
                lock = self._lifecycle_process_lock(runtime, current)
                with lock:
                    error_type = (
                        runtime.last_registration_error_type
                        or "DeregistrationReturnedFalse"
                    )
        except Exception as exc:
            result = False
            error_type = type(exc).__name__
            self._finish_deregistration_request(
                app, state, runtime, result=False, error_type=error_type
            )
            raise

        self._finish_deregistration_request(
            app, state, runtime, result=result, error_type=error_type
        )
        return result

    def _finish_deregistration_request(
        self,
        app,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        *,
        result: bool,
        error_type: Optional[str],
    ) -> None:
        """Publish a deregistration result without overriding a newer command."""
        current = lifecycle.current_pid()
        state_lock = self._lifecycle_process_lock(runtime, current)
        should_schedule = False
        with state_lock:
            if runtime.registration_desired:
                runtime.deregistration_requested = False
                should_schedule = bool(
                    not runtime.registered and not runtime.registration_in_progress
                )
            elif result:
                runtime.deregistration_requested = False
            else:
                # A failed delayed deregistration remains pending so a later
                # explicit deregister_instance() call can retry it.
                runtime.deregistration_requested = True
            if not result:
                runtime.last_registration_error_type = error_type
            self._sync_legacy_if_latest(app, state)

        if should_schedule:
            # A newer register command won while deregistration held the
            # operation lock. Reconcile to its desired state automatically.
            self._schedule_registration_for(app, state, runtime)

    def _deregister_instance_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> bool:
        client = state["client"]
        cfg = state["config"]
        current = lifecycle.current_pid()
        lock = self._process_lock(runtime, current)

        with lock:
            state_lock = self._lifecycle_process_lock(runtime, current)
            with state_lock:
                locally_registered = bool(
                    runtime.registered and runtime.registered_pid == current
                )
                identity = runtime.registered_identity

            if not locally_registered:
                logger.info("Service instance is not registered; skipping deregistration")
                return True

            skip, reason = lifecycle.should_skip_deregister(
                runtime.registered_pid, current
            )
            if skip:
                logger.info("Skipping deregistration: %s", reason)
                return False

            try:
                result = run_with_retry(
                    lambda: naming.deregister_instance(
                        client, cfg, identity=identity
                    ),
                    "Failed to deregister service instance",
                    cfg,
                )
            except Exception as exc:
                self._publish_lifecycle_error(app, state, runtime, exc)
                logger.error("Failed to deregister service instance")
                if cfg.get("NACOS_FAIL_FAST", False):
                    raise
                return False
            if result:
                state_lock = self._lifecycle_process_lock(runtime, current)
                with state_lock:
                    runtime.registered = False
                    runtime.registered_pid = None
                    runtime.deregistered = True
                    runtime.registered_identity = None
                    runtime.last_registration_error_type = None
                    self._sync_legacy_if_latest(app, state)
                return True
            return False

    def list_instances(
        self,
        service_name: str,
        group: Optional[str] = None,
        healthy_only: bool = True,
        cluster: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the list of instances for ``service_name``.

        ``cluster`` falls back to ``NACOS_DISCOVERY_CLUSTER`` and ``metadata`` to
        ``NACOS_DISCOVERY_METADATA`` only when explicitly passed as ``None``.
        """
        _, state, _ = self._require_state()
        if not self._client_available(state):
            return []
        client = state["client"]
        cfg = state["config"]
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
        """Return a single healthy instance for ``service_name`` (or ``None``)."""
        _, state, _ = self._require_state()
        if not self._client_available(state):
            return None
        cfg = state["config"]
        instances = self.list_instances(
            service_name,
            group=group,
            healthy_only=True,
            cluster=cluster,
            metadata=metadata,
        )
        strategy_name = strategy or cfg.get("NACOS_DISCOVERY_STRATEGY", "first")
        logger.info(
            "Selecting one healthy instance (service=%s, strategy=%s, candidates=%d)",
            service_name,
            strategy_name,
            len(instances),
        )
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
            logger.warning("Instance normalization failed: %s", exc)
            return None

    def get_config(
        self, data_id: Optional[str] = None, group: Optional[str] = None
    ) -> Optional[str]:
        """Fetch raw config content, using ``NACOS_CONFIG_DATA_ID`` by default."""
        _, state, _ = self._require_state()
        cfg = state["config"]
        if not cfg.get("NACOS_CONFIG_ENABLED", True):
            logger.info("Nacos config center is disabled (NACOS_CONFIG_ENABLED=False)")
            return None
        if not self._client_available(state):
            return None
        effective_data_id = data_id or cfg.get("NACOS_CONFIG_DATA_ID")
        return self._safe(
            lambda: config_center.get_config(
                state["client"], cfg, effective_data_id, group=group
            ),
            cfg,
            "Failed to get config from Nacos",
            default=None,
        )

    def get_status(self) -> Dict[str, Any]:
        """Return the selected application's runtime status without Nacos I/O."""
        try:
            _, state, runtime = self._require_state()
            cfg = state["config"]
            client = state["client"]
        except FlaskNacosError:
            cfg = {}
            client = None
            runtime = _AppRuntimeState()
        current = lifecycle.current_pid()
        state_lock = self._lifecycle_process_lock(runtime, current)
        with state_lock:
            registered = runtime.registered
            registration_in_progress = runtime.registration_in_progress
            last_registration_error_type = runtime.last_registration_error_type
            deregistration_requested = runtime.deregistration_requested
            registered_pid = runtime.registered_pid
        return {
            "nacos_enabled": bool(cfg.get("NACOS_ENABLED", False)),
            "client_initialized": client is not None,
            "registered": registered,
            "registration_in_progress": registration_in_progress,
            "last_registration_error_type": last_registration_error_type,
            "deregistration_requested": deregistration_requested,
            "service_name": cfg.get("NACOS_SERVICE_NAME"),
            "service_ip": cfg.get("NACOS_SERVICE_IP"),
            "service_port": cfg.get("NACOS_SERVICE_PORT"),
            "server_addr": cfg.get("NACOS_SERVER_ADDR"),
            "namespace_id": cfg.get("NACOS_NAMESPACE_ID", ""),
            "current_pid": current,
            "registered_pid": registered_pid,
            "deregister_on_exit": bool(cfg.get("NACOS_DEREGISTER_ON_EXIT", True)),
            "discovery_strategy": cfg.get("NACOS_DISCOVERY_STRATEGY", "first"),
            "instance_normalize": bool(cfg.get("NACOS_INSTANCE_NORMALIZE", True)),
            "health_check_enabled": bool(cfg.get("NACOS_HEALTH_CHECK_ENABLED", False)),
            "health_check_path": cfg.get("NACOS_HEALTH_CHECK_PATH", "/health/nacos"),
        }

    # -- Internal helpers ---------------------------------------------------

    def _selected_app(self):
        if has_app_context():
            app = current_app._get_current_object()
            state = app.extensions.get(EXTENSION_KEY)
            if self._is_owned_state(state):
                return app
            return None
        return self._app

    def _selected_state(self) -> Optional[Dict[str, Any]]:
        app = self._selected_app()
        if app is None:
            return None
        state = app.extensions.get(EXTENSION_KEY)
        return state if self._is_owned_state(state) else None

    def _is_owned_state(self, state: Any) -> bool:
        return (
            isinstance(state, dict)
            and state.get(_OWNER_KEY) is self
            and isinstance(state.get(_RUNTIME_KEY), _AppRuntimeState)
        )

    def _require_state(
        self, require_client: bool = False
    ) -> Tuple[Any, Dict[str, Any], _AppRuntimeState]:
        app = self._selected_app()
        if app is None:
            if has_app_context():
                raise FlaskNacosError(
                    "FlaskNacos is not initialized for the current Flask app"
                )
            raise FlaskNacosError("FlaskNacos is not initialized; call init_app(app) first")
        state = app.extensions.get(EXTENSION_KEY)
        if not self._is_owned_state(state):
            raise FlaskNacosError("FlaskNacos application state is unavailable")
        if require_client and state["client"] is None:
            self._raise_client_unavailable()
        return app, state, state[_RUNTIME_KEY]

    def _require_client(self):
        """Backward-compatible internal helper returning client and config."""
        _, state, _ = self._require_state(require_client=True)
        return state["client"], state["config"]

    @staticmethod
    def _raise_client_unavailable() -> None:
        raise FlaskNacosError(
            "Nacos client is not available "
            "(NACOS_ENABLED=False or initialization failed)"
        )

    @staticmethod
    def _process_lock(runtime: _AppRuntimeState, current_pid: int):
        if runtime.lock_pid != current_pid:
            # Locks inherited from a fork may be held by a vanished thread.
            runtime.lock = RLock()
            runtime.lock_pid = current_pid
        return runtime.lock

    @staticmethod
    def _lifecycle_process_lock(runtime: _AppRuntimeState, current_pid: int):
        if runtime.lifecycle_lock_pid != current_pid:
            # Locks, daemon threads, and local registration ownership are not
            # inherited as usable lifecycle state after fork.
            runtime.lifecycle_lock = RLock()
            runtime.lifecycle_lock_pid = current_pid
            runtime.registered = False
            runtime.deregistered = False
            runtime.registered_pid = None
            runtime.registered_identity = None
            runtime.registration_in_progress = False
            runtime.last_registration_error_type = None
            runtime.deregistration_requested = False
            runtime.registration_desired = False
        return runtime.lifecycle_lock

    def _sync_legacy_state(self, state: Dict[str, Any]) -> None:
        runtime = state[_RUNTIME_KEY]
        self._client = state.get("client")
        self._config = state.get("config")
        self._registered = runtime.registered
        self._deregistered = runtime.deregistered
        self._registered_pid = runtime.registered_pid
        self._atexit_registered = runtime.atexit_registered

    def _publish_lifecycle_error(
        self,
        app,
        state: Dict[str, Any],
        runtime: _AppRuntimeState,
        exc: BaseException,
    ) -> None:
        """Store only a safe exception class name in local lifecycle state."""
        current = lifecycle.current_pid()
        state_lock = self._lifecycle_process_lock(runtime, current)
        with state_lock:
            runtime.last_registration_error_type = type(exc).__name__
            self._sync_legacy_if_latest(app, state)

    def _sync_legacy_if_latest(self, app, state: Dict[str, Any]) -> None:
        if app is self._app:
            self._sync_legacy_state(state)

    def _restore_previous_state(self, app, state: Optional[Dict[str, Any]]) -> None:
        """Restore the latest-app compatibility mirrors after failed init."""
        self._app = app
        if state is not None:
            self._sync_legacy_state(state)
            return
        self._client = None
        self._config = None
        self._registered = False
        self._deregistered = False
        self._registered_pid = None
        self._atexit_registered = False

    def _client_available(self, state: Dict[str, Any]) -> bool:
        """Honor fail-fast when an initialized app has no usable client."""
        if state.get("client") is not None:
            return True
        cfg = state["config"]
        message = (
            "Nacos client is not available "
            "(NACOS_ENABLED=False or initialization failed)"
        )
        logger.error(message)
        if cfg.get("NACOS_FAIL_FAST", False):
            raise FlaskNacosError(message)
        return False

    def _safe(
        self,
        func,
        cfg: Dict[str, Any],
        message: str,
        default: Any = None,
        retry: bool = True,
    ) -> Any:
        """Run ``func`` with optional retry, honoring ``NACOS_FAIL_FAST``."""
        try:
            if retry:
                return run_with_retry(func, message, cfg)
            return func()
        except Exception as exc:
            logger.error(message)
            if cfg["NACOS_FAIL_FAST"]:
                raise
            logger.debug(
                "Suppressed Nacos error (error_type=%s)", type(exc).__name__
            )
            return default


__all__ = ["FlaskNacos", "EXTENSION_KEY"]
