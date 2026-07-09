# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.4.0

### Added

- Added per-process registration lifecycle control.
- Added deregistration-on-exit control.
- Added service instance normalization.
- Added service discovery filtering by cluster and metadata.
- Added service discovery strategies: `first`, `random`, and `weight`.
- Added additional runtime status fields for process and discovery information.

### Changed

- Improved service registration behavior for multi-worker deployments.
- Improved deregistration behavior to avoid deregistering instances from other processes.
- Improved README documentation for Gunicorn/uWSGI deployment scenarios.
- Improved test coverage for lifecycle and discovery strategy behavior.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.

## 0.3.0

### Added

- Added retry support for Nacos operations.
- Added retry configuration options.
- Added request timeout configuration.
- Added optional Flask health check route.
- Added `get_status()` for inspecting extension runtime status.
- Added `NACOS_AUTO_REGISTER_ON_INIT` for finer auto-registration control.

### Changed

- Improved production deployment documentation.
- Improved logging around retry, health check, and auto-registration behavior.
- Improved test coverage for retry and health check behavior.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.

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
