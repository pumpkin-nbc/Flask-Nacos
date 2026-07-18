# Configuration Reference

English | [简体中文](configuration.zh-CN.md)

All settings are read from Flask `app.config`. Missing keys fall back to the
defaults defined in `flask_nacos/config.py`. Boolean and numeric keys are
coerced from strings, so environment-variable style values work.

See also: [Quickstart](quickstart.md) - [API Reference](api-reference.md) -
[Production](production.md).

## Production and security notes

- Always set `NACOS_SERVICE_NAME`, `NACOS_SERVICE_IP`, and `NACOS_SERVICE_PORT`
  explicitly in production rather than relying on auto-detection. In containers,
  multi-NIC hosts, or behind NAT the auto-detected IP may not be reachable.
- Never commit sensitive values such as `NACOS_PASSWORD`, `NACOS_ACCESS_KEY`, or
  `NACOS_SECRET_KEY` to the repository. Inject them via environment variables or
  a secrets manager. These values are never written to logs.

## 1. Nacos connection

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_ENABLED` | bool | `True` | no | Master switch; when `False` no client is created and all operations are no-ops. |
| `NACOS_SERVER_ADDR` | str | `"127.0.0.1:8848"` | yes | Nacos server address (`host:port`). |
| `NACOS_NAMESPACE_ID` | str | `""` | no | Namespace id. |
| `NACOS_USERNAME` | str | `None` | no | Username for authentication. |
| `NACOS_PASSWORD` | str | `None` | no | Password for authentication (keep out of source control). |
| `NACOS_ACCESS_KEY` | str | `None` | no | Access key for authentication (secret). |
| `NACOS_SECRET_KEY` | str | `None` | no | Secret key for authentication (secret). |
| `NACOS_GROUP_NAME` | str | `"DEFAULT_GROUP"` | no | Default group used as a fallback. |

`NACOS_SERVER_ADDR` and `NACOS_SERVICE_IP` are not interchangeable:

- `NACOS_SERVER_ADDR` is the Nacos API endpoint the Flask process connects to.
- `NACOS_SERVICE_IP` is the Flask address registered for consumers, paired with
  `NACOS_SERVICE_PORT`.

For a documentation topology where Nacos is `203.0.113.10:8848` and Flask is
`203.0.113.20:5000`, use those two values respectively. Test the first path from
the Flask host and the second from a consumer host. See the
[Quickstart](quickstart.md#connecting-to-an-existing-authenticated-nacos) for
PowerShell/Bash connectivity commands and Docker/NAT guidance.

Example:

```python
import os

app.config.update(
    NACOS_SERVER_ADDR=os.environ["NACOS_SERVER_ADDR"],
    NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
    NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
    NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
    NACOS_ACCESS_KEY=os.environ.get("NACOS_ACCESS_KEY"),
    NACOS_SECRET_KEY=os.environ.get("NACOS_SECRET_KEY"),
)
```

Use the namespace ID rather than its display name. Prefer username/password or
AK/SK according to the server's authentication mode; do not hardcode either.

## 2. Service registration

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_REGISTER_ENABLED` | bool | `True` | no | Enable init-time automatic registration; manual registration is unaffected. |
| `NACOS_AUTO_REGISTER` | bool | `True` | no | Master switch for auto-registration. |
| `NACOS_AUTO_DEREGISTER` | bool | `True` | no | Deregister automatically on exit. |
| `NACOS_SERVICE_NAME` | str | `None` | yes (to register) | Service name. |
| `NACOS_SERVICE_IP` | str | `None` | recommended | Service IP; auto-detected if unset. |
| `NACOS_SERVICE_PORT` | int | `None` | yes (to register) | Service port, `1-65535`. |
| `NACOS_SERVICE_GROUP` | str | `"DEFAULT_GROUP"` | no | Group used for registration. |
| `NACOS_SERVICE_CLUSTER` | str | `"DEFAULT"` | no | Cluster name. |
| `NACOS_SERVICE_WEIGHT` | float | `1.0` | no | Finite load-balancing weight (`> 0`). |
| `NACOS_SERVICE_METADATA` | dict | `{}` | no | Instance metadata. |
| `NACOS_SERVICE_EPHEMERAL` | bool | `True` | no | Register as an ephemeral instance. |
| `NACOS_SERVICE_HEALTHY` | bool | `True` | no | Initial healthy flag. |
| `NACOS_SERVICE_ENABLED` | bool | `True` | no | Instance enabled flag. |

Example:

```python
app.config.update(
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_SERVICE_METADATA={"version": "v1"},
)
```

Production tip: set `NACOS_SERVICE_NAME`, `NACOS_SERVICE_IP`, and
`NACOS_SERVICE_PORT` explicitly.

## 3. Service discovery

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_DISCOVERY_STRATEGY` | str | `"first"` | no | Default strategy for `get_one_healthy_instance` (`first`/`random`/`weight`). |
| `NACOS_DISCOVERY_CLUSTER` | str | `None` | no | Default cluster filter. |
| `NACOS_DISCOVERY_METADATA` | dict | `{}` | no | Default metadata filter. |
| `NACOS_INSTANCE_NORMALIZE` | bool | `True` | no | Return normalized instance dicts from `list_instances`. |

Example:

```python
app.config.update(
    NACOS_DISCOVERY_STRATEGY="weight",
    NACOS_DISCOVERY_CLUSTER="DEFAULT",
)
```

## 4. Health check

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_HEALTH_CHECK_ENABLED` | bool | `False` | no | Register the Flask health-check route. |
| `NACOS_HEALTH_CHECK_PATH` | str | `"/health/nacos"` | no | Path of the health-check route. |

Example:

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

## 5. Retry

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_RETRY_ENABLED` | bool | `True` | no | Enable retries for Nacos operations. |
| `NACOS_RETRY_TIMES` | int | `3` | no | Maximum number of attempts per operation. |
| `NACOS_RETRY_INTERVAL` | float | `1.0` | no | Seconds between attempts. |
| `NACOS_REQUEST_TIMEOUT` | float | `5.0` | no | Timeout passed to SDK 2.x config-center read calls. |

Example:

```python
app.config.update(
    NACOS_RETRY_ENABLED=True,
    NACOS_RETRY_TIMES=3,
    NACOS_RETRY_INTERVAL=1.0,
)
```

## 6. Runtime status

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_STATUS_ENABLED` | bool | `True` | no | Deprecated no-op retained for 1.x compatibility; planned for removal in 2.0. |

## 7. Lifecycle

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_AUTO_REGISTER_ON_INIT` | bool | `True` | no | Whether `init_app(app)` performs auto-registration. |
| `NACOS_REGISTER_ONCE_PER_PROCESS` | bool | `True` | no | Register only once per process; a forked worker (new pid) may re-register. |
| `NACOS_DEREGISTER_ON_EXIT` | bool | `True` | no | Register an `atexit` handler to deregister on process exit. |

Example (explicit registration under Gunicorn):

```python
app.config["NACOS_AUTO_REGISTER_ON_INIT"] = False
```

## 8. Logging

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_LOG_LEVEL` | str | `"INFO"` | no | Logging level for the `flask_nacos` logger. Secrets are never logged. |

## 9. Behavior control

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_FAIL_FAST` | bool | `False` | no | When `True`, Nacos errors raise; when `False`, they are logged and safe defaults are returned. |

See [API Reference](api-reference.md) for how `NACOS_FAIL_FAST` affects each
method.

## Configuration center

| Key | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| `NACOS_CONFIG_ENABLED` | bool | `True` | no | Enable config-center features. |
| `NACOS_CONFIG_DATA_ID` | str | `None` | no | Default config data id. |
| `NACOS_CONFIG_GROUP` | str | `"DEFAULT_GROUP"` | no | Default config group. |

`get_config()` returns the raw configuration content string only. It does not
perform YAML, JSON, or dict parsing, and does not write into `app.config`.
When `data_id` is omitted it uses `NACOS_CONFIG_DATA_ID`. Disabling
`NACOS_CONFIG_ENABLED` skips the SDK call and returns `None`.
