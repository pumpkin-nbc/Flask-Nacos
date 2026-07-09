#!/usr/bin/env python
"""Check that the built distributions look correct before publishing.

Verifies that ``dist/`` contains a wheel and an sdist, and that the wheel
includes the expected files (``py.typed`` and core modules) while excluding
things that must never be published (tests, caches, ``.env``, log files).

Uses only the standard library. Exits non-zero on any problem.
"""

import glob
import sys
import zipfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_MEMBERS = (
    "flask_nacos/py.typed",
    "flask_nacos/__init__.py",
    "flask_nacos/extension.py",
)


def validate_wheel_names(names: List[str]) -> List[str]:
    """Return a list of problems for the given wheel member names.

    Empty list means the wheel content is acceptable.
    """
    problems: List[str] = []

    for member in REQUIRED_MEMBERS:
        if member not in names:
            problems.append(f"missing required member: {member}")

    for name in names:
        normalized = name.replace("\\", "/")
        top = normalized.split("/", 1)[0]
        base = normalized.rsplit("/", 1)[-1]

        if top == "tests" or normalized.startswith("tests/"):
            problems.append(f"tests must not be packaged: {name}")
        if base == ".env":
            problems.append(f".env must not be packaged: {name}")
        if "__pycache__" in normalized.split("/"):
            problems.append(f"__pycache__ must not be packaged: {name}")
        if ".pytest_cache" in normalized.split("/"):
            problems.append(f".pytest_cache must not be packaged: {name}")
        if base.endswith(".log"):
            problems.append(f"log files must not be packaged: {name}")

    return problems


def _find_one(pattern: str) -> List[str]:
    return sorted(glob.glob(pattern))


def main() -> int:
    dist = ROOT / "dist"
    if not dist.is_dir():
        print("[check_package] FAILED - dist/ directory does not exist", file=sys.stderr)
        return 1

    wheels = _find_one(str(dist / "*.whl"))
    sdists = _find_one(str(dist / "*.tar.gz"))

    problems: List[str] = []
    if not wheels:
        problems.append("no wheel (*.whl) found in dist/")
    if not sdists:
        problems.append("no sdist (*.tar.gz) found in dist/")

    if wheels:
        wheel_path = wheels[-1]
        with zipfile.ZipFile(wheel_path) as zf:
            names = zf.namelist()
        problems.extend(validate_wheel_names(names))

    if problems:
        print("[check_package] FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"[check_package] OK - wheel: {Path(wheels[-1]).name}, sdist: {Path(sdists[-1]).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
