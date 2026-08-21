# API Reference

English | [简体中文](api-reference.zh-CN.md)

Flask-Nacos 1.1.1 keeps lifecycle commands small and context-safe. An explicit
`app` always selects that application. Without `app`, an active Flask app or
request context is required; there is no fallback to a previously initialized
application.

## API snapshot (1.1 series)

```python
from flask_nacos import FlaskNacos

nacos = FlaskNacos()
nacos.init_app(app)

nacos.register_instance(app)       # returns None immediately
removed = nacos.deregister_instance(app)
status = nacos.get_status(app)
client = nacos.get_client(app)
```

The lifecycle signatures are:

```text
register_instance(app=None) -> None
deregister_instance(app=None) -> bool
get_status(app=None) -> Dict[str, Any]
get_client(app=None) -> Any
```

## `FlaskNacos(app=None)` and `init_app(app)`

`FlaskNacos(app)` initializes one application immediately. `FlaskNacos()` plus
`init_app(app)` supports application factories. Initialization validates its
enabled responsibilities and installs local hooks, but never constructs a
Nacos Client. Registration-only validation runs at initialization only when
automatic registration is enabled; otherwise it is deferred to the first
explicit registration command.

When automatic registration is enabled, `init_app()` calls the same public
`register_instance(app)` command used by application code. The network request
runs in one daemon convergence Worker, which exits after convergence and never
becomes a second heartbeat monitor.

## Application selection

Lifecycle and state APIs accept an optional Flask application. Without it, use
an app/request context:

```python
with app.app_context():
    nacos.register_instance()
    status = nacos.get_status()
```

No context, an uninitialized app, or an app owned by a different `FlaskNacos`
object raises `FlaskNacosError`.

The `.app`, `.config`, and `.client` properties use the same current-context
rule. This keeps multiple Flask applications isolated.

## `register_instance(app=None)`

Sets the local target to registered, schedules at most one lifecycle Worker,
and returns `None` without waiting for Client creation or network I/O.

- Repeated calls are idempotent while registration is running or complete.
- A call after an unknown/deterministic failed idle attempt starts a new finite
  attempt. Verified transient failures retain the existing Worker for
  low-frequency lifecycle recovery.
- `NACOS_ENABLED=False` makes this command a side-effect-free no-op.
- With `NACOS_FAIL_FAST=True`, a cached deterministic registration error may be
  raised synchronously without committing a new lifecycle target. Thread,
  Client, SDK, timeout, and connection failures
  are recorded safely in local status and are not raised by this command.

Registration success starts the SDK's heartbeat for ephemeral instances. The
Flask-Nacos Worker then exits; it is not a permanent heartbeat thread.

Failures are classified immediately. Deterministic failures stop, unknown
failures stop after the existing finite budget, and only verified transient
transport failures continue with interruptible bounded-backoff recovery.
`NACOS_RETRY_ENABLED=False` allows only the current attempt. Recovery does not
add remote polling and does not change the method's `None` return contract.

## `deregister_instance(app=None)`

Sets the target to unregistered. The return value is:

- `True` when already unregistered, when an active Worker accepted the new
  target, when the SDK deregistration succeeded, or when a newer register
  command made the pending deregistration unnecessary.
- `False` when deregistration is still required but cannot be completed.

An idle registered instance is deregistered synchronously. During an active
Register Worker, the target change is handled by that Worker.

All deregistration paths use the exact identity cached by the last successful
registration. They never guess a new IP or identity.

## `get_client(app=None)` and `.client`

`get_client()` explicitly requests a usable Client for the selected app and
current PID. It returns `None` only when Flask-Nacos is disabled. Creation
failure raises a safe `FlaskNacosError` and preserves the original exception as
its cause.

Reading `.client` never creates a Client. It returns the current-context app's
cached Client or `None` and raises `FlaskNacosError` without a context.

Client creation itself does not change the registration target, registration
fact, lifecycle generation, or lifecycle error.

## `get_status(app=None)`

Returns exactly these 12 local-only fields:

```python
{
    "enabled": True,
    "pid": 12345,
    "client_created": True,
    "service_name": "demo-service",
    "group_name": "DEFAULT_GROUP",
    "cluster_name": "DEFAULT",
    "service_ip": "203.0.113.20",
    "service_port": 3000,
    "target_registered": True,
    "registered": True,
    "operation_running": False,
    "last_error": None,
}
```

`registered` is the most recent local fact confirmed by a successful Naming
register/deregister call. It is not a live server query. `operation_running` is
true for either a background registration lifecycle or a synchronous
deregistration lifecycle. `last_error` contains only a safe exception type or
internal error code.

Before registration, identity values come from the configuration snapshot and
no IP detection occurs. While registered, the actual cached registration
identity is returned.

This method never creates a Client, calls the SDK, probes Nacos, detects an IP,
starts a thread, or resumes pending post-fork registration.

## Discovery and configuration

- `list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)`
  returns normalized instances.
- `get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)`
  selects one normalized healthy instance.
- `get_config(data_id=None, group=None)` returns raw text and uses
  `NACOS_CONFIG_DATA_ID` when `data_id` is omitted.
- `normalize_instance(instance)` returns a normalized dict or `None`.

These operations use the current Flask context and lazily create the app/PID
Client when needed. Flask-Nacos does not parse YAML or JSON configuration text.

## Exceptions

- `FlaskNacosError`: invalid application selection, initialization ownership,
  or explicit Client creation failure.
- `NacosConfigError`: deterministic extension configuration is invalid.
- `NacosValidationError`: registration or discovery input is invalid.
- `NacosRegistrationError` / `NacosDeregistrationError`: Naming SDK operation
  did not explicitly succeed.
- `NacosDiscoveryError`: discovery SDK operation failed.
- `NacosLoggingError`: logging configuration is invalid.

Runtime lifecycle errors are exposed through safe status and logs rather than
through `register_instance()`.
