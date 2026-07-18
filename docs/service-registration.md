# Service Registration

English | [简体中文](service-registration.zh-CN.md)

How flask-nacos registers and deregisters service instances.

See also: [Configuration](configuration.md) - [API Reference](api-reference.md) -
[Production](production.md).

## Automatic registration

When `NACOS_REGISTER_ENABLED`, `NACOS_AUTO_REGISTER`, and
`NACOS_AUTO_REGISTER_ON_INIT` are all `True`, the service is registered during
`init_app(app)`.

## Manual registration

```python
nacos.register_instance()
```

## Registration parameters

Validated before registration; invalid values follow `NACOS_FAIL_FAST`:

- `NACOS_SERVICE_NAME` - required, non-empty.
- `NACOS_SERVICE_PORT` - required, integer in `1-65535`.
- `NACOS_SERVICE_WEIGHT` - finite number greater than `0`.
- `NACOS_SERVICE_METADATA` - a `dict`.
- `NACOS_SERVICE_EPHEMERAL` - a `bool`.

## IP auto-detection

If `NACOS_SERVICE_IP` is unset, the extension attempts to detect the local
outbound IP. If detection fails, behavior follows `NACOS_FAIL_FAST`.

Production recommendation: configure `NACOS_SERVICE_IP` explicitly. In
containers, multi-NIC hosts, or behind NAT the auto-detected address may not be
reachable by other services. Also set `NACOS_SERVICE_NAME` and
`NACOS_SERVICE_PORT` explicitly.

## Idempotent registration

Registration is idempotent. With `NACOS_REGISTER_ONCE_PER_PROCESS=True`, once
`register_instance()` succeeds within a process, repeated calls are no-ops. When
a worker is forked (the process id changes), the new worker may register its own
instance.

## Multi-process registration (Gunicorn / uWSGI)

Under Gunicorn/uWSGI the master forks multiple workers; each worker runs
`init_app` and registers its own instance. flask-nacos tracks the registering
process id so a worker only deregisters the instance it registered. See
[Production](production.md) for deployment guidance.

If you prefer explicit control, set `NACOS_AUTO_REGISTER_ON_INIT=False` and call
`nacos.register_instance()` from a post-fork hook.

## Deregistration

```python
nacos.deregister_instance()
```

Deregistration is idempotent and never raises once already deregistered.

## Automatic deregistration

When `NACOS_AUTO_DEREGISTER` and `NACOS_DEREGISTER_ON_EXIT` are both `True`, an
`atexit` handler deregisters an instance successfully registered by this
extension on process exit. It does nothing if registration never occurred or
failed. The handler is registered at most once per extension instance.
