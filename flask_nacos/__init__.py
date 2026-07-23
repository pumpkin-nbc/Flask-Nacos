"""flask-nacos: a Flask extension for Nacos service discovery and configuration."""

from .exceptions import (
    FlaskNacosError,
    NacosClientError,
    NacosConfigError,
    NacosDeregistrationError,
    NacosDiscoveryError,
    NacosLoggingError,
    NacosRegistrationError,
    NacosValidationError,
)
from .extension import FlaskNacos

__version__ = "1.0.2"

__all__ = [
    "FlaskNacos",
    "FlaskNacosError",
    "NacosConfigError",
    "NacosClientError",
    "NacosValidationError",
    "NacosRegistrationError",
    "NacosDeregistrationError",
    "NacosDiscoveryError",
    "NacosLoggingError",
    "__version__",
]
