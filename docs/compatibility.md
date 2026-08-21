# Compatibility

English | [简体中文](compatibility.zh-CN.md)

This page documents the supported runtime versions and the compatibility
guarantees of flask-nacos.

`1.1.1` is the current supported release surface. Its API snapshot is enforced
by the release checks.

See also: [Quickstart](quickstart.md) - [Configuration](configuration.md) -
[Production](production.md).

## Supported Python versions

flask-nacos requires **Python `>=3.8`**. CI currently tests every stable Python
release from 3.8 through 3.14. Future Python releases are not artificially
blocked by package metadata, but enter the formally tested range after they are
added to CI.

The library keeps its type hints Python 3.8 compatible: it uses
`typing.Optional` / `typing.List` / `typing.Dict` rather than PEP 604 unions
(`str | None`) or PEP 585 builtin generics (`list[str]`), and does not use
`match`/`case`. A `scripts/check_compatibility.py` static check enforces this and
runs in CI.

## Supported Flask versions

flask-nacos requires **Flask `>=1.0`** without an artificial upper bound. CI
currently validates Flask 1.0.x, 1.1.x, 2.x, 3.0.x, and 3.1.x using combinations
supported by Flask and its dependencies.

- Flask 1.0.x through 3.1.x: extension initialization works in both the standard
  `FlaskNacos(app)` mode and the application-factory `init_app(app)` mode.
- The extension only uses long-standing Flask APIs
  (`app.extensions`, `app.add_url_rule`, `app.url_map.iter_rules`,
  `app.view_functions`, `flask.jsonify`) and examples use `app.route()` rather
  than newer route shortcuts.
- The optional health-check route registers idempotently, so a repeated
  `init_app(app)` call or a pre-existing route will not raise.
- CI tests Flask 1.0.4 and 1.1.4 with their compatible Pallets dependency stack
  on Python 3.8. Flask 3.1 dropped Python 3.8, so Python 3.8 uses Flask 3.0.x;
  Python 3.9-3.14 test the latest installable Flask release.
- Compatibility means upstream-supported runtime combinations, not every Flask
  release combined with every newer Python release.

## Recommended Nacos versions

- Nacos server: **2.x**.
- Nacos SDK: `nacos-sdk-python>=2.0.0,<3.0.0` (synchronous client).

## Naming failure compatibility

Transient lifecycle recovery primarily uses stable structured evidence: standard timeout
and connection exceptions, selected network/DNS errno values, structured HTTP
statuses, and SDK error codes. Generic SDK exceptions remain unknown and stop
after the existing finite retry budget.

The classic SDK's bare `nacos.exception.NacosRequestException` contains no
structured cause in a verified node-unavailable path. Flask-Nacos therefore has
a narrow private compatibility rule for Naming register and compensating
deregister in SDK `2.0.0` and `2.0.11`. The rule requires the installed exact
type and exact failure stage. SDK `2.0.11` additionally has one verified rule
for the same exact exception during authenticated Client construction in the
register direction. SDK `2.0.0` Client construction, synchronous/exit
deregistration, same-named replacement types, other directions, and unverified
SDK releases do not match that rule. Other 2.x exception systems remain
supported through their own structured evidence; no common exception hierarchy
is assumed. Structured 401/403 evidence always remains deterministic.

## Heartbeat observability compatibility

The synchronous SDK 2.x `send_heartbeat` layout is used only by one private,
best-effort identity extractor. Keyword arguments take precedence over the
verified positional fallback. A complete safe service/group/cluster/IP/port
identity gets independent warning throttling and one recovery record. Missing,
duplicated, unknown, or complex fields produce stateless `<unknown>` logging;
Flask-Nacos does not stringify/hash user objects or invent a collision-prone
key. The wrapper always preserves the SDK return value or original exception.

This remains an instrumentation compatibility layer, not remote monitoring.
Each Client has exactly one Flask-Nacos heartbeat wrapper shared by logging and
the optional Runtime observer. Per-identity log throttling belongs to that
Client and is discarded with it. `get_status()` exposes only the latest
sanitized observation for the current app/PID ephemeral-registration cycle;
health omits it. Neither path can trigger Lifecycle Recovery, and the SDK
remains the only post-registration heartbeat owner.

## Timeout compatibility

`NACOS_REQUEST_TIMEOUT` remains the configuration-center read timeout. Naming
uses the actual SDK Client `default_timeout`, and shutdown snapshots that value
for its bounded active-RPC wait. This separation avoids silently rewriting
shared SDK Client behavior.

## Nacos SDK response-shape compatibility

Different SDK versions return service-discovery results in slightly different
shapes. `list_instances()` uses an internal `extract_instances()` helper that
tolerates all of the following:

- a plain `list` of instances
- `{"hosts": [...]}`
- `{"instances": [...]}`
- `{"data": {"hosts": [...]}}`
- `{"data": {"instances": [...]}}`
- `None` or an empty list (treated as "no instances")

Each extracted instance is then passed through `normalize_instance()`, which
accepts both `dict` and attribute-style objects and both camelCase
(`serviceName`, `clusterName`) and snake_case (`service_name`, `cluster_name`)
field names, filling missing fields with sensible defaults.

A minor difference in the SDK response does not fail discovery as a whole. When
the response shape is fundamentally unrecognized, behavior follows
`NACOS_FAIL_FAST`: with `NACOS_FAIL_FAST=False` (default) an empty list is
returned and the issue is logged; with `NACOS_FAIL_FAST=True` an exception is
raised.

## Gunicorn / uWSGI multi-worker notes

Each worker is an independent process and registration state is tracked per
process. Workers advertising the same service/group/cluster/IP/port still map
to one Nacos instance. Disable per-worker exit deregistration for a shared
endpoint, or use one external lifecycle coordinator. See
[Production](production.md) for full deployment guidance.

## HTTPS limitation in SDK 2.x

The synchronous SDK 2.x line does not expose reliable server-certificate
verification controls. Use a trusted network or a certificate-validating TLS
proxy/sidecar for HTTPS deployments.

## Unsupported capabilities

This version intentionally does not include the following:

- `get_config()` returns the raw Nacos configuration content only; it does not
  perform YAML, JSON, or dict parsing, and does not write into Flask
  `app.config`.
- There is no `get_config_as_dict()` helper in this version.
- There is no `load_config_to_flask()` helper in this version.
- No dynamic configuration watching, hot-reload, or background config threads.
- No PyYAML dependency.
