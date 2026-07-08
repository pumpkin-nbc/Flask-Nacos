"""flask-nacos: a Flask extension for Nacos service discovery and configuration."""

from .exceptions import (
    FlaskNacosError,
    NacosConfigError,
    NacosDiscoveryError,
    NacosRegistrationError,
)
from .extension import FlaskNacos

__version__ = "0.1.0"

__all__ = [
    "FlaskNacos",
    "FlaskNacosError",
    "NacosConfigError",
    "NacosRegistrationError",
    "NacosDiscoveryError",
    "__version__",
]
