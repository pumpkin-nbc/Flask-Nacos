# Service Registration

English | [简体中文](service-registration.zh-CN.md)

Flask-Nacos 1.1.0 uses a target-state lifecycle. `target_registered` is the
latest requested state; `registered` is the last locally confirmed Naming
fact. A short-lived daemon Worker moves the fact toward the latest target.

## Automatic registration

Both registration switches default to `True`:

```python
app.config.update(
    NACOS_AUTO_REGISTER=True,
    NACOS_REGISTER_ENABLED=True,
    NACOS_SERVICE_NAME="orders-api",
    NACOS_SERVICE_PORT=5000,
)
```

When both switches and `NACOS_ENABLED` are true, `init_app(app)` validates the
registration snapshot and calls public `register_instance(app)`. That command
returns immediately; the Worker creates the Client and performs the Naming RPC.

With `NACOS_FAIL_FAST=True`, invalid deterministic registration configuration
raises during `init_app(app)` before extension state is committed. With false,
initialization completes with `target_registered=True`, `registered=False`, and
a safe `last_error`, without starting an invalid Worker.

## Explicit registration

Disable initialization registration when a process should choose the lifecycle
boundary itself:

```python
app.config["NACOS_AUTO_REGISTER"] = False
nacos.init_app(app)

# Explicit app is useful outside a Flask context.
nacos.register_instance(app)

with app.app_context():
    status = nacos.get_status()
```

Repeated calls while a Worker runs do not increment the lifecycle generation or
start another Worker. After an idle failed attempt, a new explicit call starts a
new finite attempt.

## Lifecycle flow

### Initialization

```mermaid
flowchart TD
    A["init_app(app)"] --> B["Load and validate configuration"]
    B --> C{"Deterministic auto-registration error?"}
    C -- "yes, fail-fast" --> D["Raise before committing app state"]
    C -- "yes, safe mode" --> E["Commit target=True and safe last_error"]
    C -- "no" --> F["Commit PID Runtime with client=None"]
    F --> G{"Automatic registration enabled?"}
    G -- "no" --> H["Initialization complete"]
    G -- "yes" --> I["Call register_instance(app)"]
    I --> J["Publish one daemon Worker"]
    J --> H
```

Initialization, status, health, and `.client` cache reads do not create a Nacos
Client.

### Runtime convergence

```mermaid
flowchart TD
    A["register or deregister command"] --> B["Update target_registered"]
    B --> C{"Lifecycle operation already owns convergence?"}
    C -- "yes" --> D["Wake it and return"]
    C -- "no, registration needed" --> E["Start one Register Worker"]
    C -- "no, idle registered cleanup" --> F["Run synchronous deregistration"]
    E --> G["Check latest target before Client creation"]
    G --> H["Create or reuse app/PID Client"]
    H --> I["Acquire Naming single-flight lock"]
    F --> I
    I --> J{"RPC still required by latest target?"}
    J -- "no" --> K["SKIPPED: do not call SDK"]
    J -- "yes" --> L["Execute one Naming RPC"]
    K --> M["Re-read latest target and fact"]
    L --> M
    M --> N{"registered equals target?"}
    N -- "yes" --> O["Clear recovered error and finish"]
    N -- "no" --> P["Worker retries or performs compensation"]
    P --> G
```

The Worker can register, retry, compensate with deregistration, and register
again inside one lifecycle operation. It exits as soon as state converges or an
unrecoverable finite attempt ends. The Nacos SDK—not this Worker—maintains the
heartbeat after successful ephemeral registration.

## Naming single-flight and three results

One app/PID Runtime executes at most one Naming register/deregister RPC at a
time. Each logical call has one of three private outcomes:

- `SUCCEEDED`: the SDK call was needed, executed, and explicitly succeeded.
- `FAILED`: the action is still needed but cannot be completed.
- `SKIPPED`: a newer target makes the call unnecessary, so the SDK is not
  called.

Retry belongs only to the Register Worker. The RPC infrastructure performs one
logical SDK call and never schedules follow-up work.

## Identity and deregistration

Successful registration atomically caches the actual service, group, cluster,
IP, and port. Every normal, compensating, or exit deregistration uses that exact
identity. If local state says registered but the cached identity is absent,
normal deregistration safely returns `False` with
`last_error="MissingRegisteredIdentity"`; it never guesses an address.

`deregister_instance(app)` returns:

- `True` for an idempotent cleanup, an accepted target change, a successful SDK
  call, or an obsolete call skipped after a newer register command.
- `False` when deregistration is still needed but fails.

`NACOS_REGISTER_ENABLED=False` prevents new registration but does not block
cleanup of an existing registered instance.

## Retry and target changes

Retry is finite and uses `NACOS_RETRY_TIMES` and `NACOS_RETRY_INTERVAL`. The
Worker waits on an Event. Register, deregister, or shutdown wakes it immediately;
the Event is cleared before waiting and state is rechecked to prevent a lost
wakeup.

The last valid lifecycle command wins. For example, register → deregister →
register ends registered when the final operation succeeds, even if an older
RPC completes after the intermediate target change.

## Ephemeral heartbeat

`NACOS_SERVICE_EPHEMERAL=True` passes
`NACOS_SERVICE_HEARTBEAT_INTERVAL` (default `5.0` seconds) to the synchronous
Nacos SDK. `healthy=True` is only initial registration input; it does not replace
heartbeat renewal. Persistent instances do not receive this heartbeat option.

## Fork and process servers

Client, Worker, locks, events, and registration facts are PID-bound. After a
fork, the parent Runtime is discarded and exactly one current-PID Runtime is
published. Ordinary business requests and SDK operations may resume pending
automatic registration. `get_status()`, `/health/nacos`, and `.client` do not.

Gunicorn `--preload` initializes the app in the master before workers fork. The
recommended configuration is `NACOS_AUTO_REGISTER=False`, followed by
an explicit `nacos.register_instance(app)` in Gunicorn's post-fork/worker-init
hook. Runtime rebuilding cannot undo a registration that the master already
started before the fork.

When multiple workers share the same service/group/cluster/IP/port, Nacos sees
one remote instance. Set `NACOS_AUTO_DEREGISTER=False` so one exiting worker does
not remove the shared endpoint, or use a single external coordinator.

## Old and new scheduling

| Dimension | Earlier scheduling | 1.1.0 scheduling |
| --- | --- | --- |
| Decision input | Current command plus delayed flags | Final target state |
| Core state | Multiple request booleans | `target_registered` and `registered` |
| Worker | Executes one register command | Continues one convergence operation |
| RPC result | Success or failure | Success, failure, or skip |
| Retry | Could be spread across paths | Register Worker only |
| Single-flight | Prevent duplicate register threads | All Naming RPCs |
| Client | Created during initialization | Lazy per app/PID |
| Fork | Could inherit process resources | Entire Runtime rebuilt |
| Exit | Could reuse normal deregistration | Dedicated shutdown path |

The public status exposes only stable lifecycle meaning:
`target_registered`, `registered`, `operation_running`, and `last_error`.
Internal generation, Worker ownership, pending recovery, and RPC metadata remain
private.
