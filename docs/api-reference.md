# API Reference

English | [简体中文](api-reference.zh-CN.md)

Public API of the `FlaskNacos` extension. All error behavior is governed by
`NACOS_FAIL_FAST` (see [Configuration](configuration.md)): when `False` (default)
failures are logged and a safe default is returned; when `True` an exception is
raised.

See also: [Quickstart](quickstart.md) - [Configuration](configuration.md) -
[1.0.0 Checklist](1.0-checklist.md).

## Stable API (1.0 series)

As of `1.0.0`, the public API below is stable. Method names, existing
parameters, and return contracts will not change without a deprecation cycle;
any new parameters will be added with defaults so existing calls keep working.
The stable surface is:

```python
FlaskNacos(app=None)
init_app(app)
get_client()
register_instance()
deregister_instance()
list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)
get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)
get_config(data_id, group=None)
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
Nacos client lazily, register the health route (if enabled), and auto-register
the service (if enabled). Stores the extension at `app.extensions["nacos"]`.

- Parameters: `app` - the Flask application.
- Returns: `None`.
- Exceptions: follows `NACOS_FAIL_FAST` for client/registration errors.

## `get_client()`

Return the underlying Nacos SDK client, creating it on first use.

- Returns: the SDK client object, or `None` when Nacos is disabled or client
  creation failed and `NACOS_FAIL_FAST` is `False`.
- Exceptions: follows `NACOS_FAIL_FAST` on client creation failure.

## `register_instance()`

Register the current service instance.

- Returns: `bool` - `True` on success, `False` on failure when
  `NACOS_FAIL_FAST` is `False`.
- Exceptions: raises `NacosValidationError` / `NacosRegistrationError` when
  `NACOS_FAIL_FAST` is `True`.
- Notes: idempotent; with `NACOS_REGISTER_ONCE_PER_PROCESS=True` repeated calls
  in the same process are no-ops.

```python
nacos.register_instance()
```

## `deregister_instance()`

Deregister the current service instance.

- Returns: `bool` - `True` on success, `False` otherwise (when
  `NACOS_FAIL_FAST` is `False`). Idempotent and never raises once already
  deregistered.
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
  - `metadata` - falls back to `NACOS_DISCOVERY_METADATA`; matches instances that
    contain all given key/value pairs.
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

## `get_config(data_id, group=None)`

Read configuration content from Nacos.

- Parameters: `data_id` (required); `group` falls back to `NACOS_CONFIG_GROUP`
  then `NACOS_GROUP_NAME`.
- Returns: the raw configuration content `str`, or `None` on failure when
  `NACOS_FAIL_FAST` is `False`.
- Exceptions: raises `NacosConfigError` when `NACOS_FAIL_FAST` is `True`.

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
- `NacosValidationError` - registration parameter validation (subclass of
  `NacosConfigError`).
- `NacosRegistrationError` / `NacosDeregistrationError` / `NacosDiscoveryError` -
  registration, deregistration, and discovery failures.
