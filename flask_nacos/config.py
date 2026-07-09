"""Default configuration and configuration parsing for flask-nacos."""

import logging
from typing import Any, Dict

from .exceptions import NacosConfigError, NacosValidationError
from .utils import (
    is_bool,
    to_bool,
    to_float,
    to_int,
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
    "NACOS_SERVICE_HEALTHY": True,
    "NACOS_SERVICE_ENABLED": True,
    # Configuration center.
    "NACOS_CONFIG_ENABLED": True,
    "NACOS_CONFIG_DATA_ID": None,
    "NACOS_CONFIG_GROUP": "DEFAULT_GROUP",
    # Behavior control.
    "NACOS_FAIL_FAST": False,
    "NACOS_LOG_LEVEL": "INFO",
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
        "NACOS_FAIL_FAST",
    )
    for key in bool_keys:
        merged[key] = to_bool(merged[key], DEFAULTS[key])

    # Coerce valid string numbers (e.g. from env vars) but keep the original
    # value when coercion fails so that validation can report it clearly.
    weight_coerced = to_float(merged["NACOS_SERVICE_WEIGHT"], None)
    if weight_coerced is not None:
        merged["NACOS_SERVICE_WEIGHT"] = weight_coerced

    port_coerced = to_int(merged["NACOS_SERVICE_PORT"], None)
    if port_coerced is not None:
        merged["NACOS_SERVICE_PORT"] = port_coerced

    # Metadata validation is deferred to registration so a bad value honors
    # NACOS_FAIL_FAST rather than crashing init_app unconditionally.
    return merged


def validate_connection_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to create a Nacos client."""
    if not config.get("NACOS_SERVER_ADDR"):
        raise NacosConfigError("NACOS_SERVER_ADDR is required to initialize Nacos client")


def validate_registration_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to register a service instance.

    Raises :class:`NacosValidationError` (a subclass of ``NacosConfigError``)
    when a required field is missing or a value is invalid.
    """
    if not config.get("NACOS_SERVICE_NAME"):
        logger.error("Service registration failed: NACOS_SERVICE_NAME is required")
        raise NacosValidationError("NACOS_SERVICE_NAME is required to register a service")

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


__all__ = [
    "DEFAULTS",
    "load_config",
    "validate_connection_config",
    "validate_registration_config",
]
