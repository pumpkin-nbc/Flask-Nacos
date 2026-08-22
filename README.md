# Flask-Nacos

[![PyPI](https://img.shields.io/pypi/v/flask-nacos.svg)](https://pypi.org/project/flask-nacos/)
[![Python](https://img.shields.io/pypi/pyversions/flask-nacos.svg)](https://pypi.org/project/flask-nacos/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/LICENSE)

English | [简体中文](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/README.zh-CN.md)

Flask-Nacos integrates Flask with Nacos service registration, discovery, and
configuration center. Version 1.1.1 uses a target-state lifecycle, lazy
app/PID-bound Clients, and strict multi-application isolation.

## New users start here

- [Beginner quickstart](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/quickstart.md)
- [Complete application-factory example](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/complete-example.md)
- [Configuration reference](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/configuration.md)
- [API reference](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/api-reference.md)
- [Service registration lifecycle](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/service-registration.md)
- [Service discovery](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/service-discovery.md)
- [Health check](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/health-check.md)
- [Production deployment](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/production.md)
- [Troubleshooting](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/troubleshooting.md)
- [Compatibility matrix](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/compatibility.md)
- [Changelog](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/CHANGELOG.md)

## Features

- Flask extension and application-factory integration.
- Nacos Naming registration/deregistration with exact cached identity.
- Ephemeral-instance heartbeat delegated to Nacos SDK 2.x.
- Normalized discovery, cluster/metadata filtering, and first/random/weight
  selection.
- Raw configuration-center reads with configurable timeout.
- Target-state registration lifecycle with last-command-wins behavior.
- One lifecycle Worker and one Naming RPC at a time per app/PID Runtime.
- Lazy Client creation: initialization, status, and health remain SDK-free.
- Fork-safe PID Runtime rebuilding and strict multi-app context isolation.
- Sanitized colored console logs and optional rotating file logs.
- Python 3.8 syntax, type marker, and bilingual documentation.

## Compatibility

- Python `>=3.8`; CI verifies Python 3.8 through 3.14.
- Flask `>=1.0`; CI verifies valid combinations from Flask 1.0.x through 3.1.x.
- `nacos-sdk-python>=2.0.0,<3.0.0`.

Python 3.8 is tested with Flask 1.0.4, 1.1.4, 2.x, and 3.0.x. Flask 3.1
requires newer Python, so unsupported upstream combinations are not claimed.

## Installation

```bash
python -m pip install flask-nacos
```

Installing `flask-nacos` from PyPI also installs the compatible
`nacos-sdk-python` dependency. When validating from TestPyPI, use PyPI as the
dependency source because TestPyPI is not a complete mirror:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos==1.1.1
```

## Quick start

```python
from flask import Flask

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME="orders-api",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_HEALTH_CHECK_ENABLED=True,
)

nacos = FlaskNacos(app)
```

The default automatic-registration path is:

```text
init_app(app)
  -> validate deterministic configuration
  -> commit a Client-free PID Runtime
  -> call register_instance(app)
  -> return while a daemon Worker creates the Client and performs Naming I/O
```

`NACOS_AUTO_REGISTER` (default `True`) is the single automatic-registration
switch. Automatic registration runs when both `NACOS_ENABLED` and
`NACOS_AUTO_REGISTER` are enabled. Turning automatic registration off does not
block an explicit `register_instance(app)` command.

## Configuration quick reference

All settings are read from Flask `app.config`. This table matches the current
code defaults; see the [configuration reference](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/configuration.md)
for validation rules and complete examples.

| Setting | Default | Description |
| --- | --- | --- |
| `NACOS_ENABLED` | `True` | Master switch; when disabled, no Client is created and related operations are no-ops. |
| `NACOS_SERVER_ADDR` | `"127.0.0.1:8848"` | Nacos Server address in `host:port` form. |
| `NACOS_NAMESPACE_ID` | `""` | Namespace ID. |
| `NACOS_USERNAME` | `None` | Username authentication value; configure it together with the password. |
| `NACOS_PASSWORD` | `None` | Username authentication password; never commit it to source control. |
| `NACOS_ACCESS_KEY` | `None` | AccessKey authentication value; configure it together with the SecretKey. |
| `NACOS_SECRET_KEY` | `None` | SecretKey authentication value; never commit it to source control. |
| `NACOS_GROUP_NAME` | `"DEFAULT_GROUP"` | Default group fallback. |
| `NACOS_AUTO_REGISTER` | `True` | Submit the registration target during initialization and post-fork recovery. |
| `NACOS_DEREGISTER_ON_EXIT` | `True` | Install the best-effort normal-process-exit deregistration callback. |
| `NACOS_SERVICE_NAME` | `None` | Service name; required when registering. |
| `NACOS_SERVICE_IP` | `None` | Registered instance IP; auto-detected when unset. |
| `NACOS_SERVICE_PORT` | `None` | Registered instance port in `1-65535`; required when registering. |
| `NACOS_SERVICE_GROUP` | `"DEFAULT_GROUP"` | Group used for service registration. |
| `NACOS_SERVICE_CLUSTER` | `"DEFAULT"` | Cluster used for service registration. |
| `NACOS_SERVICE_WEIGHT` | `1.0` | Finite load-balancing weight greater than `0`. |
| `NACOS_SERVICE_METADATA` | `{}` | Registered instance metadata. |
| `NACOS_SERVICE_EPHEMERAL` | `True` | Register as an ephemeral instance. |
| `NACOS_SERVICE_HEARTBEAT_INTERVAL` | `5.0` | SDK heartbeat interval in seconds for ephemeral instances. |
| `NACOS_SERVICE_HEALTHY` | `True` | Initial health flag sent during registration. |
| `NACOS_SERVICE_ENABLED` | `True` | Whether the registered instance is enabled. |
| `NACOS_CONFIG_ENABLED` | `True` | Enable configuration-center features. |
| `NACOS_CONFIG_DATA_ID` | `None` | Default used when `get_config()` receives no `data_id`. |
| `NACOS_CONFIG_GROUP` | `"DEFAULT_GROUP"` | Default configuration-center group. |
| `NACOS_RETRY_ENABLED` | `True` | Enable finite retry and registration lifecycle recovery. |
| `NACOS_RETRY_TIMES` | `3` | Maximum finite-stage attempts; integer `>=1`. |
| `NACOS_RETRY_INTERVAL` | `1.0` | Finite delay between attempts in seconds; must be `>=0`. |
| `NACOS_REQUEST_TIMEOUT` | `5.0` | Configuration-center read timeout; does not override Naming Client timeout. |
| `NACOS_HEALTH_CHECK_ENABLED` | `False` | Register the Flask health-check route. |
| `NACOS_HEALTH_CHECK_PATH` | `"/health/nacos"` | Health-check route path. |
| `NACOS_DISCOVERY_STRATEGY` | `"first"` | Healthy-instance strategy: `first`, `random`, or `weight`. |
| `NACOS_DISCOVERY_CLUSTER` | `None` | Default discovery cluster filter. |
| `NACOS_DISCOVERY_METADATA` | `{}` | Default discovery metadata filter. |
| `NACOS_INSTANCE_NORMALIZE` | `True` | Return normalized instance dictionaries and skip malformed endpoints. |
| `NACOS_LOG_ENABLED` | `False` | Master switch for Flask-Nacos safety logs. |
| `NACOS_LOG_LEVEL` | `"INFO"` | Safety-log level. |
| `NACOS_LOG_CONSOLE_ENABLED` | `True` | Emit console records when logging is enabled. |
| `NACOS_LOG_FILE_ENABLED` | `True` | Write file records when logging is enabled. |
| `NACOS_LOG_PATH` | `"./logs"` | Log file directory. |
| `NACOS_LOG_FILENAME` | `"flask-nacos.log"` | Log filename inside `NACOS_LOG_PATH`. |
| `NACOS_LOG_FORMAT` | `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` | Format used by Flask-Nacos handlers. |
| `NACOS_LOG_PROPAGATE` | `True` | Propagate records to parent loggers. |
| `NACOS_LOG_MAX_BYTES` | `10485760` | Rotating-file size limit; `None` selects a plain file handler. |
| `NACOS_LOG_BACKUP_COUNT` | `5` | Number of rotated log backups to retain. |

## Application factory

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

Configuration must be loaded before `init_app(app)`. Calls without an explicit
app require the corresponding Flask app/request context. Flask-Nacos never
falls back to the first or most recently initialized application.

## Registration lifecycle

The public lifecycle API is deliberately small:

```python
nacos.register_instance(app)        # returns None immediately
removed = nacos.deregister_instance(app)
status = nacos.get_status(app)
client = nacos.get_client(app)
```

`register_instance(app=None) -> None` changes the final target to registered
and publishes at most one daemon convergence Worker. Client construction,
network retry, Naming RPC, and SDK heartbeat startup never delay the caller.

`deregister_instance(app=None) -> bool` changes the final target to
unregistered. It returns `True` for an idempotent/accepted/successful cleanup or
when a newer register command makes the RPC unnecessary, and `False` when
cleanup is still required but fails.

The Worker continually re-reads the latest target. A sequence such as register
→ deregister → register therefore ends at the final register target; an old
delayed command cannot permanently override it. Register, normal deregister,
compensating deregister, and exit deregister share one Naming single-flight
lock.

Successful registration caches the exact service/group/cluster/IP/port used by
the SDK. Every deregistration uses that identity; Flask-Nacos never guesses a
replacement IP. Registration success transfers ephemeral heartbeat ownership
to the SDK, and the Flask-Nacos Worker exits.

See the full [lifecycle diagrams and old/new scheduling table](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/docs/service-registration.md).

## Deterministic validation and retry

When automatic registration is enabled, `init_app(app)` validates
`NACOS_SERVICE_NAME`, port, weight, metadata, ephemeral/heartbeat settings,
authentication, and retry settings before creating extension state.

When automatic registration is disabled, initialization skips registration-only
validation. The first explicit `register_instance(app)` performs that local,
deterministic validation and caches its result without creating a Client or
performing network I/O.

Deterministic local errors for active automatic registration raise before
`app.extensions["nacos"]` is committed. An invalid explicit registration also
raises synchronously without changing the lifecycle target. Thread
creation/start, Client construction, timeout, connection, and SDK failures stay
inside the lifecycle Worker and are recorded by safe type/code in `last_error`.

Registration lifecycle failures are classified immediately and conservatively:

- deterministic configuration, authentication, permission, parameter, or
  invariant failures stop the Worker immediately;
- unknown failures use only the existing finite retry budget;
- explicitly identified transient transport failures use the same finite
  budget first, then continue low-frequency, interruptible lifecycle recovery
  with bounded backoff and jitter until the target changes, shutdown begins, a
  later failure is no longer transient, or registration succeeds.

Recovery covers both lazy Client construction and Naming registration when the
failure has verified transient evidence. In SDK `2.0.11`, the exact bare
`nacos.exception.NacosRequestException` raised while an authenticated Client is
constructed is covered only for the register direction. Structured 401/403
authentication failures remain deterministic and stop immediately.

`NACOS_RETRY_ENABLED=False` disables both finite retry and lifecycle recovery.
Recovery applies only to proven transient failures and does not poll remote
state. Once `registered == target_registered`, the Worker exits and the Nacos
SDK continues to own heartbeat and connection maintenance.

Heartbeat observability is Client-local: failures are throttled separately for
each service/group/cluster/IP/port identity, and the first successful beat after
a failure emits one recovery record. If a complete safe identity cannot be
extracted, logging falls back to stateless `<unknown>` records rather than a
possibly colliding key. These records never change Lifecycle state or trigger
registration.

`NACOS_RETRY_TIMES` must be an integer `>=1`; `NACOS_RETRY_INTERVAL` must be a
finite number `>=0`; `NACOS_REQUEST_TIMEOUT` must be finite and `>0` when the
configuration center is enabled. Numeric strings are accepted. Booleans, NaN,
Infinity, fractional attempt counts, and out-of-range values are rejected.

`NACOS_REQUEST_TIMEOUT` applies only to configuration-center reads. Naming RPCs
use the SDK Client's own `default_timeout`; shutdown snapshots that actual value
and waits for its remaining budget plus a small allowance, capped at five
seconds. It falls back to three seconds when no valid SDK timeout is available.

## Local status

`get_status(app=None)` returns exactly 16 local fields:

```python
{
    "enabled": True,
    "pid": 12345,
    "client_created": True,
    "service_name": "orders-api",
    "group_name": "DEFAULT_GROUP",
    "cluster_name": "DEFAULT",
    "service_ip": "203.0.113.20",
    "service_port": 5000,
    "target_registered": True,
    "registered": True,
    "operation_running": False,
    "last_error": None,
    "heartbeat_state": "healthy",
    "last_heartbeat_success_at": 1770000000.25,
    "last_heartbeat_failure_at": None,
    "heartbeat_error_type": None,
}
```

`registered` is the most recent local fact confirmed by a successful Naming
RPC, not a live Nacos query. `heartbeat_state` is the most recent local SDK
heartbeat observation for the current ephemeral registration cycle:
`unknown` before the first observed beat, `healthy` after success, `failing`
after failure, and `not_applicable` while disabled, unregistered, or persistent.
Heartbeat timestamps are Unix epoch seconds; the error field contains only a
safe exception type. These fields do not prove that the remote instance still
exists and never drive Lifecycle recovery.

Status does not create a Client, contact Nacos, detect an IP, start a thread,
or resume post-fork registration.

`get_client(app)` explicitly creates or returns the app/PID Client and raises a
safe `NacosConfigError` or `NacosClientError` if preparation fails. The `.client` property is cache-only
and requires a current Flask context.

## Health route

Enable it with:

```python
NACOS_HEALTH_CHECK_ENABLED = True
NACOS_HEALTH_CHECK_PATH = "/health/nacos"
```

It returns exactly `status`, `enabled`, `client_created`, `target_registered`,
`registered`, `operation_running`, and `last_error`. `status=ok` means local
lifecycle state is converged or is progressing without a recorded error. It is
not a remote Nacos or heartbeat probe and never creates a Client.

## Discovery

```python
with app.app_context():
    instances = nacos.list_instances("inventory-api")
    instance = nacos.get_one_healthy_instance(
        "inventory-api",
        strategy="weight",
        cluster="CANARY",
        metadata={"version": "v2"},
    )
```

Malformed instances are logged and skipped. IP must be a non-empty string and
port must be an integer from 1 to 65535. String booleans are normalized, and
invalid/non-finite weight falls back safely.

## Configuration center

```python
with app.app_context():
    content = nacos.get_config("application.yaml", group="DEFAULT_GROUP")
```

`get_config()` returns raw text. Flask-Nacos does not parse YAML/JSON and does
not write remote content into `app.config`.

`NACOS_USERNAME`/`NACOS_PASSWORD` must be configured as a complete pair,
`NACOS_ACCESS_KEY`/`NACOS_SECRET_KEY` must be a complete pair, and the two
authentication methods are mutually exclusive. Never commit real credentials.

## Logging

`NACOS_LOG_ENABLED=False` by default. SDK-native logs are isolated, so
Flask-Nacos does not create `~/logs/nacos` or an SDK log file. The complete
logging settings and defaults are listed in the quick-reference table above.

Console records use blue DEBUG, green INFO, yellow WARNING, red ERROR, and bold
red CRITICAL. File records contain no ANSI colors. When logging is disabled,
configured paths are not created.

Choose one logging topology to avoid duplicate output: either disable the
extension console/file handlers and keep `NACOS_LOG_PROPAGATE=True` so the host
owns all output, or enable the extension console handler with file output off
and set `NACOS_LOG_PROPAGATE=False` for container stdout. Do not let multiple
processes share one rotating file handler.

## Fork, Gunicorn, and shutdown

Runtime resources are bound to one Flask app and PID. After fork, the entire
parent Runtime is discarded. Explicit registration or a real Client,
Discovery, or Config SDK operation may resume automatic registration without
waiting for convergence; ordinary business requests, status, health, and
`.client` reads do not.

For Gunicorn `--preload`, use `NACOS_AUTO_REGISTER=False` and call
`nacos.register_instance(app)` in the post-fork/worker-init hook. This avoids
starting SDK runtime in the preload master.

Workers advertising the same service/group/cluster with the same IP and port
represent one Nacos instance. Set `NACOS_DEREGISTER_ON_EXIT=False` for a shared
endpoint so one exiting worker cannot delete it while others remain alive.

`NACOS_DEREGISTER_ON_EXIT=True` installs the process-exit deregistration
callback; `False` installs no remote-cleanup callback. The setting never blocks
an explicit `deregister_instance()`. On a normal interpreter exit, cleanup
never changes the user's target, never starts normal retry, and waits only a
bounded time for an already-active Naming RPC before one best-effort cleanup.
Forced termination such as `SIGKILL` cannot guarantee callback execution.

## Security note

The synchronous Nacos SDK 2.x line has limitations around HTTPS server
certificate verification. Use a trusted network or a certificate-validating
proxy/sidecar when transport policy requires verified TLS.

See the [security policy](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/SECURITY.md)
for private vulnerability reporting.

## Examples and development

- [Beginner app](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/examples/beginner_app.py)
- [Complete factory app](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/examples/complete_factory_app.py)
- [Service registration](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/examples/service_registration.py)
- [Service discovery](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/examples/service_discovery.py)

Local quality checks:

```bash
pytest
ruff check .
mypy flask_nacos
python scripts/check_api_snapshot.py
python scripts/check_docs.py
python scripts/check_examples.py
```

## License

Apache-2.0. See [LICENSE](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/LICENSE)
and [NOTICE](https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/NOTICE).
