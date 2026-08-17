#!/usr/bin/env python
"""Check that the public API matches the Flask-Nacos 1.1 snapshot.

Version 1.1 intentionally changes registration into a no-argument lifecycle
command. This guard enforces the supported public signature.

Uses only the standard library (``importlib`` / ``inspect``). It imports the
package but never creates a real Nacos connection. Exits non-zero on any
problem.
"""

import importlib
import inspect
import sys
from typing import List

# Methods that must exist on FlaskNacos (the supported public surface).
REQUIRED_METHODS = (
    "init_app",
    "get_client",
    "register_instance",
    "deregister_instance",
    "list_instances",
    "get_one_healthy_instance",
    "get_config",
    "get_status",
    "normalize_instance",
)

# Identifiers that must never appear on the public surface.
FORBIDDEN_METHODS = (
    "get_config_as_dict",
    "load_config_to_flask",
)


def scan() -> List[str]:
    """Return a list of API-snapshot problems (empty means the API is intact)."""
    problems: List[str] = []

    try:
        flask_nacos = importlib.import_module("flask_nacos")
    except Exception as exc:  # pragma: no cover - import failure is fatal
        return [f"cannot import flask_nacos: {exc}"]

    if not hasattr(flask_nacos, "FlaskNacos"):
        return ["flask_nacos.FlaskNacos is not importable"]

    extension = flask_nacos.FlaskNacos

    for name in REQUIRED_METHODS:
        if not callable(getattr(extension, name, None)):
            problems.append(f"missing frozen API method: FlaskNacos.{name}()")

    register = getattr(extension, "register_instance", None)
    if callable(register):
        signature = inspect.signature(register)
        if list(signature.parameters) != ["self"]:
            problems.append("register_instance() must accept only self")
        if signature.return_annotation is not None:
            problems.append("register_instance() must be annotated as returning None")

    all_names = getattr(flask_nacos, "__all__", [])
    for name in FORBIDDEN_METHODS:
        if hasattr(extension, name):
            problems.append(f"unsupported method present: FlaskNacos.{name}")
        if name in all_names:
            problems.append(f"unsupported identifier exported in __all__: {name}")

    return problems


def main() -> int:
    problems = scan()
    if not problems:
        print("[check_api_snapshot] OK - public API matches the 1.1 surface")
        return 0

    print("[check_api_snapshot] FAILED - public API problems:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
