"""Default configuration and configuration parsing for flask-nacos."""

import logging
from typing import Any, Dict

from .exceptions import NacosConfigError, NacosValidationError
from .utils import (
    is_bool,
    to_bool,
    to_float,
    to_int,
    validate_heartbeat_interval,
    validate_metadata,
    validate_port,
    validate_weight,
)

logger = logging.getLogger("flask_nacos")

DEFAULTS: Dict[str, Any] = {
    # Whether Nacos is enabled at all.
    "NACOS_ENABLED": True,
    # Connection settings.
    "NACOS_SERVER_ADDR": "127.0.0.1:8848",
    "NACOS_NAMESPACE_ID": "",
    "NACOS_USERNAME": None,
    "NACOS_PASSWORD": None,
    "NACOS_ACCESS_KEY": None,
    "NACOS_SECRET_KEY": None,
    "NACOS_GROUP_NAME": "DEFAULT_GROUP",
    # Service registration.
    "NACOS_REGISTER_ENABLED": True,
    "NACOS_AUTO_REGISTER": True,
    "NACOS_AUTO_DEREGISTER": True,
    "NACOS_SERVICE_NAME": None,
    "NACOS_SERVICE_IP": None,
    "NACOS_SERVICE_PORT": None,
    "NACOS_SERVICE_GROUP": "DEFAULT_GROUP",
    "NACOS_SERVICE_CLUSTER": "DEFAULT",
    "NACOS_SERVICE_WEIGHT": 1.0,
    "NACOS_SERVICE_METADATA": {},
    "NACOS_SERVICE_EPHEMERAL": True,
    "NACOS_SERVICE_HEARTBEAT_INTERVAL": 5.0,
    "NACOS_SERVICE_HEALTHY": True,
    "NACOS_SERVICE_ENABLED": True,
    # Configuration center.
    "NACOS_CONFIG_ENABLED": True,
    "NACOS_CONFIG_DATA_ID": None,
    "NACOS_CONFIG_GROUP": "DEFAULT_GROUP",
    # Retry (0.3.0).
    "NACOS_RETRY_ENABLED": True,
    "NACOS_RETRY_TIMES": 3,
    "NACOS_RETRY_INTERVAL": 1.0,
    # Configuration-center request timeout.
    "NACOS_REQUEST_TIMEOUT": 5.0,
    # Health check route (0.3.0).
    "NACOS_HEALTH_CHECK_ENABLED": False,
    "NACOS_HEALTH_CHECK_PATH": "/health/nacos",
    # Deprecated compatibility setting; get_status() is always available.
    "NACOS_STATUS_ENABLED": True,
    # Auto-registration control (0.3.0).
    "NACOS_AUTO_REGISTER_ON_INIT": True,
    # Lifecycle control (0.4.0).
    "NACOS_REGISTER_ONCE_PER_PROCESS": True,
    "NACOS_DEREGISTER_ON_EXIT": True,
    # Service discovery selection strategy (0.4.0).
    "NACOS_DISCOVERY_STRATEGY": "first",
    # Service discovery filtering (0.4.0).
    "NACOS_DISCOVERY_CLUSTER": None,
    "NACOS_DISCOVERY_METADATA": {},
    # Instance normalization (0.4.0).
    "NACOS_INSTANCE_NORMALIZE": True,
    # Behavior control.
    "NACOS_FAIL_FAST": False,
    # Safe Flask-Nacos logging control (1.0.2). Raw SDK logs stay silent.
    "NACOS_LOG_ENABLED": False,
    "NACOS_LOG_LEVEL": "INFO",
    "NACOS_LOG_CONSOLE_ENABLED": True,
    "NACOS_LOG_FILE_ENABLED": True,
    "NACOS_LOG_PATH": "./logs",
    "NACOS_LOG_FILENAME": "flask-nacos.log",
    "NACOS_LOG_FORMAT": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "NACOS_LOG_PROPAGATE": True,
    "NACOS_LOG_MAX_BYTES": 10485760,
    "NACOS_LOG_BACKUP_COUNT": 5,
}


def load_config(app) -> Dict[str, Any]:
    """Merge the application config over the flask-nacos defaults.

    Values present in ``app.config`` take precedence; missing keys fall back to
    :data:`DEFAULTS`. Boolean/number valued keys are coerced to their expected
    types so that string based config sources (e.g. env vars) behave correctly.
    """
    merged: Dict[str, Any] = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in app.config:
            merged[key] = app.config[key]

    # NACOS_SERVICE_EPHEMERAL is intentionally excluded: it must be a genuine
    # bool and is validated strictly at registration time.
    bool_keys = (
        "NACOS_ENABLED",
        "NACOS_REGISTER_ENABLED",
        "NACOS_AUTO_REGISTER",
        "NACOS_AUTO_DEREGISTER",
        "NACOS_SERVICE_HEALTHY",
        "NACOS_SERVICE_ENABLED",
        "NACOS_CONFIG_ENABLED",
        "NACOS_RETRY_ENABLED",
        "NACOS_HEALTH_CHECK_ENABLED",
        "NACOS_STATUS_ENABLED",
        "NACOS_AUTO_REGISTER_ON_INIT",
        "NACOS_REGISTER_ONCE_PER_PROCESS",
        "NACOS_DEREGISTER_ON_EXIT",
        "NACOS_INSTANCE_NORMALIZE",
        "NACOS_FAIL_FAST",
        "NACOS_LOG_ENABLED",
        "NACOS_LOG_CONSOLE_ENABLED",
        "NACOS_LOG_FILE_ENABLED",
        "NACOS_LOG_PROPAGATE",
    )
    for key in bool_keys:
        merged[key] = to_bool(merged[key], DEFAULTS[key])

    # Logging file-rotation numbers may arrive as strings (e.g. env vars).
    # Coerce when possible; leave the original value otherwise so logging
    # setup can decide how to degrade (honoring NACOS_FAIL_FAST).
    max_bytes_coerced = to_int(merged["NACOS_LOG_MAX_BYTES"], None)
    if max_bytes_coerced is not None:
        merged["NACOS_LOG_MAX_BYTES"] = max_bytes_coerced

    backup_count_coerced = to_int(merged["NACOS_LOG_BACKUP_COUNT"], None)
    if backup_count_coerced is not None:
        merged["NACOS_LOG_BACKUP_COUNT"] = backup_count_coerced

    # Coerce valid string numbers (e.g. from env vars) but keep the original
    # value when coercion fails so that validation can report it clearly.
    retry_times_coerced = to_int(merged["NACOS_RETRY_TIMES"], None)
    if retry_times_coerced is not None:
        merged["NACOS_RETRY_TIMES"] = retry_times_coerced

    for key in ("NACOS_RETRY_INTERVAL", "NACOS_REQUEST_TIMEOUT"):
        coerced = to_float(merged[key], None)
        if coerced is not None:
            merged[key] = coerced

    weight_coerced = to_float(merged["NACOS_SERVICE_WEIGHT"], None)
    if weight_coerced is not None:
        merged["NACOS_SERVICE_WEIGHT"] = weight_coerced

    heartbeat_coerced = to_float(
        merged["NACOS_SERVICE_HEARTBEAT_INTERVAL"], None
    )
    if heartbeat_coerced is not None:
        merged["NACOS_SERVICE_HEARTBEAT_INTERVAL"] = heartbeat_coerced

    port_coerced = to_int(merged["NACOS_SERVICE_PORT"], None)
    if port_coerced is not None:
        merged["NACOS_SERVICE_PORT"] = port_coerced

    # Keep mutable metadata isolated per initialized application. This also
    # snapshots user-provided metadata instead of retaining app.config's dict.
    for key in ("NACOS_SERVICE_METADATA", "NACOS_DISCOVERY_METADATA"):
        if isinstance(merged[key], dict):
            merged[key] = dict(merged[key])

    # Metadata validation is deferred to registration so a bad value honors
    # NACOS_FAIL_FAST rather than crashing init_app unconditionally.
    return merged


def validate_connection_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to create a Nacos client."""
    server_addr = config.get("NACOS_SERVER_ADDR")
    if not isinstance(server_addr, str) or not server_addr.strip():
        raise NacosConfigError("NACOS_SERVER_ADDR is required to initialize Nacos client")

    auth_keys = (
        "NACOS_USERNAME",
        "NACOS_PASSWORD",
        "NACOS_ACCESS_KEY",
        "NACOS_SECRET_KEY",
    )
    for key in auth_keys:
        value = config.get(key)
        if value is not None and value != "" and not isinstance(value, str):
            raise NacosConfigError(f"{key} must be a string when configured")

    username_set = config.get("NACOS_USERNAME") not in (None, "")
    password_set = config.get("NACOS_PASSWORD") not in (None, "")
    access_key_set = config.get("NACOS_ACCESS_KEY") not in (None, "")
    secret_key_set = config.get("NACOS_SECRET_KEY") not in (None, "")

    if username_set != password_set:
        raise NacosConfigError(
            "NACOS_USERNAME and NACOS_PASSWORD must be configured together"
        )
    if access_key_set != secret_key_set:
        raise NacosConfigError(
            "NACOS_ACCESS_KEY and NACOS_SECRET_KEY must be configured together"
        )
    if username_set and access_key_set:
        raise NacosConfigError(
            "Username/password authentication and AK/SK authentication "
            "cannot be configured together"
        )


def validate_registration_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to register a service instance.

    Raises :class:`NacosValidationError` (a subclass of ``NacosConfigError``)
    when a required field is missing or a value is invalid.
    """
    service_name = config.get("NACOS_SERVICE_NAME")
    if not isinstance(service_name, str) or not service_name.strip():
        logger.error(
            "Service registration failed: NACOS_SERVICE_NAME must be a "
            "non-empty string"
        )
        raise NacosValidationError(
            "NACOS_SERVICE_NAME must be a non-empty string to register a service"
        )

    if config.get("NACOS_SERVICE_PORT") is None:
        logger.error("Service registration failed: NACOS_SERVICE_PORT is required")
        raise NacosValidationError(
            "NACOS_SERVICE_PORT is required to register a service and cannot be guessed"
        )

    # Raises NacosValidationError on illegal port / weight / metadata values.
    validate_port(config["NACOS_SERVICE_PORT"])
    validate_weight(config.get("NACOS_SERVICE_WEIGHT", 1.0))
    validate_metadata(config.get("NACOS_SERVICE_METADATA"))

    if not is_bool(config.get("NACOS_SERVICE_EPHEMERAL")):
        logger.error("Service registration failed: NACOS_SERVICE_EPHEMERAL must be a bool")
        raise NacosValidationError("NACOS_SERVICE_EPHEMERAL must be a bool")
    if config.get("NACOS_SERVICE_EPHEMERAL"):
        validate_heartbeat_interval(
            config.get("NACOS_SERVICE_HEARTBEAT_INTERVAL", 5.0)
        )


__all__ = [
    "DEFAULTS",
    "load_config",
    "validate_connection_config",
    "validate_registration_config",
]
