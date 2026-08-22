# Health Check

English | [简体中文](health-check.zh-CN.md)

## Enable the route

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

The route is installed during `init_app(app)` and returns exactly seven fields:

```json
{
  "status": "ok",
  "enabled": true,
  "client_created": true,
  "target_registered": true,
  "registered": true,
  "operation_running": false,
  "last_error": null
}
```

The status rule is:

```text
disabled extension                                      -> disabled
registered equals target_registered                     -> ok
operation is running and no lifecycle error is recorded -> ok
all other non-converged states                          -> error
```

`registered` is a locally confirmed fact from the latest successful Naming
register/deregister RPC. `status=ok` means the local lifecycle is converged or
converging without a recorded error. Neither field proves that Nacos is
currently reachable or that the remote instance still exists.

`get_status()` exposes four local heartbeat-observation fields for the current
ephemeral registration cycle. This health response deliberately omits them and
does not use heartbeat observations in its `status` rule. Heartbeat logging and
observation do not change `registered` and never wake or create a Lifecycle
Worker. A separate remote probe is required for real-time Nacos readiness.

The health route never creates a Client, performs SDK or Nacos I/O, detects an
IP, starts a thread, or resumes pending post-fork registration. A completely
lazy enabled state (`client_created=false`, target and fact both false) is
therefore healthy.

When `NACOS_ENABLED=False`, the fixed lifecycle portion is:

```json
{
  "status": "disabled",
  "enabled": false,
  "client_created": false,
  "target_registered": false,
  "registered": false,
  "operation_running": false,
  "last_error": null
}
```

Use external monitoring or a separate application probe when remote Nacos
reachability must be verified.
