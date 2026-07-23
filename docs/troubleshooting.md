# Troubleshooting

English | [简体中文](troubleshooting.zh-CN.md)

Common issues and how to resolve them. Each entry lists the symptom, likely
cause, how to investigate, and the fix.

See also: [Configuration](configuration.md) - [API Reference](api-reference.md) -
[Production](production.md).

## 1. App starts but nothing registers in Nacos

- Symptom: the Flask app runs, but the instance does not appear in Nacos.
- Cause: registration disabled, or auto-registration turned off.
- Investigate: check `NACOS_ENABLED`, `NACOS_REGISTER_ENABLED`,
  `NACOS_AUTO_REGISTER`, `NACOS_AUTO_REGISTER_ON_INIT`; inspect logs and
  `get_status()`.
- Fix: enable the switches or call `nacos.register_instance()` explicitly.

## 2. Registration fails: `NACOS_SERVICE_NAME` empty

- Symptom: a validation error or a failed registration.
- Cause: `NACOS_SERVICE_NAME` is missing or empty.
- Investigate: print `app.config["NACOS_SERVICE_NAME"]`.
- Fix: set a non-empty `NACOS_SERVICE_NAME`.

## 3. Registration fails: `NACOS_SERVICE_PORT` missing

- Symptom: registration fails with a required-field error.
- Cause: `NACOS_SERVICE_PORT` is unset; it cannot be guessed.
- Investigate: confirm the value is set and is an integer in `1-65535`.
- Fix: set `NACOS_SERVICE_PORT` explicitly.

## 4. Auto-detected IP is wrong

- Symptom: the registered IP is not reachable by other services.
- Cause: auto-detection picked an unexpected NIC (containers, multi-NIC, NAT).
- Investigate: check the registered IP in Nacos / `get_status()`.
- Fix: set `NACOS_SERVICE_IP` explicitly.

## 5. Nacos client initialization fails

- Symptom: `client_initialized` is `False` in `get_status()`.
- Cause: bad `NACOS_SERVER_ADDR`, network issues, or auth failure.
- Investigate: verify the server address and connectivity; read logs.
- Fix: correct the address/credentials. Set `NACOS_FAIL_FAST=True` temporarily
  to surface the error during startup.

## 6. Wrong username / password

- Symptom: auth-related errors from the SDK.
- Cause: incorrect `NACOS_USERNAME` / `NACOS_PASSWORD`.
- Investigate: verify credentials against the Nacos console.
- Fix: correct the credentials (inject via environment variables).

## Authentication configuration is rejected before client initialization

- Cause: `NACOS_USERNAME`/`NACOS_PASSWORD` or
  `NACOS_ACCESS_KEY`/`NACOS_SECRET_KEY` is incomplete, both authentication
  methods are configured, or a credential is not a string.
- Fix: configure exactly one complete credential pair. Temporarily enable
  `NACOS_FAIL_FAST=True` to surface the safe configuration error.

## 7. Wrong namespace

- Symptom: instances/config not found even though they exist.
- Cause: `NACOS_NAMESPACE_ID` points to a different namespace.
- Investigate: confirm the namespace id in the Nacos console.
- Fix: set the correct `NACOS_NAMESPACE_ID`.

## 8. Discovery returns an empty list

- Symptom: `list_instances()` returns `[]`.
- Cause: no matching instances, wrong group/cluster/metadata filters, or
  `healthy_only=True` excluding all.
- Investigate: relax filters, try `healthy_only=False`, confirm the group.
- Fix: correct the `service_name`/`group`/`cluster`/`metadata`; an empty result
  is normal when nothing matches.
- A returned instance with an empty IP or an invalid port is logged and skipped;
  verify the provider's registered `NACOS_SERVICE_IP` and port in Nacos.

## Retry or request-timeout configuration fails immediately

- Cause: attempts are below `1` or not an integer, an interval is negative, or
  a numeric value is boolean, NaN, Infinity, or non-numeric.
- Fix: use `NACOS_RETRY_TIMES >= 1`, `NACOS_RETRY_INTERVAL >= 0`, and
  `NACOS_REQUEST_TIMEOUT > 0`. Deterministic validation failures are not retried.

## 9. `get_one_healthy_instance()` returns `None`

- Symptom: `None` is returned.
- Cause: no healthy instances match, or all weights are non-positive.
- Investigate: call `list_instances(healthy_only=True)` to inspect candidates.
- Fix: ensure healthy instances exist; check the `strategy` value.

## Ephemeral instance becomes unhealthy and disappears

- Symptom: the service appears in Nacos with zero healthy instances and is
  removed after a short delay.
- Cause: the ephemeral instance is not renewing its heartbeat, the Flask
  process stopped, or the query uses a different namespace/group.
- Investigate: keep the Flask process alive; inspect SDK heartbeat logs; confirm
  `NACOS_SERVICE_EPHEMERAL=True`, the namespace, and the group. `/health/nacos`
  only reports local client initialization and is not a remote heartbeat probe.
- Fix: use flask-nacos with the default
  `NACOS_SERVICE_HEARTBEAT_INTERVAL=5.0`, or set another finite positive interval.
  Do not use the initial `healthy=True` flag as a substitute for heartbeats.

## 10. Health check route is not registered

- Symptom: the health path returns 404.
- Cause: `NACOS_HEALTH_CHECK_ENABLED` is `False`, or the path is already used.
- Investigate: check the config and existing routes/logs.
- Fix: enable the route and/or choose a free `NACOS_HEALTH_CHECK_PATH`.

## 11. Multi-worker registration does not mean one Nacos instance per worker

- Symptom: several workers run registration, but Nacos shows one instance; or an
  exiting worker removes the endpoint while other workers still run.
- Cause: Nacos identifies an instance by service/group/cluster/IP/port. Workers
  advertising the same IP and port share one instance even though Flask-Nacos
  tracks their local state separately.
- Investigate: compare the complete advertised identities, not the worker count.
- Fix: for a shared endpoint set `NACOS_DEREGISTER_ON_EXIT=False`, or let one
  external coordinator own registration and deregistration. See
  [Production](production.md).

## 12. `NACOS_FAIL_FAST=True` prevents startup

- Symptom: the app crashes during `FlaskNacos(app)` / `init_app(app)`, or a
  lazy-loading WSGI server shows the error on the first request.
- Cause: `NACOS_FAIL_FAST=True` turns Nacos errors into exceptions. When
  automatic registration is active, missing or invalid registration settings
  are checked before client creation.
- Investigate: read the exception and confirm when the application factory is
  executed. `NACOS_SERVICE_NAME` must be a non-empty, non-whitespace string when
  automatic registration is active.
- Fix: fix the underlying Nacos issue, or use `NACOS_FAIL_FAST=False` (default)
  so failures are logged and startup continues. Configure the WSGI server for
  eager loading/preloading if validation must finish before traffic is accepted.

## 13. `get_config()` returns a string, not a dict

- Symptom: you expected a parsed object but got a string.
- Cause: `get_config()` intentionally returns the raw configuration content.
- Investigate: inspect the returned value type.
- Fix: parse the content in your application code as needed. flask-nacos does
  not perform YAML, JSON, or dict parsing and does not write into `app.config`.

## 14. Reading the failure reason from error messages

- Symptom: a Nacos operation raised an exception and you need the exact cause.
- Cause: registration, discovery, and config errors wrap the underlying SDK
  failure with a specific message.
- Investigate: read the exception message. Registration/deregistration errors
  name the service, ip, port, and group; discovery errors state whether the
  service name was empty, the SDK query failed, or the instance shape was
  unrecognized; config errors state whether the client was unavailable or the
  SDK call failed.
- Fix: address the specific cause reported. Error messages never contain
  passwords, access keys, or secret keys.

## 15. Why does `~/logs/nacos/nacos-client-python.log` appear?

- Symptom: a log file shows up at `~/logs/nacos/nacos-client-python.log` even
  though your app never configured it.
- Cause: the underlying `nacos-sdk-python` installs its own file handler when
  its logger has no handlers at client construction time.
- Investigate: confirm the file is created only after the Nacos client is built.
- Fix: upgrade to flask-nacos 1.0.2+. It silences native SDK loggers and sends
  the SDK an existing alternate directory, so neither the default file nor the
  `~/logs/nacos` directory is created. Do not enable raw SDK logging because it
  may contain sensitive request or configuration data.

## 16. How to turn off Flask-Nacos logging

- Symptom: you want no logging from the extension.
- Cause: Flask-Nacos safety logging is enabled by default (`INFO`, propagating
  to your handlers); SDK-native logging is already always silent.
- Investigate: check `NACOS_LOG_ENABLED`.
- Fix: set `NACOS_LOG_ENABLED=False`. No Flask-Nacos console/file handler is
  added or propagated. SDK-native logging remains silent.

## 17. How to send logs to a specific directory

- Symptom: you want Flask-Nacos safety logs in a specific directory.
- Cause: no file is created unless you ask for one.
- Investigate: confirm the target directory is writable.
- Fix: set `NACOS_LOG_ENABLED=True`, `NACOS_LOG_PATH="/var/log/flask-nacos"`,
  and optionally `NACOS_LOG_FILENAME="service.log"`. For rotation, also set
  `NACOS_LOG_MAX_BYTES` and `NACOS_LOG_BACKUP_COUNT`. Native SDK records are
  never written there.
- If an older configuration already created a regular file at that directory
  path (for example a file named `logs`), rename or remove that file first.

## 18. `nacos-client-python.log` still appears with Flask-Nacos logging disabled

- Symptom: the default SDK file appears even though you did not set
  Flask-Nacos logging or its directory settings.
- Cause: an older flask-nacos version, or another component created the SDK
  client before flask-nacos configured logging.
- Investigate: ensure `FlaskNacos(app)` / `init_app(app)` runs before any code
  that constructs a `nacos.NacosClient` directly.
- Fix: upgrade to 1.0.2+. Flask-Nacos silences SDK loggers before creating the
  client and directs SDK setup away from the home directory. A directly created
  SDK client is outside Flask-Nacos control.

## 19. Duplicate flask-nacos log lines

- Symptom: each log line appears twice (or more).
- Cause: both a flask-nacos handler and a propagated parent handler emit the
  record, or multiple logging setups added handlers.
- Investigate: check whether your app configured the root logger and whether
  `NACOS_LOG_CONSOLE_ENABLED`/`NACOS_LOG_FILE_ENABLED` overlap with your own handlers.
- Fix: either use flask-nacos handlers (set `NACOS_LOG_CONSOLE_ENABLED`/
  `NACOS_LOG_FILE_ENABLED`) and set `NACOS_LOG_PROPAGATE=False`, or rely on your own
  logging with `NACOS_LOG_PROPAGATE=True` and no flask-nacos handlers.

## 20. Integrating with application logging

- Symptom: you want flask-nacos logs to follow the application's logging topology.
- Cause: by default flask-nacos uses its own named logger.
- Investigate: check the console/file switches and parent logger propagation.
- Fix: configure `NACOS_LOG_CONSOLE_ENABLED`, `NACOS_LOG_FILE_ENABLED`, and
  `NACOS_LOG_PROPAGATE` for the desired topology. Flask-Nacos does not reuse or
  modify `app.logger` handlers. SDK-native records remain silent.

## 21. Can HTTPS verify the Nacos server certificate?

- Symptom: you need verified TLS between the Flask process and Nacos.
- Cause: synchronous `nacos-sdk-python` 2.x does not expose reliable HTTPS
  certificate-verification controls.
- Fix: use a trusted network or a TLS proxy/sidecar that validates the Nacos
  server certificate; do not rely on an `https://` address alone.

## 22. Logs duplicated after repeated `init_app`

- Symptom: calling `init_app(app)` more than once multiplies handlers/log lines.
- Cause: naive handler setup re-adds handlers on every call.
- Investigate: count handlers on `logging.getLogger("flask_nacos")`.
- Fix: none needed on 1.0.2+. flask-nacos de-duplicates handlers, so repeated
  `init_app(app)` never adds a second console or file handler.
