# Compatibility

English | [简体中文](compatibility.zh-CN.md)

This page documents the supported runtime versions and the compatibility
guarantees of flask-nacos.

`0.9.0` is the Release Candidate preparation version before `1.0.0`: the public
API is frozen as the `1.0.0` candidate (see [1.0.0 Checklist](1.0-checklist.md)).

See also: [Quickstart](quickstart.md) - [Configuration](configuration.md) -
[Production](production.md).

## Supported Python versions

flask-nacos supports **Python 3.8 - 3.12**. The library keeps its type hints
Python 3.8 compatible: it uses `typing.Optional` / `typing.List` / `typing.Dict`
rather than PEP 604 unions (`str | None`) or PEP 585 builtin generics
(`list[str]`), and does not use `match`/`case`. A `scripts/check_compatibility.py`
static check enforces this and runs in CI.

## Supported Flask versions

flask-nacos supports **Flask `>=1.0, <4.0`** (Flask 1.x, 2.x, and 3.x).

- Flask 1.x / 2.x / 3.x: extension initialization works in both the standard
  `FlaskNacos(app)` mode and the application-factory `init_app(app)` mode.
- The extension only uses Flask APIs that are stable across 1.x-3.x
  (`app.extensions`, `app.add_url_rule`, `app.url_map.iter_rules`,
  `app.view_functions`, `flask.jsonify`), and avoids APIs removed in Flask 3.x.
- The optional health-check route registers idempotently, so a repeated
  `init_app(app)` call or a pre-existing route will not raise.
- Flask 1.x pins an older Werkzeug that is incompatible with newer Python
  releases, so CI exercises Flask 1.x on Python 3.8 only.

## Recommended Nacos versions

- Nacos server: **2.x**.
- Nacos SDK: `nacos-sdk-python>=2.0.0,<3.0.0` (synchronous client).

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

Each worker is an independent process and registers its own instance;
registration state is tracked per process. See [Production](production.md) for
full deployment guidance.

## Unsupported capabilities

This version intentionally does not include the following:

- `get_config()` returns the raw Nacos configuration content only; it does not
  perform YAML, JSON, or dict parsing, and does not write into Flask
  `app.config`.
- There is no `get_config_as_dict()` helper in this version.
- There is no `load_config_to_flask()` helper in this version.
- No dynamic configuration watching, hot-reload, or background config threads.
- No PyYAML dependency.
