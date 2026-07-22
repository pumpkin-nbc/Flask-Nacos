# Production Deployment

English | [简体中文](production.zh-CN.md)

Guidance for running flask-nacos in production.

See also: [Configuration](configuration.md) -
[Service Registration](service-registration.md) -
[Troubleshooting](troubleshooting.md).

## Gunicorn

```bash
gunicorn "app:create_app()" -w 4 -b 0.0.0.0:5000
```

Each worker is an independent process and runs `init_app`, so registration state
is tracked per process.

## uWSGI

uWSGI behaves like Gunicorn: each worker process registers and deregisters its
own instance. If you prefer explicit control, set
`NACOS_AUTO_REGISTER_ON_INIT=False` and register from a post-fork hook.

## Multi-worker registration

Under multi-worker servers, the master forks workers and each worker registers
its own instance. flask-nacos records the registering process id:

- `NACOS_REGISTER_ONCE_PER_PROCESS=True`: within a process, repeated
  `register_instance()` calls after the first success are skipped; a forked
  worker with a new pid may register its own instance.
- On shutdown, a process only deregisters the instance it registered.

## Docker

- Set `NACOS_SERVER_ADDR` to the reachable Nacos address for the container
  network.
- Set `NACOS_SERVICE_IP` and `NACOS_SERVICE_PORT` explicitly so other services
  can reach this instance; do not rely on auto-detection inside containers.
- Inject credentials via environment variables, not baked into the image.

A local Nacos for testing is available via
[`examples/docker-compose-nacos.yml`](../examples/docker-compose-nacos.yml)
(local use only).

## Explicit service IP and port

Always configure `NACOS_SERVICE_NAME`, `NACOS_SERVICE_IP`, and
`NACOS_SERVICE_PORT` explicitly in production.

## Auto-deregistration notes

`atexit`-based deregistration is best-effort: it may not run on hard kills
(`SIGKILL`) or crashes. Nacos will eventually drop unhealthy ephemeral instances,
but for graceful shutdowns ensure your process exits cleanly.

## `NACOS_AUTO_REGISTER_ON_INIT`

Set to `False` when you want to control exactly when registration happens (for
example, from a post-fork hook or a management command) instead of implicitly at
`init_app` time.

## `NACOS_DEREGISTER_ON_EXIT`

Controls whether the `atexit` deregistration handler is installed (only when
`NACOS_AUTO_DEREGISTER` is also `True`).

## Logging in production

flask-nacos uses unified `NACOS_LOG_*` settings to control both its own logging
and the underlying `nacos-sdk-python` logging. Recommendations:

1. If you need file logs, configure them explicitly with `NACOS_LOG_FILE`
   (optionally `NACOS_LOG_MAX_BYTES` + `NACOS_LOG_BACKUP_COUNT` for rotation).
2. In containers, prefer stdout: set `NACOS_LOG_TO_CONSOLE=True` and leave
   `NACOS_LOG_FILE` unset so the platform's log system collects the output.
3. If your project already has a unified logging system, set
   `NACOS_LOG_PROPAGATE=True` and do not set `NACOS_LOG_FILE`; let your existing
   handlers format and route the records.
4. To silence flask-nacos and nacos-sdk-python entirely, set
   `NACOS_LOG_ENABLED=False`.
5. Do not rely on the nacos-sdk-python default log path in production.
6. The nacos-sdk-python default log `~/logs/nacos/nacos-client-python.log` is
   prevented by flask-nacos by default.

## Logging safety

Secrets (`NACOS_PASSWORD`, `NACOS_ACCESS_KEY`, `NACOS_SECRET_KEY`) are never
written to logs. Keep your own application logs free of credentials too.

## Keep secrets out of source control

Never commit real credentials, internal Nacos addresses, or internal IPs.
Prefer injecting configuration via environment variables or a secrets manager.
