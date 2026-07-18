# Health Check

English | [简体中文](health-check.zh-CN.md)

An optional Flask route that reports the extension's internal state.

See also: [Configuration](configuration.md) - [Production](production.md).

## Enabling the route

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

The route is registered during `init_app(app)` when
`NACOS_HEALTH_CHECK_ENABLED=True`. Registration is idempotent: a pre-existing
route or path will not cause Flask to raise.

## Path configuration

`NACOS_HEALTH_CHECK_PATH` controls the route path (default `/health/nacos`).

## Response

```json
{
  "status": "ok",
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true
}
```

When Nacos is disabled the `status` is `"disabled"`; when client initialization
failed it is `"error"`. Service identity fields (`service_name`, `service_ip`,
`service_port`) are included when known.

## Scope

- The route reports only the extension's internal state.
- It never calls the Nacos server, so it stays fast and is unaffected by Nacos
  latency.
- It is suitable for observing local service state. It is not a full Nacos
  connectivity probe, so a healthy response does not by itself guarantee the
  Nacos server is reachable.
