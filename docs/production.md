# Production Deployment

English | [简体中文](production.zh-CN.md)

## Normal WSGI startup

With the default `NACOS_AUTO_REGISTER=True`, a normal non-preloaded application
factory schedules registration when `init_app(app)` runs. Client creation and
Naming I/O happen in one daemon convergence Worker.

If startup meets a verified transient network failure, the Worker first uses
the configured finite retry budget and then remains as a low-frequency,
interruptible lifecycle recovery owner. It stops when registration converges,
the target changes, shutdown starts, or a later failure is no longer classified
as transient. This includes verified failures while an authenticated SDK
`2.0.11` Client is being constructed; no request or readiness probe is required
to trigger recovery. Structured authentication rejection such as HTTP 401/403
stops instead of entering long-lived Recovery.

Configure the externally reachable `NACOS_SERVICE_IP` and
`NACOS_SERVICE_PORT`; binding Flask to localhost does not make that advertised
address reachable from another machine.

## Gunicorn `--preload`

Preload imports and initializes the Flask application in the master before
workers fork. Starting SDK runtime or registration there is unsafe and may also
register the master. Recommended configuration:

```python
# application configuration
NACOS_AUTO_REGISTER = False
```

Then call the existing lifecycle command from Gunicorn's worker hook after the
fork:

```python
def post_fork(server, worker):
    from myservice import app, nacos

    nacos.register_instance(app)
```

Do not rely on the first business request to recover registration. Ordinary
requests, health/status reads, and the cache-only `.client` property do not
consume post-fork pending intent. An explicit `register_instance()` or a real
Client, Discovery, or Config SDK operation may consume it non-blockingly; the
triggering synchronous SDK operation then continues under its own contract
without waiting for registration convergence.

Flask-Nacos does not guess the server type or worker count and provides no
Gunicorn-specific public API. PID Runtime rebuilding prevents workers from
using a parent Client, lock, Event, or registration fact; it cannot undo work
that the preload master already started.

## Multiple workers and shared endpoints

Workers advertising the same service/group/cluster/IP/port represent the same
Nacos instance, even though every process owns a separate local Runtime and
Client. One worker must not delete that shared instance while others still
serve traffic:

```python
NACOS_DEREGISTER_ON_EXIT = False
```

Alternatively, let one external coordinator own registration and
deregistration. When each worker advertises a distinct IP or port, the default
`NACOS_DEREGISTER_ON_EXIT=True` can be appropriate.

## Shutdown behavior

With `NACOS_DEREGISTER_ON_EXIT=True`, the installed exit callback marks the
current PID Runtime as shutting down and wakes any retry wait. Normal lifecycle
paths cannot begin another Naming RPC afterward.

- With `NACOS_DEREGISTER_ON_EXIT=False`, no remote deregistration callback is
  installed, so process exit performs no Naming wait or cleanup.
- With `True`, exit may wait for only the already-active Naming RPC, using its
  remaining timeout plus a small scheduling allowance and a five-second wait
  cap. It then performs at most one exit deregistration with the cached exact
  identity.

This setting never disables an explicit `deregister_instance()`. Exit cleanup
is best-effort on normal interpreter shutdown; `SIGKILL`, forced container
termination, and host failure cannot guarantee callback execution.

The active RPC timeout snapshot comes from the actual SDK Client
`default_timeout`, not `NACOS_REQUEST_TIMEOUT` (which is configuration-center
only). A missing, raising, boolean, non-numeric, non-finite, or non-positive SDK
value uses the three-second fallback.

Exit deregistration never retries, schedules follow-up registration, or guesses
a missing identity.

## Container deployment

Use a graceful stop interval long enough for the SDK request timeout. Explicitly
set the advertised IP/port and prefer console logs:

```python
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = True
NACOS_LOG_FILE_ENABLED = False
```

## Logging and secrets

Native SDK logs are isolated and Flask-Nacos does not create
`~/logs/nacos`. Safe extension logging is disabled by default. When file output
is enabled, `NACOS_LOG_PATH` defaults to `./logs` and
`NACOS_LOG_FILENAME` defaults to `flask-nacos.log`.

Do not let multiple Gunicorn or Celery processes write to the same rotating log
file. Prefer console output collected by the process supervisor, or configure a
process-safe logging pipeline in the host application. Flask-Nacos does not
remove, close, or take ownership of handlers installed by the host application;
1.1.1 does not add a multi-process file-rotation mechanism.

Choose exactly one non-duplicating topology:

```python
# Host application owns console/file handlers.
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = False
NACOS_LOG_FILE_ENABLED = False
NACOS_LOG_PROPAGATE = True
```

```python
# Container stdout is the only output.
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = True
NACOS_LOG_FILE_ENABLED = False
NACOS_LOG_PROPAGATE = False
```

Keep Nacos username/password or AK/SK in environment variables or a secret
manager. Do not return complete application configuration or internal status
from an unauthenticated endpoint.

## HTTPS limitation

The supported synchronous Nacos SDK 2.x line has limitations around HTTPS
server certificate verification. Treat this as a deployment risk: use a trusted
private network, a terminating proxy with appropriate controls, or another
verified transport boundary until the upstream SDK behavior meets your policy.

## Health and observability

`/health/nacos` reports local lifecycle state only. `get_status()` additionally
reports the latest locally observed SDK heartbeat for the current ephemeral
registration cycle. Neither endpoint queries Nacos, and neither observation
proves that the remote instance still exists. Add a separate remote probe when
your readiness policy requires current Nacos reachability.

During transient startup recovery, `operation_running=True` can remain visible
while `registered=False`; this is local convergence activity, not a remote
health result. Status and health reads neither speed up nor trigger retries.
