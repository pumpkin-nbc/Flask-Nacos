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

## Installation

```bash
pip install flask-nacos
```

Optional YAML support (reserved for future config parsing helpers):

```bash
pip install "flask-nacos[yaml]"
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

After initialization the extension instance is available at
`app.extensions["nacos"]`.

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
register manually:

```python
nacos.register_instance()
```

### Registration Parameter Rules

The following are validated before an instance is registered. Invalid values
follow the `NACOS_FAIL_FAST` rule (see [Exception Handling](#exception-handling)):

- `NACOS_SERVICE_NAME` - required, must be non-empty.
- `NACOS_SERVICE_PORT` - required, must be an integer in the range `1-65535`.
- `NACOS_SERVICE_WEIGHT` - must be a number greater than `0`.
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

When `NACOS_AUTO_DEREGISTER` is `True`, the instance is deregistered on process
exit via `atexit`. You can also deregister manually:

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
- `get_one_healthy_instance()` currently returns the first healthy instance.
  Random, round-robin, and weighted load-balancing strategies are planned for a
  later release.

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

### Request Timeout

- `NACOS_REQUEST_TIMEOUT` (default `5.0`).

> Reserved setting: the bundled synchronous `nacos-sdk-python` (2.x) client does
> not expose a reliable per-request timeout, so this value is read and exposed
> via `get_status()`/config but is not currently applied to SDK calls. It is
> reserved so applications can configure it today and have it take effect in a
> future release without config changes.

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
| `NACOS_REGISTER_ENABLED` | `True` | Enable service registration. |
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
| `NACOS_REQUEST_TIMEOUT` | `5.0` | Request timeout (reserved; see Production Readiness). |
| `NACOS_HEALTH_CHECK_ENABLED` | `False` | Register the Flask health-check route. |
| `NACOS_HEALTH_CHECK_PATH` | `"/health/nacos"` | Path of the health-check route. |
| `NACOS_STATUS_ENABLED` | `True` | Enable runtime status querying. |
| `NACOS_AUTO_REGISTER_ON_INIT` | `True` | Auto register during `init_app` (with `NACOS_AUTO_REGISTER`). |
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

## Compatibility

- Flask: `>=1.0, <4.0`
- Python: `>=3.8`
- Nacos: 2.x
- Nacos SDK: `nacos-sdk-python>=2.0.0,<3.0.0` (synchronous client)

## License

Licensed under the GNU General Public License v3.0 or later. See
[LICENSE](LICENSE).
