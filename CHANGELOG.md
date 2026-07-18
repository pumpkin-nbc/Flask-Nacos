# Changelog

English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.0.1

### Fixed

- Preflighted active automatic-registration settings during `init_app()`, so
  fail-fast validation errors occur before client creation or partial extension
  state is installed, while disabled auto-registration still supports
  config-center and discovery-only applications without a service name.

## 1.0.0

### Added

- Released the first stable version of Flask-Nacos.
- Added stable API documentation for the 1.0 series.
- Added final release checklist for PyPI publishing.
- Added stable installation and smoke test validation steps.
- Added Python 3.13 CI coverage and an 85% coverage floor.
- Added regression coverage for multi-app state, concurrent lifecycle calls,
  post-fork locks, config defaults/timeouts, and SDK client construction.
- Added a runnable application-factory example with matching English and
  Simplified Chinese end-to-end integration guides.
- Added a beginner example and rewrote both Quickstart guides as a progressive
  Python-first tutorial covering registration, health, config, and discovery.
- Added environment-based authentication to the beginner example, separate
  username/password and AK/SK tests, and an opt-in real Nacos auth test.
- Added `NACOS_SERVICE_HEARTBEAT_INTERVAL` with a validated `5.0` second default
  for SDK-managed ephemeral-instance heartbeat renewal.
- Added a security policy and private vulnerability reporting guidance.
- Added release-tag and package-index preflight checks for immutable versions.

### Changed

- Adopted the Apache License 2.0 for the initial public release.
- Hardened configuration isolation, numeric validation, discovery filtering,
  and automatic deregistration behavior.
- Added package checks that keep source and distribution license metadata aligned.
- Marked the public API as stable.
- Improved README for PyPI display.
- Improved release documentation for TestPyPI and PyPI publishing.
- Improved final validation scripts for package release.
- Split CI into one quality/package job and a lightweight Python/Flask test
  matrix so expensive release checks run only once.
- `get_config()` now accepts an omitted `data_id`, falling back to
  `NACOS_CONFIG_DATA_ID`, and passes `NACOS_REQUEST_TIMEOUT` to SDK 2.x.
- SDK import and client-construction failures now use `NacosClientError` while
  preserving the original exception as the cause.
- Clarified that `NACOS_SERVER_ADDR` locates Nacos while `NACOS_SERVICE_IP`
  advertises the Flask service to consumers.
- Documented how to integrate Flask-Nacos through an existing centralized
  `app/extensions.py` and `extension_config(app)` application-factory pattern.
- Replaced long-lived PyPI token publishing with protected OIDC Trusted
  Publishing jobs for TestPyPI and PyPI.
- Strengthened release validation to reject stale artifacts and broken PyPI
  links, and to install-test both wheel and sdist distributions.

### Fixed

- Treated SDK `False` registration and deregistration results as retryable
  failures without corrupting lifecycle state.
- Rejected incomplete or mixed authentication credentials and invalid retry or
  request-timeout numbers through the existing fail-fast behavior.
- Skipped discovered instances with malformed endpoints, parsed string boolean
  fields correctly, and sanitized invalid weights.
- Kept ephemeral service instances healthy by passing the heartbeat interval to
  Nacos SDK 2.x, while leaving persistent-instance registration unchanged.
- Aligned the beginner example's registered and listening ports at `3000` and
  removed hardcoded connection and authentication values.
- Made runtime state, health reporting, registration flags, process IDs, locks,
  and shutdown callbacks independent for every initialized Flask app.
- Made repeated `init_app()` calls reuse the existing client and lifecycle
  state, and reject extension-slot collisions explicitly.
- Serialized concurrent registration and deregistration transitions with a
  per-app `RLock`, replacing inherited locks after a process ID change.
- Prevented deterministic `NacosValidationError` failures from being retried.
- Made `NACOS_CONFIG_ENABLED=False` skip configuration-center SDK calls.

### Deprecated

- `NACOS_STATUS_ENABLED` is retained as a no-op for 1.x compatibility and is
  planned for removal in 2.0; `get_status()` remains consistently available.

### Stable APIs

The following APIs are considered stable in the 1.0 series:

- `FlaskNacos`
- `init_app(app)`
- `get_client()`
- `register_instance()`
- `deregister_instance()`
- `list_instances()`
- `get_one_healthy_instance()`
- `get_config()`
- `get_status()`
- `normalize_instance()`

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.
- This is the first stable release intended for PyPI publishing.

## 0.9.0

### Added

- Added public API snapshot checks.
- Added backward compatibility tests.
- Added package smoke test script.
- Added examples validation script.
- Added 1.0.0 release checklist.
- Added Release Candidate preparation documentation.
- Added additional CI checks for API stability and example consistency.

### Changed

- Improved error messages and logging consistency.
- Improved TestPyPI release validation workflow.
- Improved documentation for API freeze and 1.0.0 preparation.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.
- `0.9.0` is intended as the final preparation version before `1.0.0`.

## 0.8.0

### Added

- Added compatibility checks for Python 3.8 syntax support.
- Added compatibility documentation.
- Added Nacos SDK response extraction compatibility helpers.
- Added tests for multiple Nacos instance response structures.
- Added CI compatibility validation.

### Changed

- Improved service discovery compatibility with different Nacos SDK response shapes.
- Improved instance normalization for camelCase and snake_case fields.
- Improved README compatibility documentation.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.

## 0.7.0

### Added

- Added quickstart documentation.
- Added full configuration reference documentation.
- Added API reference documentation.
- Added service registration documentation.
- Added service discovery documentation.
- Added health check documentation.
- Added production deployment documentation.
- Added troubleshooting documentation.
- Added local Nacos Docker Compose example.
- Added documentation link and unsupported-feature checks.

### Changed

- Improved README structure for PyPI display.
- Improved examples for common Flask-Nacos usage scenarios.
- Improved CI to validate documentation consistency.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.

## 0.6.0

### Added

- Added `scripts/check_version.py` to verify version consistency across
  `pyproject.toml`, `__version__`, and `CHANGELOG.md`.
- Added `scripts/check_package.py` to inspect built distributions and verify the
  wheel ships `py.typed` and core modules while excluding tests and caches.
- Added `scripts/check_sensitive_info.py` to scan for hardcoded secrets, private
  IPs, internal domains, and stray `.env` files.
- Added `scripts/release_check.sh` one-shot pre-release check script.
- Added a manual TestPyPI/PyPI release workflow (`.github/workflows/release.yml`).
- Added `docs/release.md` release guide.

### Changed

- Extended the CI workflow with version-consistency, sensitive-information, and
  package-content checks.
- Included `/scripts` and `/docs` in the sdist build.
- Updated README (English and Chinese) with release, development, and security
  sections.

### Notes

- No library API changes; runtime behavior is unchanged.
- `get_config()` continues to return raw config content only.
- Publishing to PyPI is never automated on push; release uploads are manual and
  require explicitly choosing the target index.

## 0.5.0

### Added

- Added type hints for public APIs and core internal methods.
- Added `py.typed` for PEP 561 typing support.
- Added ruff configuration.
- Added mypy configuration.
- Added pytest and coverage configuration.
- Added GitHub Actions CI workflow.
- Added additional example applications.
- Added PyPI release preparation documentation.

### Changed

- Improved package metadata in `pyproject.toml`.
- Improved README documentation for local development, testing, and production usage.
- Improved code style and import organization.

### Notes

- `get_config()` continues to return raw config content only.
- YAML, JSON, and dict config parsing are not supported in this version.
- Loading Nacos config into Flask `app.config` is not supported.

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
