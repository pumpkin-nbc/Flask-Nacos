# API Reference

English | [简体中文](api-reference.zh-CN.md)

Public API of the `FlaskNacos` extension. Unless a method-specific contract says
otherwise, error behavior is governed by `NACOS_FAIL_FAST` (see
[Configuration](configuration.md)): when `False` (default), failures are logged
and a safe default is returned; when `True`, an exception is raised. Background
registration failures occur after the caller returns and therefore remain in
local status instead of being raised into the old call stack.

See also: [Quickstart](quickstart.md) - [Configuration](configuration.md).

## API snapshot (1.1 series)

The API snapshot below is enforced for the supported 1.1 surface:

```python
FlaskNacos(app=None)
init_app(app)
get_client()
register_instance()
deregister_instance()
list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)
get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)
get_config(data_id=None, group=None)
get_status()
normalize_instance(instance)
```

`get_config()` returns the raw Nacos config content only.

- This package does not provide `get_config_as_dict()`.
- This package does not provide `load_config_to_flask()`.

The snapshot is enforced by `scripts/check_api_snapshot.py`.

## `FlaskNacos(app=None)`

Construct the extension. When `app` is provided, `init_app(app)` is called
immediately (Flask standard mode). When omitted, call `init_app(app)` later
(factory mode).

```python
from flask_nacos import FlaskNacos

nacos = FlaskNacos(app)          # standard mode
nacos = FlaskNacos()             # factory mode; call init_app later
```

## `init_app(app)`

Initialize the extension against a Flask `app`: load configuration, create the
Nacos client, register the health route (if enabled), and schedule background
service registration (enabled by default). Stores a state mapping containing `config` and
`client` at `app.extensions["nacos"]`.

- Parameters: `app` - the Flask application.
- Returns: `None`.
- Exceptions: deterministic config/client and registration-thread start errors
  follow `NACOS_FAIL_FAST`; background network failures are reported in status.

## `get_client()`

Return the underlying Nacos SDK client created by `init_app()`.

- Returns: the SDK client object, or `None` when Nacos is disabled or client
  creation failed and `NACOS_FAIL_FAST` is `False`.
- Exceptions: follows `NACOS_FAIL_FAST` on client creation failure.

## `register_instance()`

Request registration of the current service instance.

- Returns: `None` immediately; no SDK network I/O or retry runs in the caller.
- At most one background registration task runs per app and process. It reuses
  the validation, retry, identity, and heartbeat path.
- Deterministic config errors, client unavailability, and thread-start errors
  follow `NACOS_FAIL_FAST`. Network failures cannot return to the old call stack
  and are stored as a safe type in local status.
- Repeated calls are idempotent after registration and single-flight while a
  task is running. A failed task may be retried with a later explicit call.

```python
nacos.register_instance()
status = nacos.get_status()
```

See [Service Registration](service-registration.md) for lifecycle and deployment
details.

## `deregister_instance()`

Deregister the current service instance.

- Returns: `bool`. An absent instance returns `True` without SDK I/O. During
  registration, `True` means delayed cleanup was accepted. A registered
  instance is deregistered synchronously and returns the actual result.
- Exceptions: raises `NacosDeregistrationError` when `NACOS_FAIL_FAST` is `True`.

```python
nacos.deregister_instance()
```

## `list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)`

List service instances.

- Parameters:
  - `service_name` (required) - empty value follows `NACOS_FAIL_FAST`.
  - `group` - falls back to `NACOS_GROUP_NAME`.
  - `healthy_only` - default `True`.
  - `cluster` - falls back to `NACOS_DISCOVERY_CLUSTER`.
  - `metadata` - falls back to `NACOS_DISCOVERY_METADATA` when `None`; `{}`
    explicitly disables the configured filter. Matches instances that contain
    all given key/value pairs.
- Returns: `list` of instances (normalized dicts when `NACOS_INSTANCE_NORMALIZE`
  is `True`). Empty result is an empty list.
- Exceptions: raises `NacosDiscoveryError` when `NACOS_FAIL_FAST` is `True`.

```python
instances = nacos.list_instances("user-service", cluster="CANARY")
```

## `get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)`

Select a single healthy instance.

- Parameters: `strategy` falls back to `NACOS_DISCOVERY_STRATEGY` (`first`,
  `random`, `weight`); other parameters as in `list_instances`.
- Returns: a single instance, or `None` when there are no healthy instances.
- Exceptions: an unsupported strategy follows `NACOS_FAIL_FAST`; discovery errors
  raise `NacosDiscoveryError` when `NACOS_FAIL_FAST` is `True`.

```python
instance = nacos.get_one_healthy_instance("user-service", strategy="weight")
```

## `get_config(data_id=None, group=None)`

Read configuration content from Nacos.

- Parameters: `data_id` falls back to `NACOS_CONFIG_DATA_ID`; `group` falls back
  to `NACOS_CONFIG_GROUP` then `NACOS_GROUP_NAME`.
- Returns: the raw configuration content `str`, or `None` on failure when
  `NACOS_FAIL_FAST` is `False`. Returns `None` without an SDK call when
  `NACOS_CONFIG_ENABLED` is `False`.
- Exceptions: raises `NacosValidationError` when both data IDs are empty and
  fail-fast is enabled; other config failures raise `NacosConfigError`.
- Timeout: `NACOS_REQUEST_TIMEOUT` is passed to the SDK 2.x read call.

`get_config()` returns the raw Nacos configuration string only. It does not
perform YAML, JSON, or dict parsing, and it does not write into Flask
`app.config`.

```python
content = nacos.get_config("application.yaml")
```

## `get_status()`

Return the extension's internal state and non-sensitive configuration.

- Returns: `dict`. Never calls Nacos and never includes `NACOS_PASSWORD`,
  `NACOS_ACCESS_KEY`, or `NACOS_SECRET_KEY`.
- Lifecycle fields: `registration_in_progress`, `deregistration_requested`, and
  `last_registration_error_type`. The error field contains only a class name,
  never an exception message.

```python
status = nacos.get_status()
```

## `normalize_instance(instance)`

Normalize a raw SDK instance (dict or attribute-style) into a standard dict.

- Returns: a standard dict, or `None` for a single instance that cannot be
  normalized (logged, never raises for one bad instance).

```python
normalized = nacos.normalize_instance(raw_sdk_instance)
```

## Exceptions

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

- `FlaskNacosError` - base class.
- `NacosConfigError` - invalid config or config-read failures.
- `NacosClientError` - Nacos client creation/usage failures.
- `NacosValidationError` - deterministic input or numeric configuration validation (subclass of
  `NacosConfigError`).
- `NacosRegistrationError` / `NacosDeregistrationError` / `NacosDiscoveryError` -
  registration, deregistration, and discovery failures.
