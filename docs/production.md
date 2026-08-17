# Production Deployment

English | [简体中文](production.zh-CN.md)

## Normal WSGI startup

With the default `NACOS_AUTO_REGISTER=True`, a normal non-preloaded application
factory schedules registration when `init_app(app)` runs. Client creation and
Naming I/O happen in a short-lived daemon Worker.

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
NACOS_AUTO_DEREGISTER = False
```

Alternatively, let one external coordinator own registration and
deregistration. When each worker advertises a distinct IP or port, the default
`NACOS_AUTO_DEREGISTER=True` can be appropriate.

`NACOS_REGISTER_ENABLED=False` prevents new registration but intentionally
does not prevent cleanup of an instance already registered by the current
Runtime.

## Shutdown behavior

The exit callback marks the current PID Runtime as shutting down and wakes any
retry wait. Normal lifecycle paths cannot begin another Naming RPC afterward.

- With `NACOS_AUTO_DEREGISTER=False`, exit returns without waiting or changing
  the user's registration target.
- With `True`, exit may wait for only the already-active Naming RPC, using its
  remaining timeout plus a small scheduling allowance and a five-second wait
  cap. It then performs at most one exit deregistration with the cached exact
  identity.

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

Keep Nacos username/password or AK/SK in environment variables or a secret
manager. Do not return complete application configuration or internal status
from an unauthenticated endpoint.

## HTTPS limitation

The supported synchronous Nacos SDK 2.x line has limitations around HTTPS
server certificate verification. Treat this as a deployment risk: use a trusted
private network, a terminating proxy with appropriate controls, or another
verified transport boundary until the upstream SDK behavior meets your policy.

## Health and observability

`/health/nacos` and `get_status()` report local lifecycle state only. They do not
query Nacos or inspect SDK heartbeat success. Add a separate remote probe when
your readiness policy requires current Nacos reachability.
