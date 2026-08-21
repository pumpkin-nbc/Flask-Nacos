# Changelog

English | [简体中文](CHANGELOG.zh-CN.md)

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version labels follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.1.1

### Fixed

- Fixed registration lifecycle recovery when authenticated Nacos Client
  construction fails during temporary server unavailability. The verified SDK
  `2.0.11` `NacosRequestException` at the exact `CLIENT_CREATE/register` stage
  now participates in the existing transient Recovery path.
- Kept structured 401/403 authentication failures deterministic, while
  unverified SDK versions, stages, directions, and exception types remain
  `UNKNOWN` and stop after the finite retry budget.
- Fixed heartbeat log-state cross-talk when one SDK Client sends beats for
  multiple instances. Warning throttling and recovery are now isolated by the
  exact service/group/cluster/IP/port identity; unsafe or incomplete identities
  fall back to stateless `<unknown>` logging without collision-prone keys.
- Fixed heartbeat observation cross-talk across repeated registrations of the
  same identity. Private monotonic cycle and completion gates now reject stale
  or out-of-order callbacks, while logging and Runtime observation share one
  idempotently installed Client wrapper.
- Fixed shutdown's active Naming RPC timeout snapshot to use the actual SDK
  Client `default_timeout`. `NACOS_REQUEST_TIMEOUT` remains configuration-center
  only, and invalid SDK timeout values retain the bounded three-second fallback.

### Changed

- Clarified process-exit cleanup with the sole
  `NACOS_DEREGISTER_ON_EXIT` setting. Disabling it installs no remote cleanup
  callback and never blocks an explicit `deregister_instance()`.
- Reduced heartbeat log noise: ordinary success is `DEBUG`, first/type-changed
  failure is `WARNING`, unchanged failures are warning-throttled for 60 seconds,
  and the first per-identity success after failure is one recovery `INFO`.
- Extended the side-effect-free `get_status()` snapshot from 12 to 16 fields
  with the current ephemeral-registration cycle's local heartbeat state, last
  success/failure Unix timestamps, and safe error type. Health remains the same
  seven-field local lifecycle response and does not use heartbeat observations.
- Added Python 3.8/Flask 1.1.4/gevent compatibility coverage and pinned the SDK
  compatibility matrix to the explicitly verified `2.0.0` and `2.0.11`
  releases.
- Expanded concurrency, fork, heartbeat isolation, timeout, and opt-in real
  Nacos regression coverage, including a test-only TCP recovery gate.

### Compatibility

- Public method signatures, the seven-field health schema, target-state
  lifecycle, fork/shutdown behavior, and SDK heartbeat ownership are unchanged.
  The local `get_status()` schema has the documented additive heartbeat fields.
- Lifecycle Recovery still performs no remote-instance monitoring: after local
  state converges, the Worker exits and the Nacos SDK remains responsible for
  heartbeat and connection maintenance.

## 1.1.0

### Added

- Added target-state lifecycle convergence through
  `register_instance(app=None) -> None`, with per-app/PID Worker ownership and
  Naming RPC single-flight.
- Added the fixed local status model: `target_registered`, `registered`,
  `operation_running`, and safe `last_error`, plus Client and registered
  identity snapshots.
- Added three-state internal Naming results (success, failure, skip), exact
  registered-identity reuse, interruptible retry, fork Runtime rebuilding, and
  bounded shutdown cleanup.
- Added registration lifecycle self-recovery for explicitly identified
  transient transport failures. It preserves the existing finite attempt
  budget, then uses interruptible bounded backoff with jitter; deterministic
  failures stop immediately and unknown failures stop at the finite limit.
- Expanded CI coverage through Python 3.14 and the valid Flask 1.0.x, 1.1.x,
  2.x, 3.0.x, and 3.1.x runtime combinations.
- Pinned wheel and sdist output to Core Metadata 2.4 for strict validation by
  current packaging tools while retaining PEP 639 license metadata.

### Changed

- `register_instance()` accepts an optional Flask app, returns `None`, and
  schedules Client creation, SDK registration, lifecycle retry, and heartbeat
  startup in a named daemon thread.
- Removed the redundant initialization-specific auto-registration switch.
  `NACOS_AUTO_REGISTER` is now the single automatic-registration switch, and
  initialization calls the public registration command without waiting for Nacos.
- Removed the redundant registration-permission switch. `NACOS_ENABLED` now
  controls the integration, while `NACOS_AUTO_REGISTER` controls only automatic
  registration; an explicit `register_instance()` remains the registration command.
- Registration-only validation is lazy when automatic registration is disabled.
  Automatic, explicit, and post-fork pending registration share one call-local
  orchestration path without adding Runtime or public status fields.
- Client creation is lazy and bound to one Flask app/PID. Status, health, and
  `.client` cache reads have no SDK side effects.
- `deregister_instance(app=None)` preserves the last lifecycle command and
  keeps its idempotent, synchronous-cleanup contract.
- `NACOS_DEREGISTER_ON_EXIT` is the single exit deregistration switch.
- Kept retry/recovery ownership inside the Register Worker. Client creation and
  Naming failures share conservative classification without mixing Client state
  into Naming RPC outcome metadata, and successful convergence still hands
  heartbeat maintenance entirely to the Nacos SDK.
- Synchronized the bilingual Quickstart code with the runnable beginner app,
  documented every environment variable consumed by the complete factory
  example, and removed hardcoded demo credentials from simplified examples.

### Compatibility

- Lifecycle runtime failures are reported through safe local status and logs;
  fail-fast remains limited to deterministic configuration failures.
- The runtime requirement remains Python `>=3.8`; Flask is now declared as
  `>=1.0` without an artificial upper bound.
- Development type checking stays on mypy `<1.15`, the last line that can run
  on and explicitly target Python 3.8.

## 1.0.2

### Added

- Added configurable, sanitized logging through `NACOS_LOG_ENABLED`,
  `NACOS_LOG_CONSOLE_ENABLED`, `NACOS_LOG_FILE_ENABLED`, `NACOS_LOG_PATH`,
  `NACOS_LOG_FILENAME`, `NACOS_LOG_FORMAT`, `NACOS_LOG_PROPAGATE`,
  `NACOS_LOG_MAX_BYTES`, and `NACOS_LOG_BACKUP_COUNT`.
- Added level-specific console colors: blue for `DEBUG`, green for `INFO`,
  yellow for `WARNING`, red for `ERROR`, and bold red for `CRITICAL`.
- Added sanitized temporary-instance heartbeat success and failure logs.
- Added regression coverage for logging, transactional initialization,
  registration identity, and discovery validation.

### Changed

- `NACOS_LOG_*` settings control only sanitized Flask-Nacos logs; native SDK
  loggers are always silent and no longer create `~/logs/nacos`.
- Logging is disabled by default and never creates configured directories while
  disabled. When enabled, console and rotating file output both default to
  active, using `./logs/flask-nacos.log`, 10 MiB per file, and five backups.
- File logs remain plain text without ANSI escape sequences. Flask-Nacos uses
  the named `flask_nacos` logger and does not configure the root logger.
- Registration caches and reuses the exact successful service identity for
  retries and deregistration; persistent instances ignore heartbeat settings.
- Discovery validates service, group, cluster, and filter inputs before SDK
  calls, forwards cluster filters to SDK 2.x, and also filters defensively.
- Status examples expose only safe fields. Production guidance covers shared
  multi-worker identities, SDK 2.x HTTPS verification limitations, and safe
  logging defaults.

### Fixed

- Fixed library and SDK logging side effects, duplicate handlers, unexpected
  log files, and potential leakage of credentials, request data, or config
  content through application, root, console, or file handlers.
- Fixed fail-fast initialization leaving partial app or extension state.
- Fixed non-fail-fast operations raising when the initialized client is
  unavailable; these operations now return their documented safe defaults.
- Fixed deregistration resolving a new identity instead of using the exact
  identity registered with Nacos.

### Notes

- `get_config()` continues to return raw content; Flask-Nacos does not parse
  YAML, JSON, or dictionaries and does not load remote content into
  `app.config`.

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
