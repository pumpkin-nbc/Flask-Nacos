"""Default configuration and configuration parsing for flask-nacos."""

from typing import Any, Dict

from .exceptions import NacosConfigError
from .utils import to_bool, to_float, to_int, validate_metadata

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

    bool_keys = (
        "NACOS_ENABLED",
        "NACOS_REGISTER_ENABLED",
        "NACOS_AUTO_REGISTER",
        "NACOS_AUTO_DEREGISTER",
        "NACOS_SERVICE_EPHEMERAL",
        "NACOS_SERVICE_HEALTHY",
        "NACOS_SERVICE_ENABLED",
        "NACOS_CONFIG_ENABLED",
        "NACOS_FAIL_FAST",
    )
    for key in bool_keys:
        merged[key] = to_bool(merged[key], DEFAULTS[key])

    merged["NACOS_SERVICE_WEIGHT"] = to_float(
        merged["NACOS_SERVICE_WEIGHT"], DEFAULTS["NACOS_SERVICE_WEIGHT"]
    )
    merged["NACOS_SERVICE_PORT"] = to_int(merged["NACOS_SERVICE_PORT"], None)
    merged["NACOS_SERVICE_METADATA"] = validate_metadata(merged["NACOS_SERVICE_METADATA"])

    return merged


def validate_connection_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to create a Nacos client."""
    if not config.get("NACOS_SERVER_ADDR"):
        raise NacosConfigError("NACOS_SERVER_ADDR is required to initialize Nacos client")


def validate_registration_config(config: Dict[str, Any]) -> None:
    """Validate the settings required to register a service instance."""
    if not config.get("NACOS_SERVICE_NAME"):
        raise NacosConfigError("NACOS_SERVICE_NAME is required to register a service")
    if config.get("NACOS_SERVICE_PORT") is None:
        raise NacosConfigError(
            "NACOS_SERVICE_PORT is required to register a service and cannot be guessed"
        )


__all__ = [
    "DEFAULTS",
    "load_config",
    "validate_connection_config",
    "validate_registration_config",
]
