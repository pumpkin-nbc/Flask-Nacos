"""Custom exception hierarchy for flask-nacos."""


class FlaskNacosError(Exception):
    """Base exception for all flask-nacos errors."""


class NacosConfigError(FlaskNacosError):
    """Raised when configuration is invalid or a config operation fails."""


class NacosClientError(FlaskNacosError):
    """Raised when the underlying Nacos client cannot be created or used."""


class NacosValidationError(NacosConfigError):
    """Raised when deterministic Nacos input or numeric config validation fails.

    Subclasses :class:`NacosConfigError` so that code catching configuration
    errors also catches validation errors.
    """


class NacosRegistrationError(FlaskNacosError):
    """Raised when service registration fails."""


class NacosDeregistrationError(FlaskNacosError):
    """Raised when service deregistration fails."""


class NacosDiscoveryError(FlaskNacosError):
    """Raised when a service discovery operation fails."""


class NacosLoggingError(FlaskNacosError):
    """Raised when logging configuration is invalid or a logging setup step fails."""


__all__ = [
    "FlaskNacosError",
    "NacosConfigError",
    "NacosClientError",
    "NacosValidationError",
    "NacosRegistrationError",
    "NacosDeregistrationError",
    "NacosDiscoveryError",
    "NacosLoggingError",
]
