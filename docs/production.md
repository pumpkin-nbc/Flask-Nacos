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

Each worker is an independent process and runs `init_app`, so local registration
state is tracked per process. Nacos still treats workers advertising the same
service/group/cluster/IP/port as one shared instance.

## uWSGI

uWSGI behaves like Gunicorn: each worker initializes the extension, but workers
advertising the same IP and port refer to one Nacos instance. For a shared
endpoint, disable worker exit deregistration or use one external lifecycle
coordinator.

## Multi-worker registration

Under multi-worker servers, the master forks workers and Flask-Nacos records
registration state per process:

- `NACOS_REGISTER_ONCE_PER_PROCESS=True`: within a process, repeated
  `register_instance()` calls after the first success are skipped; a forked
  worker with a new pid may register its own instance.
- On shutdown, a process only attempts to deregister the identity it registered.

Process-local state does not create distinct Nacos identities. If workers share
one advertised endpoint, an exiting worker can remove that shared instance while
other workers still serve traffic. Set `NACOS_DEREGISTER_ON_EXIT=False` for the
workers, or let one external coordinator own registration and deregistration.

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

`NACOS_LOG_*` controls sanitized Flask-Nacos records only. Native SDK logging
from `nacos-sdk-python` is always silenced because it may contain sensitive
request or response data. Recommendations:

1. If you need file logs, set `NACOS_LOG_ENABLED=True` and configure
   `NACOS_LOG_DIR`/`NACOS_LOG_FILENAME` (plus rotation settings when needed).
2. In containers, prefer stdout: set `NACOS_LOG_ENABLED=True`,
   `NACOS_LOG_TO_CONSOLE=True`, and `NACOS_LOG_DIR=None`.
3. If your project already has a unified logging system, set
   `NACOS_LOG_PROPAGATE=True` and `NACOS_LOG_DIR=None`; let your existing
   handlers format and route the records.
4. To silence Flask-Nacos safety logs as well, set `NACOS_LOG_ENABLED=False`.
5. Do not rely on the nacos-sdk-python default log path in production.
6. Logging defaults to disabled, so no configured directory or `~/logs/nacos`
   directory is created. When enabled, the defaults write
   `./logs/flask_nacos.log`.

## Logging safety

Secrets (`NACOS_PASSWORD`, `NACOS_ACCESS_KEY`, `NACOS_SECRET_KEY`) are never
written to logs. Keep your own application logs free of credentials too.

## HTTPS certificate verification

Synchronous `nacos-sdk-python` 2.x does not expose reliable HTTPS certificate-
verification controls. Use a trusted network or terminate TLS through a proxy or
sidecar that validates the Nacos server certificate. Do not assume that an
`https://` address alone provides server-identity verification.

## Keep secrets out of source control

Never commit real credentials, internal Nacos addresses, or internal IPs.
Prefer injecting configuration via environment variables or a secrets manager.
