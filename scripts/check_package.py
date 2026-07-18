#!/usr/bin/env python
"""Check that the built distributions look correct before publishing.

Verifies that ``dist/`` contains exactly one wheel and one sdist, that both
contain the required license files, and that the wheel exposes the expected
PEP 639 metadata and package files while excluding content that must never be
published (tests, caches, ``.env``, log files).

Uses only the standard library. Exits non-zero on any problem.
"""

import glob
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_MEMBERS = (
    "flask_nacos/py.typed",
    "flask_nacos/__init__.py",
    "flask_nacos/extension.py",
)

REQUIRED_LICENSE_FILES = ("LICENSE", "NOTICE")
EXPECTED_LICENSE_EXPRESSION = "Apache-2.0"


def validate_wheel_names(names: List[str]) -> List[str]:
    """Return a list of problems for the given wheel member names.

    Empty list means the wheel content is acceptable.
    """
    problems: List[str] = []

    for member in REQUIRED_MEMBERS:
        if member not in names:
            problems.append(f"missing required member: {member}")

    normalized_names = [name.replace("\\", "/") for name in names]
    for filename in REQUIRED_LICENSE_FILES:
        suffix = f".dist-info/licenses/{filename}"
        if not any(name.endswith(suffix) for name in normalized_names):
            problems.append(f"missing packaged license file: {filename}")

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


def validate_wheel_metadata(metadata_text: str) -> List[str]:
    """Validate PEP 639 license metadata from a wheel ``METADATA`` file."""
    metadata = Parser().parsestr(metadata_text)
    problems: List[str] = []

    expression = metadata.get("License-Expression")
    if expression != EXPECTED_LICENSE_EXPRESSION:
        problems.append(
            "wrong License-Expression: "
            f"expected {EXPECTED_LICENSE_EXPRESSION!r}, got {expression!r}"
        )

    declared_files = set(metadata.get_all("License-File", []))
    for filename in REQUIRED_LICENSE_FILES:
        if filename not in declared_files:
            problems.append(f"missing License-File metadata: {filename}")

    deprecated = [
        value
        for value in metadata.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if deprecated:
        problems.append(f"deprecated license classifier present: {deprecated[0]}")

    return problems


def validate_sdist_names(names: List[str]) -> List[str]:
    """Validate that the source distribution contains both license files."""
    normalized_names = [name.replace("\\", "/") for name in names]
    problems: List[str] = []
    for filename in REQUIRED_LICENSE_FILES:
        if not any(name.endswith(f"/{filename}") for name in normalized_names):
            problems.append(f"sdist missing license file: {filename}")
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
    elif len(wheels) > 1:
        problems.append(f"expected exactly one wheel, found {len(wheels)}")
    if not sdists:
        problems.append("no sdist (*.tar.gz) found in dist/")
    elif len(sdists) > 1:
        problems.append(f"expected exactly one sdist, found {len(sdists)}")

    if wheels:
        wheel_path = wheels[-1]
        with zipfile.ZipFile(wheel_path) as zf:
            names = zf.namelist()
            metadata_names = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                problems.append(
                    "wheel must contain exactly one .dist-info/METADATA file"
                )
            else:
                metadata_text = zf.read(metadata_names[0]).decode("utf-8")
                problems.extend(validate_wheel_metadata(metadata_text))
        problems.extend(validate_wheel_names(names))

    if sdists:
        with tarfile.open(sdists[-1], "r:gz") as archive:
            problems.extend(validate_sdist_names(archive.getnames()))

    if problems:
        print("[check_package] FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"[check_package] OK - wheel: {Path(wheels[-1]).name}, sdist: {Path(sdists[-1]).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
