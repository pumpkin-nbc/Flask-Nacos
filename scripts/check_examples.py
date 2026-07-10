#!/usr/bin/env python
"""Check the quality of the example applications under ``examples/``.

Static checks only (no network, no execution of the example modules -- some
examples call ``FlaskNacos(app)`` at import time and would attempt
registration). Verifies that:

- every ``examples/*.py`` file has valid Python syntax;
- ``import flask_nacos`` works in the current environment;
- examples do not reference unsupported identifiers (``get_config_as_dict`` /
  ``load_config_to_flask``) or implement YAML parsing;
- examples contain no private IPs, internal domains, or real secrets.

A Nacos ``data_id`` such as ``"application.yaml"`` is NOT flagged: only concrete
parsing markers (``import yaml`` / ``yaml.load`` / ``yaml.safe_load``) are.

Standard library only. Exits non-zero when any problem is found.
"""

import importlib
import py_compile
import sys
from pathlib import Path
from typing import List, NamedTuple

# Reuse the value-based secret/IP/domain detection from the sensitive scanner.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sensitive_info  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples"

FORBIDDEN_IDENTIFIERS = ("get_config_as_dict", "load_config_to_flask")
YAML_MARKERS = ("import yaml", "from yaml", "yaml.load", "yaml.safe_load")


class Problem(NamedTuple):
    path: str
    lineno: int
    message: str


def _example_files() -> List[Path]:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(EXAMPLES_DIR.glob("*.py"))


def scan() -> List[Problem]:
    """Run all example checks and return the combined problems."""
    problems: List[Problem] = []

    try:
        importlib.import_module("flask_nacos")
    except Exception as exc:  # pragma: no cover - import failure is fatal
        problems.append(Problem("flask_nacos", 0, f"cannot import flask_nacos: {exc}"))

    for path in _example_files():
        rel = path.relative_to(ROOT).as_posix()

        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            problems.append(Problem(rel, 0, f"syntax error: {exc.msg}"))
            continue

        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for identifier in FORBIDDEN_IDENTIFIERS:
                if identifier in line:
                    problems.append(
                        Problem(rel, lineno, f"unsupported identifier {identifier!r}")
                    )
            for marker in YAML_MARKERS:
                if marker in line:
                    problems.append(
                        Problem(rel, lineno, f"YAML parsing is not supported ({marker!r})")
                    )
            for reason in check_sensitive_info._scan_line(line):
                problems.append(Problem(rel, lineno, reason))

    return problems


def main() -> int:
    problems = scan()
    if not problems:
        print("[check_examples] OK - examples are valid and clean")
        return 0

    print("[check_examples] FAILED - example problems:", file=sys.stderr)
    for problem in problems:
        location = f"{problem.path}:{problem.lineno}" if problem.lineno else problem.path
        print(f"  - {location}: {problem.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
