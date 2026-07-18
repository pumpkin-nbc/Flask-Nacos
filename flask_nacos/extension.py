"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
import os
import weakref
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, has_app_context

from . import config as config_module
from . import config_center, discovery, lifecycle, naming
from .client import create_client
from .exceptions import FlaskNacosError, NacosClientError, NacosConfigError
from .health import register_health_route
from .retry import run_with_retry

logger = logging.getLogger("flask_nacos")

EXTENSION_KEY = "nacos"
_OWNER_KEY = "_extension"
_RUNTIME_KEY = "_runtime"


@dataclass
class _AppRuntimeState:
    """Private mutable lifecycle state owned by one Flask application."""

    registered: bool = False
    deregistered: bool = False
    registered_pid: Optional[int] = None
    lock: Any = field(default_factory=RLock)
    lock_pid: Optional[int] = field(default_factory=os.getpid)
    atexit_registered: bool = False


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

        cfg = config_module.load_config(app)
        self._configure_logging(cfg)

        should_auto_register = bool(
            cfg["NACOS_ENABLED"]
            and cfg["NACOS_REGISTER_ENABLED"]
            and cfg["NACOS_AUTO_REGISTER"]
            and cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True)
        )
        registration_config_valid = True
        if should_auto_register:
            registration_config_valid = self._preflight_auto_registration(cfg)

        runtime = _AppRuntimeState()
        state = {
            "config": cfg,
            "client": None,
            _OWNER_KEY: self,
            _RUNTIME_KEY: runtime,
        }
        app.extensions[EXTENSION_KEY] = state
        self._app = app
        self._sync_legacy_state(state)

        def _maybe_register_health_route() -> None:
            if cfg.get("NACOS_HEALTH_CHECK_ENABLED"):
                self._safe(
                    lambda: register_health_route(app, self),
                    cfg,
                    "Failed to register health check route",
                    retry=False,
                )

        if not cfg["NACOS_ENABLED"]:
            logger.info("Nacos is disabled (NACOS_ENABLED=False); skipping initialization")
            _maybe_register_health_route()
            return

        client = self._init_client(cfg)
        state["client"] = client
        self._sync_legacy_state(state)

        _maybe_register_health_route()

        if client is None:
            return

        if should_auto_register and registration_config_valid:
            self._register_instance_for(app, state, runtime)
        elif cfg["NACOS_REGISTER_ENABLED"] and cfg["NACOS_AUTO_REGISTER"]:
            if not cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True):
                logger.info(
                    "Auto registration on init disabled by configuration "
                    "(NACOS_AUTO_REGISTER_ON_INIT=False)"
                )

        if cfg["NACOS_AUTO_DEREGISTER"] and cfg.get("NACOS_DEREGISTER_ON_EXIT", True):
            self._register_atexit(app, state, runtime)
        else:
            logger.info(
                "atexit auto-deregister disabled by configuration "
                "(NACOS_AUTO_DEREGISTER=%s, NACOS_DEREGISTER_ON_EXIT=%s)",
                cfg["NACOS_AUTO_DEREGISTER"],
                cfg.get("NACOS_DEREGISTER_ON_EXIT", True),
            )

    def _configure_logging(self, cfg: Dict[str, Any]) -> None:
        level_name = str(cfg.get("NACOS_LOG_LEVEL") or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())

    def _preflight_auto_registration(self, cfg: Dict[str, Any]) -> bool:
        """Validate active init-time registration before creating a client."""
        try:
            config_module.validate_registration_config(cfg)
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
        if not runtime.registered:
            logger.info(
                "No service instance registered by this extension; "
                "skipping exit deregistration"
            )
            return
        try:
            self._deregister_instance_for(app, state, runtime)
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

    def register_instance(self) -> bool:
        """Register the current service instance with Nacos.

        Registration is idempotent per process: when
        ``NACOS_REGISTER_ONCE_PER_PROCESS`` is enabled, concurrent and repeated
        calls from the same process perform at most one SDK operation. A changed
        process id (for example a forked worker) receives a fresh lock and may
        register its own instance.
        """
        app, state, runtime = self._require_state(require_client=True)
        return self._register_instance_for(app, state, runtime)

    def _register_instance_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> bool:
        client = state["client"]
        cfg = state["config"]
        current = lifecycle.current_pid()
        lock = self._process_lock(runtime, current)

        with lock:
            if lifecycle.should_skip_register(
                runtime.registered,
                runtime.registered_pid,
                current,
                cfg.get("NACOS_REGISTER_ONCE_PER_PROCESS", True),
            ):
                logger.info(
                    "Service instance already registered in process %s; "
                    "skipping re-registration",
                    current,
                )
                return True

            if runtime.registered and runtime.registered_pid != current:
                logger.info(
                    "Process id changed (registered_pid=%s, current_pid=%s); "
                    "re-registering service instance",
                    runtime.registered_pid,
                    current,
                )

            logger.info("Process %s registering service instance", current)
            result = self._safe(
                lambda: naming.register_instance(client, cfg),
                cfg,
                "Failed to register service instance",
                default=False,
            )
            if result:
                runtime.registered = True
                runtime.registered_pid = current
                runtime.deregistered = False
                self._sync_legacy_if_latest(app, state)
                logger.info("Process %s registered service instance", current)
                return True
            return False

    def deregister_instance(self) -> bool:
        """Deregister the current service instance from Nacos.

        Only the instance registered by the current process is deregistered: if
        the recorded registration pid differs from the current process, the call
        is logged and skipped so another process's instance is not affected.
        """
        app, state, runtime = self._require_state(require_client=True)
        return self._deregister_instance_for(app, state, runtime)

    def _deregister_instance_for(
        self, app, state: Dict[str, Any], runtime: _AppRuntimeState
    ) -> bool:
        client = state["client"]
        cfg = state["config"]
        current = lifecycle.current_pid()
        lock = self._process_lock(runtime, current)

        with lock:
            if runtime.deregistered:
                logger.info("Service instance already deregistered; skipping")
                return True

            skip, reason = lifecycle.should_skip_deregister(
                runtime.registered_pid, current
            )
            if skip:
                logger.info("Skipping deregistration: %s", reason)
                return False

            result = self._safe(
                lambda: naming.deregister_instance(client, cfg),
                cfg,
                "Failed to deregister service instance",
                default=False,
            )
            if result:
                runtime.registered = False
                runtime.registered_pid = None
                runtime.deregistered = True
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
        _, state, _ = self._require_state(require_client=True)
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
        _, state, _ = self._require_state(require_client=True)
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
        if state["client"] is None:
            self._raise_client_unavailable()
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
        return {
            "nacos_enabled": bool(cfg.get("NACOS_ENABLED", False)),
            "client_initialized": client is not None,
            "registered": runtime.registered,
            "service_name": cfg.get("NACOS_SERVICE_NAME"),
            "service_ip": cfg.get("NACOS_SERVICE_IP"),
            "service_port": cfg.get("NACOS_SERVICE_PORT"),
            "server_addr": cfg.get("NACOS_SERVER_ADDR"),
            "namespace_id": cfg.get("NACOS_NAMESPACE_ID", ""),
            "current_pid": lifecycle.current_pid(),
            "registered_pid": runtime.registered_pid,
            "register_once_per_process": bool(
                cfg.get("NACOS_REGISTER_ONCE_PER_PROCESS", True)
            ),
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

    def _sync_legacy_state(self, state: Dict[str, Any]) -> None:
        runtime = state[_RUNTIME_KEY]
        self._client = state.get("client")
        self._config = state.get("config")
        self._registered = runtime.registered
        self._deregistered = runtime.deregistered
        self._registered_pid = runtime.registered_pid
        self._atexit_registered = runtime.atexit_registered

    def _sync_legacy_if_latest(self, app, state: Dict[str, Any]) -> None:
        if app is self._app:
            self._sync_legacy_state(state)

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
            logger.debug("Suppressed Nacos error: %s", exc)
            return default


__all__ = ["FlaskNacos", "EXTENSION_KEY"]
