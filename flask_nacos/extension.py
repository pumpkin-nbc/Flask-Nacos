"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
from typing import Any, Dict, List, Optional

from . import config as config_module
from . import config_center, discovery, lifecycle, naming
from .client import create_client
from .exceptions import FlaskNacosError
from .health import register_health_route
from .retry import run_with_retry

logger = logging.getLogger("flask_nacos")

EXTENSION_KEY = "nacos"


class FlaskNacos:
    """Flask extension integrating Nacos service discovery and configuration.

    Supports both the direct ``FlaskNacos(app)`` style and the application
    factory ``init_app(app)`` style. Per-application state is stored in
    ``app.extensions["nacos"]`` while the most recently initialized app's client
    and config are also exposed via the ``client`` and ``config`` attributes for
    convenience.
    """

    def __init__(self, app=None) -> None:
        self._app = None
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
        return self._app

    @property
    def client(self) -> Any:
        return self._client

    @property
    def config(self) -> Optional[Dict[str, Any]]:
        return self._config

    # -- Initialization -----------------------------------------------------

    def init_app(self, app) -> None:
        """Initialize the extension for the given Flask ``app``."""
        cfg = config_module.load_config(app)
        self._configure_logging(cfg)

        state = {"config": cfg, "client": None}
        app.extensions[EXTENSION_KEY] = state
        self._app = app
        self._config = cfg
        self._client = None
        self._registered = False
        self._deregistered = False
        self._registered_pid = None

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
        self._client = client

        _maybe_register_health_route()

        if client is None:
            return

        if cfg["NACOS_REGISTER_ENABLED"] and cfg["NACOS_AUTO_REGISTER"]:
            if cfg.get("NACOS_AUTO_REGISTER_ON_INIT", True):
                self.register_instance()
            else:
                logger.info(
                    "Auto registration on init disabled by configuration "
                    "(NACOS_AUTO_REGISTER_ON_INIT=False)"
                )

        if cfg["NACOS_AUTO_DEREGISTER"] and cfg.get("NACOS_DEREGISTER_ON_EXIT", True):
            self._register_atexit()
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

    def _init_client(self, cfg: Dict[str, Any]) -> Any:
        try:
            config_module.validate_connection_config(cfg)
            return create_client(cfg)
        except Exception as exc:
            logger.error("Failed to initialize Nacos client")
            if cfg["NACOS_FAIL_FAST"]:
                raise
            logger.debug("Nacos client init error suppressed: %s", exc)
            return None

    def _atexit_handler(self) -> None:
        if not self._registered:
            logger.info(
                "No service instance registered by this extension; "
                "skipping exit deregistration"
            )
            return
        try:
            self.deregister_instance()
        except Exception:  # pragma: no cover - best effort on shutdown
            logger.warning("Failed to deregister service instance on exit")

    def _register_atexit(self) -> None:
        if self._atexit_registered:
            logger.info("atexit deregister handler already registered; skipping")
            return
        atexit.register(self._atexit_handler)
        self._atexit_registered = True
        logger.info("atexit deregister handler registered")

    # -- Public API ---------------------------------------------------------

    def get_client(self) -> Any:
        """Return the underlying Nacos client (may be ``None`` if disabled)."""
        return self._client

    def register_instance(self) -> bool:
        """Register the current service instance with Nacos.

        Registration is idempotent per process: when
        ``NACOS_REGISTER_ONCE_PER_PROCESS`` is enabled, a repeated call from the
        same process is skipped. A changed process id (e.g. a forked
        Gunicorn/uWSGI worker) is allowed to register its own instance.
        """
        client, cfg = self._require_client()
        current = lifecycle.current_pid()

        if lifecycle.should_skip_register(
            self._registered,
            self._registered_pid,
            current,
            cfg.get("NACOS_REGISTER_ONCE_PER_PROCESS", True),
        ):
            logger.info(
                "Service instance already registered in process %s; "
                "skipping re-registration",
                current,
            )
            return True

        if self._registered and self._registered_pid != current:
            logger.info(
                "Process id changed (registered_pid=%s, current_pid=%s); "
                "re-registering service instance",
                self._registered_pid,
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
            self._registered = True
            self._registered_pid = current
            self._deregistered = False
            logger.info("Process %s registered service instance", current)
            return True
        return False

    def deregister_instance(self) -> bool:
        """Deregister the current service instance from Nacos.

        Only the instance registered by the current process is deregistered: if
        the recorded registration pid differs from the current process, the call
        is logged and skipped so another process's instance is not affected.
        """
        client, cfg = self._require_client()
        current = lifecycle.current_pid()

        if self._deregistered:
            logger.info("Service instance already deregistered; skipping")
            return True

        skip, reason = lifecycle.should_skip_deregister(self._registered_pid, current)
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
            self._registered = False
            self._registered_pid = None
            self._deregistered = True
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
        ``NACOS_DISCOVERY_METADATA`` when not provided.
        """
        client, cfg = self._require_client()
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
        """Return a single healthy instance for ``service_name`` (or ``None``).

        Selection uses ``strategy`` (falling back to ``NACOS_DISCOVERY_STRATEGY``):
        ``first``, ``random`` or ``weight``.
        """
        cfg = self._config or {}
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
        """Convert a Nacos SDK instance into a standard dict (or ``None``).

        Never raises: on failure it logs and returns ``None`` so a single bad
        instance cannot break the caller.
        """
        try:
            return discovery.normalize_instance(instance)
        except Exception as exc:
            logger.warning("Instance normalization failed: %s", exc)
            return None

    def get_config(self, data_id: str, group: Optional[str] = None) -> Optional[str]:
        """Fetch the raw content of a config item from Nacos."""
        client, cfg = self._require_client()
        return self._safe(
            lambda: config_center.get_config(client, cfg, data_id, group=group),
            cfg,
            "Failed to get config from Nacos",
            default=None,
        )

    def get_status(self) -> Dict[str, Any]:
        """Return the extension's runtime status (no Nacos call, no secrets).

        Reflects only internal state and non-sensitive configuration. Never
        includes ``NACOS_PASSWORD`` / ``NACOS_ACCESS_KEY`` / ``NACOS_SECRET_KEY``.
        """
        cfg = self._config or {}
        return {
            "nacos_enabled": bool(cfg.get("NACOS_ENABLED", False)),
            "client_initialized": self._client is not None,
            "registered": self._registered,
            "service_name": cfg.get("NACOS_SERVICE_NAME"),
            "service_ip": cfg.get("NACOS_SERVICE_IP"),
            "service_port": cfg.get("NACOS_SERVICE_PORT"),
            "server_addr": cfg.get("NACOS_SERVER_ADDR"),
            "namespace_id": cfg.get("NACOS_NAMESPACE_ID", ""),
            "current_pid": lifecycle.current_pid(),
            "registered_pid": self._registered_pid,
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

    def _require_client(self):
        cfg = self._config
        if cfg is None:
            raise FlaskNacosError("FlaskNacos is not initialized; call init_app(app) first")
        if self._client is None:
            raise FlaskNacosError(
                "Nacos client is not available (NACOS_ENABLED=False or initialization failed)"
            )
        return self._client, cfg

    def _safe(
        self,
        func,
        cfg: Dict[str, Any],
        message: str,
        default: Any = None,
        retry: bool = True,
    ) -> Any:
        """Run ``func`` with optional retry, honoring ``NACOS_FAIL_FAST``.

        Retry (when enabled via config) is applied first; if all attempts fail
        the fail-fast setting decides whether to raise or return ``default``.
        """
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
