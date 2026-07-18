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

## 11. Understanding duplicate registration under multiple workers

- Symptom: multiple instances appear for one service under Gunicorn/uWSGI.
- Cause: this is expected - each worker is a separate process and registers its
  own instance.
- Investigate: correlate instance count with worker count.
- Fix: nothing to fix; see [Production](production.md). Use explicit registration
  if you want a different topology.

## 12. `NACOS_FAIL_FAST=True` prevents startup

- Symptom: the app crashes on startup when Nacos is unreachable.
- Cause: `NACOS_FAIL_FAST=True` turns Nacos errors into exceptions.
- Investigate: read the raised exception.
- Fix: fix the underlying Nacos issue, or use `NACOS_FAIL_FAST=False` (default)
  so failures are logged and startup continues.

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
