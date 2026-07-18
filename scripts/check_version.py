#!/usr/bin/env python
"""Check that the project version is consistent across all definitions.

Compares the versions declared in:

- ``pyproject.toml`` (``[project].version``)
- ``flask_nacos/__init__.py`` (``__version__``)
- ``CHANGELOG.md`` (the most recent ``## X.Y.Z`` heading)

Exits with a non-zero status when they disagree. Uses only the standard
library so it can run anywhere without extra dependencies.
"""

import re
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent


def read_pyproject_version(root: Path) -> Optional[str]:
    """Return the ``version`` declared in ``[project]`` of pyproject.toml."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


def read_dunder_version(root: Path) -> Optional[str]:
    """Return ``__version__`` from flask_nacos/__init__.py, if present."""
    init_file = root / "flask_nacos" / "__init__.py"
    if not init_file.is_file():
        return None
    text = init_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def read_changelog_version(root: Path) -> Optional[str]:
    """Return the most recent ``## X.Y.Z`` version heading from CHANGELOG.md."""
    changelog = root / "CHANGELOG.md"
    if not changelog.is_file():
        return None
    text = changelog.read_text(encoding="utf-8")
    match = re.search(r"^##\s*v?([0-9]+\.[0-9]+\.[0-9]+)", text, re.MULTILINE)
    return match.group(1) if match else None


def check(root: Path = ROOT) -> Tuple[bool, dict, str]:
    """Return ``(ok, versions, message)`` for the version consistency check."""
    versions = {
        "pyproject.toml": read_pyproject_version(root),
        "flask_nacos/__init__.py": read_dunder_version(root),
        "CHANGELOG.md": read_changelog_version(root),
    }

    present = {source: ver for source, ver in versions.items() if ver is not None}
    if "pyproject.toml" not in present:
        return False, versions, "Could not read version from pyproject.toml"

    unique = set(present.values())
    if len(unique) == 1:
        version = next(iter(unique))
        return True, versions, f"All versions are consistent: {version}"

    details = ", ".join(f"{source}={ver!r}" for source, ver in versions.items())
    return False, versions, f"Version mismatch: {details}"


def main() -> int:
    ok, _versions, message = check()
    if ok:
        print(f"[check_version] OK - {message}")
        return 0
    print(f"[check_version] FAILED - {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
