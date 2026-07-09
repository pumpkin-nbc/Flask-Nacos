"""The :class:`FlaskNacos` extension class."""

import atexit
import logging
from typing import Any, Dict, List, Optional

from . import config as config_module
from . import config_center, naming
from .client import create_client
from .exceptions import FlaskNacosError

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

        if not cfg["NACOS_ENABLED"]:
            logger.info("Nacos is disabled (NACOS_ENABLED=False); skipping initialization")
            return

        client = self._init_client(cfg)
        state["client"] = client
        self._client = client

        if client is None:
            return

        if cfg["NACOS_REGISTER_ENABLED"] and cfg["NACOS_AUTO_REGISTER"]:
            self.register_instance()

        if cfg["NACOS_AUTO_DEREGISTER"]:
            self._register_atexit()

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

    def _register_atexit(self) -> None:
        def _deregister_on_exit() -> None:
            try:
                self.deregister_instance()
            except Exception:  # pragma: no cover - best effort on shutdown
                logger.warning("Failed to deregister service instance on exit")

        atexit.register(_deregister_on_exit)

    # -- Public API ---------------------------------------------------------

    def get_client(self) -> Any:
        """Return the underlying Nacos client (may be ``None`` if disabled)."""
        return self._client

    def register_instance(self) -> bool:
        """Register the current service instance with Nacos (idempotent)."""
        client, cfg = self._require_client()
        if self._registered:
            logger.info("Service instance already registered; skipping re-registration")
            return True

        result = self._safe(
            lambda: naming.register_instance(client, cfg),
            cfg,
            "Failed to register service instance",
            default=False,
        )
        if result:
            self._registered = True
            self._deregistered = False
            return True
        return False

    def deregister_instance(self) -> bool:
        """Deregister the current service instance from Nacos (idempotent)."""
        client, cfg = self._require_client()
        if self._deregistered:
            logger.info("Service instance already deregistered; skipping")
            return True

        result = self._safe(
            lambda: naming.deregister_instance(client, cfg),
            cfg,
            "Failed to deregister service instance",
            default=False,
        )
        if result:
            self._registered = False
            self._deregistered = True
            return True
        return False

    def list_instances(
        self,
        service_name: str,
        group: Optional[str] = None,
        healthy_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Return the list of instances for ``service_name``."""
        client, cfg = self._require_client()
        result = self._safe(
            lambda: naming.list_instances(
                client, cfg, service_name, group=group, healthy_only=healthy_only
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
    ) -> Optional[Dict[str, Any]]:
        """Return a single healthy instance for ``service_name`` (or ``None``)."""
        client, cfg = self._require_client()
        return self._safe(
            lambda: naming.get_one_healthy_instance(client, cfg, service_name, group=group),
            cfg,
            "Service discovery failed",
            default=None,
        )

    def get_config(self, data_id: str, group: Optional[str] = None) -> Optional[str]:
        """Fetch the raw content of a config item from Nacos."""
        client, cfg = self._require_client()
        return self._safe(
            lambda: config_center.get_config(client, cfg, data_id, group=group),
            cfg,
            "Failed to get config from Nacos",
            default=None,
        )

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

    def _safe(self, func, cfg: Dict[str, Any], message: str, default: Any = None) -> Any:
        """Run ``func`` honoring the ``NACOS_FAIL_FAST`` behavior."""
        try:
            return func()
        except Exception as exc:
            logger.error(message)
            if cfg["NACOS_FAIL_FAST"]:
                raise
            logger.debug("Suppressed Nacos error: %s", exc)
            return default


__all__ = ["FlaskNacos", "EXTENSION_KEY"]
