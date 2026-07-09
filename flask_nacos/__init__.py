"""flask-nacos: a Flask extension for Nacos service discovery and configuration."""

from .exceptions import (
    FlaskNacosError,
    NacosClientError,
    NacosConfigError,
    NacosDeregistrationError,
    NacosDiscoveryError,
    NacosRegistrationError,
    NacosValidationError,
)
from .extension import FlaskNacos

__version__ = "0.5.0"

__all__ = [
    "FlaskNacos",
    "FlaskNacosError",
    "NacosConfigError",
    "NacosClientError",
    "NacosValidationError",
    "NacosRegistrationError",
    "NacosDeregistrationError",
    "NacosDiscoveryError",
    "__version__",
]
