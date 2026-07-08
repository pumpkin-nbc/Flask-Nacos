"""Custom exception hierarchy for flask-nacos."""


class FlaskNacosError(Exception):
    """Base exception for all flask-nacos errors."""


class NacosConfigError(FlaskNacosError):
    """Raised when configuration is invalid or a config operation fails."""


class NacosRegistrationError(FlaskNacosError):
    """Raised when service registration or deregistration fails."""


class NacosDiscoveryError(FlaskNacosError):
    """Raised when a service discovery operation fails."""


__all__ = [
    "FlaskNacosError",
    "NacosConfigError",
    "NacosRegistrationError",
    "NacosDiscoveryError",
]
