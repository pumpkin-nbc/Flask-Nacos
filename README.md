# Flask-Nacos

English | [简体中文](README.zh-CN.md)

`flask-nacos` is a Flask extension that integrates Flask applications with
[Nacos](https://nacos.io/), providing service registration, deregistration,
service discovery, and configuration-center access. It follows the conventions
of common Flask extensions such as `Flask-SQLAlchemy` and `Flask-Redis`.

## Features

- Simple `FlaskNacos(app)` and application-factory `init_app(app)` styles.
- Nacos client initialization from `app.config`, with namespace and
  username/password authentication.
- Automatic and manual service registration.
- Automatic (via `atexit`) and manual service deregistration.
- Service discovery: list instances and pick one healthy instance.
- Configuration-center read support (`get_config`).
- Configurable fail-fast behavior with a dedicated exception hierarchy.
- Standard `logging` integration that never logs secrets.
- Unified retry for Nacos operations, an optional health-check route, and a
  `get_status()` runtime inspector (0.3.0).
- Per-process registration lifecycle, safe deregistration, instance
  normalization, and `first`/`random`/`weight` discovery strategies (0.4.0).
- Full type hints with `py.typed` (PEP 561), plus ruff/mypy/pytest/coverage
  configuration and CI (0.5.0).
- Release tooling: version-consistency, package-content, and sensitive-info
  check scripts, a one-shot `release_check.sh`, expanded CI checks, and a
  manual TestPyPI/PyPI release workflow (0.6.0).
- Full documentation set under [`docs/`](docs/), enhanced examples, a local
  Nacos Docker Compose file, and a documentation-consistency check (0.7.0).
- Broad compatibility: Python 3.8-3.13 and Flask `>=1.0,<4.0` (1.x/2.x/3.x),
  tolerant handling of different Nacos SDK response shapes, a Python-3.8
  compatibility checker, and a Python x Flask CI matrix (0.8.0).
- Release Candidate preparation: frozen public API with an API-snapshot check,
  backward-compatibility tests, an examples validator, a package smoke test, and
  a 1.0.0 acceptance checklist (0.9.0).
- First stable release: the public API is declared stable for the 1.0 series and
  is verified by an API-snapshot check and backward-compatibility tests (1.0.0).

## Stable release

`1.0.0` is the first stable release of Flask-Nacos, intended for PyPI. The public
API is stable for the 1.0 series: method names, existing parameters, and return
contracts will not change without a deprecation cycle, and any new parameters
will be added with defaults so existing code keeps working.

- `get_config()` returns the raw Nacos config content only; it does not perform
  YAML, JSON, or dict parsing.
- This version does not provide `get_config_as_dict()`.
- This version does not provide `load_config_to_flask()`.
- Nacos configuration is never written into Flask `app.config` automatically.
- See the full pre-release verification in
  [docs/1.0-checklist.md](docs/1.0-checklist.md).

## Compatibility

- Python: 3.8 - 3.13.
- Flask: `>=1.0, <4.0` (Flask 1.x, 2.x, and 3.x).
- Nacos: server 2.x with the synchronous `nacos-sdk-python` client.
- Service discovery tolerates different SDK response shapes (plain list,
  `hosts`/`instances`, or a nested `data` wrapper) and both camelCase and
  snake_case instance fields.

See [Compatibility](docs/compatibility.md) for details.

## Installation

```bash
pip install flask-nacos
```

For local development (tests, linting, type checking, building):

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
)

nacos = FlaskNacos(app)
```

After initialization, `app.extensions["nacos"]` contains the extension state
mapping with its `config` and `client` entries. Continue using the `nacos`
variable above to call `FlaskNacos` methods.

## Documentation

Full documentation lives under [`docs/`](docs/):

- [Quickstart](docs/quickstart.md) - install and first app.
- [Configuration](docs/configuration.md) - every config key, grouped.
- [API Reference](docs/api-reference.md) - public methods and error behavior.
- [Service Registration](docs/service-registration.md) - register/deregister.
- [Service Discovery](docs/service-discovery.md) - listing and strategies.
- [Health Check](docs/health-check.md) - the optional health route.
- [Production](docs/production.md) - Gunicorn/uWSGI/Docker deployment.
- [Troubleshooting](docs/troubleshooting.md) - common issues and fixes.
- [Compatibility](docs/compatibility.md) - supported Python/Flask/Nacos versions.
- [1.0.0 Checklist](docs/1.0-checklist.md) - release-candidate acceptance list.
- [Release Guide](docs/release.md) - publishing to TestPyPI/PyPI.
- [Changelog](docs/changelog.md) - links to the full changelog.

## Flask Standard Mode

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.from_object("config.Config")

nacos = FlaskNacos(app)
```

## Flask Factory Mode

```python
from flask import Flask
from flask_nacos import FlaskNacos

nacos = FlaskNacos()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    nacos.init_app(app)
    return app
```

## Service Registration

When `NACOS_REGISTER_ENABLED` and `NACOS_AUTO_REGISTER` are both `True`, the
service is registered automatically during `init_app(app)`. You can also
register manually. `NACOS_REGISTER_ENABLED` only controls init-time automatic
registration; it does not disable an explicit `register_instance()` call:

```python
nacos.register_instance()
```

### Registration Parameter Rules

The following are validated before an instance is registered. Invalid values
follow the `NACOS_FAIL_FAST` rule (see [Exception Handling](#exception-handling)):

- `NACOS_SERVICE_NAME` - required, must be non-empty.
- `NACOS_SERVICE_PORT` - required, must be an integer in the range `1-65535`.
- `NACOS_SERVICE_WEIGHT` - must be a finite number greater than `0`.
- `NACOS_SERVICE_METADATA` - must be a `dict`.
- `NACOS_SERVICE_EPHEMERAL` - must be a `bool`.

Registration is idempotent: calling `register_instance()` multiple times on the
same extension instance registers only once (subsequent calls are no-ops).

### Service IP Auto-detection

If `NACOS_SERVICE_IP` is not provided, the extension attempts to detect the
local outbound IP via the `get_local_ip()` helper. If detection fails, the
behavior follows the `NACOS_FAIL_FAST` rule.

> Production recommendation: explicitly configure `NACOS_SERVICE_IP` rather than
> relying on auto-detection. In containers, multi-NIC hosts, or behind NAT the
> auto-detected address may not be the one you want other services to reach.

## Service Deregistration

When `NACOS_AUTO_DEREGISTER` is `True`, an instance successfully registered by
this extension is deregistered on process exit via `atexit`. You can also
deregister manually:

```python
nacos.deregister_instance()
```

Deregistration is idempotent: once an instance has been deregistered, further
`deregister_instance()` calls are no-ops and never raise.

## Service Discovery

```python
# List instances (healthy only by default)
instances = nacos.list_instances("user-service")

# List all instances of a specific group
instances = nacos.list_instances("user-service", group="DEFAULT_GROUP", healthy_only=False)

# Get a single healthy instance
instance = nacos.get_one_healthy_instance("user-service")
```

- `service_name` is required; an empty value follows the `NACOS_FAIL_FAST` rule.
- `group` falls back to `NACOS_GROUP_NAME` when omitted.
- `healthy_only=True` (default) returns only healthy instances; `healthy_only=False`
  returns all instances.
- An empty result is returned as an empty list (not an error).
- `get_one_healthy_instance()` supports pluggable selection strategies
  (`first`, `random`, `weight`) and optional cluster/metadata filtering. See
  "Service Discovery Enhancements (0.4.0)" below.

## Configuration Center

```python
content = nacos.get_config("application.yaml")
```

`data_id` is required. `group` falls back to `NACOS_CONFIG_GROUP` (and then to
`NACOS_GROUP_NAME`) when omitted. The raw content string from Nacos is returned
as-is; no YAML, JSON, or dict parsing is performed.

## Production Readiness (0.3.0)

Version 0.3.0 adds features aimed at production use: retries, a request-timeout
setting, an optional health-check route, a runtime status inspector, and finer
control over auto-registration.

### Retry

`register_instance()`, `deregister_instance()`, `list_instances()`, and
`get_config()` are wrapped in a unified retry helper.

- `NACOS_RETRY_ENABLED` (default `True`): enable retries. When `False`, each
  operation runs exactly once.
- `NACOS_RETRY_TIMES` (default `3`): maximum number of attempts (not extra
  retries). `3` means the operation is attempted up to 3 times.
- `NACOS_RETRY_INTERVAL` (default `1.0`): seconds to wait between attempts.

Each failed attempt is logged at `warning` level. After the final failure the
`NACOS_FAIL_FAST` rule decides whether to raise or return a safe default.
Deterministic input and validation errors fail immediately without retrying or
waiting for backoff.

### Request Timeout

- `NACOS_REQUEST_TIMEOUT` (default `5.0`) is passed to synchronous SDK 2.x
  configuration-center `get_config(..., timeout=...)` calls.

### Health Check Route

When `NACOS_HEALTH_CHECK_ENABLED` is `True`, a Flask route is registered at
`NACOS_HEALTH_CHECK_PATH` (default `/health/nacos`). It reports only the
extension's internal state and never calls the Nacos server, so it stays fast.

```json
{
  "status": "ok",
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true,
  "service_name": "fund-service",
  "service_ip": "127.0.0.1",
  "service_port": 5000
}
```

When Nacos is disabled:

```json
{
  "status": "disabled",
  "nacos_enabled": false,
  "client_initialized": false,
  "registered": false
}
```

When client initialization failed:

```json
{
  "status": "error",
  "nacos_enabled": true,
  "client_initialized": false,
  "registered": false
}
```

The route is registered idempotently: repeated `init_app(app)` calls or a
pre-existing route will not cause Flask to raise.

### Runtime Status

```python
status = nacos.get_status()
```

Returns the extension's internal state and non-sensitive configuration only. It
never calls Nacos and never includes `NACOS_PASSWORD`, `NACOS_ACCESS_KEY`, or
`NACOS_SECRET_KEY`:

```python
{
    "nacos_enabled": True,
    "client_initialized": True,
    "registered": True,
    "service_name": "fund-service",
    "service_ip": "127.0.0.1",
    "service_port": 5000,
    "server_addr": "127.0.0.1:8848",
    "namespace_id": "",
}
```

### Auto-registration Control

Two switches control init-time registration:

- `NACOS_AUTO_REGISTER` (default `True`): master switch for auto-registration.
- `NACOS_AUTO_REGISTER_ON_INIT` (default `True`): whether `init_app(app)`
  performs the auto-registration.

The service is auto-registered during `init_app(app)` only when both are `True`
(and `NACOS_REGISTER_ENABLED` is `True`). You can always register manually:

```python
nacos.register_instance()
```

### Gunicorn / Multi-worker Deployment

Under Gunicorn/uWSGI each worker process runs `init_app` and would register its
own instance. For more predictable behavior consider setting
`NACOS_AUTO_REGISTER_ON_INIT = False` and registering explicitly from a defined
startup hook (for example a post-fork hook or a management command) instead of
implicitly at import/init time.

In production, always set `NACOS_SERVICE_NAME`, `NACOS_SERVICE_IP`, and
`NACOS_SERVICE_PORT` explicitly rather than relying on auto-detection.

## Production Deployment & Service Discovery (0.4.0)

Version 0.4.0 focuses on multi-worker deployment safety and richer service
discovery: per-process registration lifecycle, safe deregistration, instance
normalization, discovery filtering, and pluggable selection strategies.

### Multi-worker Registration (Gunicorn / uWSGI)

Under Gunicorn or uWSGI, the master process forks multiple workers and each
worker runs `init_app`. flask-nacos tracks the process id that performed the
registration:

- `NACOS_REGISTER_ONCE_PER_PROCESS` (default `True`): within the same process,
  once `register_instance()` succeeds, repeated calls are skipped. When a worker
  is forked and the process id changes, the new worker is allowed to register
  its own instance.
- On shutdown, `deregister_instance()` only deregisters the instance registered
  by the current process. If the recorded registration pid differs from the
  current process (for example the master vs a worker), deregistration is logged
  and skipped so another process's instance is not removed by mistake.

Gunicorn example (register per worker, deregister on worker exit):

```python
# wsgi.py
from myapp import create_app

app = create_app()  # init_app runs here; each forked worker registers itself
```

```bash
gunicorn -w 4 wsgi:app
```

uWSGI behaves the same way; each worker process registers and deregisters its
own instance. If you prefer to control registration explicitly, set
`NACOS_AUTO_REGISTER_ON_INIT = False` and call `nacos.register_instance()` from a
post-fork hook.

### Deregistration on Exit

- `NACOS_DEREGISTER_ON_EXIT` (default `True`): whether an `atexit` handler is
  registered to deregister on process exit.
- The `atexit` handler is only registered when both `NACOS_AUTO_DEREGISTER` and
  `NACOS_DEREGISTER_ON_EXIT` are `True`, and it is registered at most once per
  extension instance (repeated `init_app(app)` calls do not add duplicates).
- The handler only deregisters an instance that this extension successfully
  registered; it is a no-op when registration never occurred or failed.

### Instance Normalization

- `NACOS_INSTANCE_NORMALIZE` (default `True`): when enabled, `list_instances()`
  returns a list of standard dicts. When disabled, the raw SDK instances are
  returned unchanged.

```python
instance = nacos.normalize_instance(raw_sdk_instance)
```

The standard dict shape:

```python
{
    "ip": "127.0.0.1",
    "port": 5000,
    "service_name": "user-service",
    "cluster_name": "DEFAULT",
    "weight": 1.0,
    "healthy": True,
    "enabled": True,
    "ephemeral": True,
    "metadata": {},
}
```

`normalize_instance()` accepts dict or attribute-style instances, fills missing
fields with sensible defaults, and never raises for a single bad instance (it
logs and returns `None`). During discovery a single instance that fails
normalization is skipped rather than failing the whole call.

### Discovery Filtering

`list_instances()` accepts optional `cluster` and `metadata` filters:

```python
nacos.list_instances("user-service", cluster="CANARY")
nacos.list_instances("user-service", metadata={"version": "v1"})
```

- `cluster` falls back to `NACOS_DISCOVERY_CLUSTER` when not provided.
- `metadata` falls back to `NACOS_DISCOVERY_METADATA` when omitted or `None`;
  pass `{}` to explicitly disable the configured metadata filter.
- When `cluster` is set, only instances in that cluster are returned.
- When `metadata` is set, only instances whose metadata contains all the given
  key/value pairs are returned.
- An empty result after filtering is returned as an empty list.

### Selection Strategies

`get_one_healthy_instance()` accepts an optional `strategy` (falling back to
`NACOS_DISCOVERY_STRATEGY`, default `first`), plus the same `cluster`/`metadata`
filters:

```python
# first (default): return the first healthy instance
nacos.get_one_healthy_instance("user-service", strategy="first")

# random: pick a random healthy instance
nacos.get_one_healthy_instance("user-service", strategy="random")

# weight: weighted-random selection using each instance's weight
nacos.get_one_healthy_instance("user-service", strategy="weight")
```

Currently supported strategies: `first`, `random`, `weight`.

- `first`: returns the first healthy instance.
- `random`: returns a uniformly random healthy instance.
- `weight`: weighted-random selection using each instance's `weight` (missing
  weight defaults to `1.0`; instances with weight `<= 0` are ignored; if all
  weights are `<= 0` the strategy degrades to `first`).
- When there are no healthy instances, `None` is returned.
- An unsupported strategy follows the `NACOS_FAIL_FAST` rule (`None` when
  `False`, raises when `True`).

### Runtime Status (new fields)

`get_status()` now also reports process and discovery information (still
secret-free and without calling Nacos):

```python
{
    # ... existing fields ...
    "current_pid": 12345,
    "registered_pid": 12345,
    "register_once_per_process": True,
    "deregister_on_exit": True,
    "discovery_strategy": "first",
    "instance_normalize": True,
    "health_check_enabled": True,
    "health_check_path": "/health/nacos",
}
```

### Configuration Center (unchanged)

`get_config()` still returns the raw config content from Nacos as-is; no YAML,
JSON, or dict parsing is performed.

## Configuration Reference

| Key | Default | Description |
| --- | --- | --- |
| `NACOS_ENABLED` | `True` | Master switch; when `False` no client is created. |
| `NACOS_SERVER_ADDR` | `"127.0.0.1:8848"` | Nacos server address (required). |
| `NACOS_NAMESPACE_ID` | `""` | Namespace id. |
| `NACOS_USERNAME` | `None` | Username for authentication. |
| `NACOS_PASSWORD` | `None` | Password for authentication. |
| `NACOS_ACCESS_KEY` | `None` | Access key for authentication. |
| `NACOS_SECRET_KEY` | `None` | Secret key for authentication. |
| `NACOS_GROUP_NAME` | `"DEFAULT_GROUP"` | Default group. |
| `NACOS_REGISTER_ENABLED` | `True` | Enable init-time automatic registration; manual registration remains available. |
| `NACOS_AUTO_REGISTER` | `True` | Auto register during `init_app`. |
| `NACOS_AUTO_DEREGISTER` | `True` | Auto deregister on exit. |
| `NACOS_SERVICE_NAME` | `None` | Service name (required to register). |
| `NACOS_SERVICE_IP` | `None` | Service IP; auto-detected if unset. |
| `NACOS_SERVICE_PORT` | `None` | Service port (required to register). |
| `NACOS_SERVICE_GROUP` | `"DEFAULT_GROUP"` | Group used for registration. |
| `NACOS_SERVICE_CLUSTER` | `"DEFAULT"` | Cluster name. |
| `NACOS_SERVICE_WEIGHT` | `1.0` | Load-balancing weight. |
| `NACOS_SERVICE_METADATA` | `{}` | Instance metadata dict. |
| `NACOS_SERVICE_EPHEMERAL` | `True` | Register as ephemeral instance. |
| `NACOS_SERVICE_HEALTHY` | `True` | Initial healthy flag. |
| `NACOS_SERVICE_ENABLED` | `True` | Instance enabled flag. |
| `NACOS_CONFIG_ENABLED` | `True` | Enable config-center features. |
| `NACOS_CONFIG_DATA_ID` | `None` | Default config data id. |
| `NACOS_CONFIG_GROUP` | `"DEFAULT_GROUP"` | Default config group. |
| `NACOS_RETRY_ENABLED` | `True` | Enable retries for Nacos operations. |
| `NACOS_RETRY_TIMES` | `3` | Maximum number of attempts per operation. |
| `NACOS_RETRY_INTERVAL` | `1.0` | Seconds between retry attempts. |
| `NACOS_REQUEST_TIMEOUT` | `5.0` | Timeout passed to config-center read calls. |
| `NACOS_HEALTH_CHECK_ENABLED` | `False` | Register the Flask health-check route. |
| `NACOS_HEALTH_CHECK_PATH` | `"/health/nacos"` | Path of the health-check route. |
| `NACOS_STATUS_ENABLED` | `True` | Deprecated no-op retained for 1.x compatibility; planned for removal in 2.0. |
| `NACOS_AUTO_REGISTER_ON_INIT` | `True` | Auto register during `init_app` (with `NACOS_AUTO_REGISTER`). |
| `NACOS_REGISTER_ONCE_PER_PROCESS` | `True` | Register only once per process; a forked worker (new pid) may re-register. |
| `NACOS_DEREGISTER_ON_EXIT` | `True` | Register an `atexit` handler to deregister on process exit. |
| `NACOS_DISCOVERY_STRATEGY` | `"first"` | Default strategy for `get_one_healthy_instance` (`first`/`random`/`weight`). |
| `NACOS_DISCOVERY_CLUSTER` | `None` | Default cluster filter for discovery. |
| `NACOS_DISCOVERY_METADATA` | `{}` | Default metadata filter for discovery. |
| `NACOS_INSTANCE_NORMALIZE` | `True` | Return normalized instance dicts from `list_instances`. |
| `NACOS_FAIL_FAST` | `False` | Raise on Nacos errors when `True`. |
| `NACOS_LOG_LEVEL` | `"INFO"` | Logging level for `flask_nacos`. |

## Exception Handling

The behavior on failure is controlled by `NACOS_FAIL_FAST`. This covers Nacos
client initialization, registration, deregistration, discovery, registration
parameter validation, and local IP auto-detection:

- `NACOS_FAIL_FAST = False` (default): failures are logged and do not prevent
  the Flask app from starting. Methods return safe defaults:
  - `register_instance()` -> `False`
  - `deregister_instance()` -> `False`
  - `list_instances()` -> `[]`
  - `get_one_healthy_instance()` -> `None`
  - `get_config()` -> `None`
- `NACOS_FAIL_FAST = True`: failures raise an exception.

Exception hierarchy:

```python
from flask_nacos import (
    FlaskNacosError,
    NacosConfigError,
    NacosClientError,
    NacosValidationError,
    NacosRegistrationError,
    NacosDeregistrationError,
    NacosDiscoveryError,
)
```

- `FlaskNacosError` — base class.
- `NacosConfigError` — invalid config or config-read failures.
- `NacosClientError` — Nacos client creation/usage failures.
- `NacosValidationError` — registration parameter validation failures (subclass
  of `NacosConfigError`).
- `NacosRegistrationError` — service registration failures.
- `NacosDeregistrationError` — service deregistration failures.
- `NacosDiscoveryError` — discovery failures.

## Production Notes

- Under multi-worker servers (Gunicorn/uWSGI) each worker registers its own
  instance. The `atexit`-based deregistration is best-effort; more complete
  multi-worker handling is planned for a later release.
- Never commit real credentials, internal Nacos addresses, or internal IPs.
  Prefer environment variables for `NACOS_USERNAME` / `NACOS_PASSWORD`.
- Secrets (`NACOS_PASSWORD`, `NACOS_ACCESS_KEY`, `NACOS_SECRET_KEY`) are never
  written to logs.
- A sensitive-information scan (`scripts/check_sensitive_info.py`) runs in CI to
  guard against accidentally committed secrets, private IPs, or `.env` files.

## Examples

Runnable examples live in the [`examples/`](examples/) directory:

- [`examples/basic_app.py`](examples/basic_app.py) — Flask standard mode with
  `FlaskNacos(app)`.
- [`examples/factory_app.py`](examples/factory_app.py) — Flask application
  factory mode with `nacos.init_app(app)`.
- [`examples/service_registration.py`](examples/service_registration.py) —
  manual and automatic registration and deregistration.
- [`examples/service_discovery.py`](examples/service_discovery.py) — listing
  instances, cluster/metadata filtering, and `get_one_healthy_instance()`.
- [`examples/health_check_app.py`](examples/health_check_app.py) — enabling the
  health-check route via `NACOS_HEALTH_CHECK_ENABLED` / `NACOS_HEALTH_CHECK_PATH`.
- [`examples/production_config.py`](examples/production_config.py) — env-var
  driven configuration for multi-worker deployments.
- [`examples/docker-compose-nacos.yml`](examples/docker-compose-nacos.yml) — a
  local Nacos for manual testing (local use only).

The examples use `127.0.0.1:8848` and the local demo credentials `nacos/nacos`;
replace them with your own configuration (preferably via environment variables).

Start a local Nacos for manual testing:

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

## Local Development & Testing

Install the dev extras into your virtual environment, then run the tooling. All
Nacos interactions in the test suite are mocked, so no real Nacos server is
required.

```bash
# Linux / macOS
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy flask_nacos
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

```powershell
# Windows (PowerShell)
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy flask_nacos
.venv\Scripts\python -m build
.venv\Scripts\python -m twine check dist/*
```

Test coverage is reported automatically (`--cov=flask_nacos`); there is no hard
coverage threshold, so it never blocks development.

## Type Hints

`flask-nacos` ships inline type hints and a `py.typed` marker (PEP 561), so type
checkers such as mypy and Pyright pick up the package's types automatically once
it is installed — no separate stub package is needed.

## PyPI Release Preparation

Before publishing a release, run the one-shot pre-release checks from the
repository root:

```bash
bash scripts/release_check.sh
```

This runs `ruff`, `mypy`, `pytest`, the version-consistency check, the
sensitive-information scan, a clean `python -m build`, `twine check`, and the
package-content check — without uploading anything. The individual scripts are:

- [`scripts/check_version.py`](scripts/check_version.py) — verifies the version
  is consistent across `pyproject.toml`, `__version__`, and `CHANGELOG.md`.
- [`scripts/check_sensitive_info.py`](scripts/check_sensitive_info.py) — scans
  for hardcoded secrets, private IPs, internal domains, and `.env` files.
- [`scripts/check_package.py`](scripts/check_package.py) — inspects the built
  wheel to confirm `py.typed` and core modules ship and tests/caches do not.

The manual `Release` workflow ([`.github/workflows/release.yml`](.github/workflows/release.yml))
reruns these checks and uploads to TestPyPI (default) or PyPI (explicit). See
[`docs/release.md`](docs/release.md) for the full release procedure, TestPyPI/PyPI
flow, and GitHub Secrets setup (`TEST_PYPI_API_TOKEN`, `PYPI_API_TOKEN`).

Publishing to PyPI is never automated on push; CI only lints, type checks,
tests, builds, and runs the release-check scripts.

## Compatibility

- Flask: `>=1.0, <4.0`
- Python: `>=3.8`
- Nacos: 2.x
- Nacos SDK: `nacos-sdk-python>=2.0.0,<3.0.0` (synchronous client)

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
