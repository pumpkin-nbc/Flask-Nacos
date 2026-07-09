# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.2.0

### Added

- Added stronger validation for service registration parameters.
- Added local IP auto-detection helper for service registration.
- Added idempotent handling for service registration.
- Added idempotent handling for service deregistration.
- Added improved service discovery behavior.
- Added clearer fail-fast behavior for registration, deregistration, and discovery.
- Added additional tests for service registration and discovery.

### Changed

- Improved logging for Nacos client initialization, service registration, deregistration, and discovery.
- Improved README documentation for service registration and discovery.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.

## [0.1.0] - 2026-07-08

### Added

- Initial release of `flask-nacos`.
- `FlaskNacos` extension supporting both direct (`FlaskNacos(app)`) and factory
  (`init_app(app)`) initialization styles.
- Nacos client initialization from `app.config` with namespace and
  username/password authentication.
- Automatic and manual service registration (`register_instance`).
- Automatic (via `atexit`) and manual service deregistration
  (`deregister_instance`).
- Service discovery: `list_instances` and `get_one_healthy_instance`.
- Configuration center read support: `get_config`.
- `NACOS_FAIL_FAST` behavior control and a custom exception hierarchy.
- Standard `logging` integration that never emits secrets.
- pytest test suite with a fully mocked Nacos SDK.
- PyPI packaging via hatchling.
