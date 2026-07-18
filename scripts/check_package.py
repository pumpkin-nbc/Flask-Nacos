#!/usr/bin/env python
"""Validate release distributions before they are uploaded.

The check is intentionally standard-library only. In addition to package and
license metadata, it rejects stale distributions whose packaged source or
README no longer matches the current checkout.
"""

import glob
import re
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_MEMBERS = (
    "flask_nacos/py.typed",
    "flask_nacos/__init__.py",
    "flask_nacos/extension.py",
)
REQUIRED_LICENSE_FILES = ("LICENSE", "NOTICE")
REQUIRED_SDIST_FILES = (
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
)
REQUIRED_SDIST_DIRECTORIES = (
    "flask_nacos/",
    "tests/",
    "examples/",
    "scripts/",
    "docs/",
)
EXPECTED_LICENSE_EXPRESSION = "Apache-2.0"
EXPECTED_NAME = "flask-nacos"
EXPECTED_VERSION = "1.0.0"
EXPECTED_PROJECT_URLS = {
    "Changelog": (
        "https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/CHANGELOG.md"
    ),
    "Documentation": "https://github.com/pumpkin-nbc/Flask-Nacos/tree/master/docs",
    "Security": "https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/SECURITY.md",
}
REQUIRED_CLASSIFIERS = {
    "Operating System :: OS Independent",
    "Typing :: Typed",
}

_RELATIVE_MARKDOWN_LINK_RE = re.compile(
    r"\]\((?!https?://|mailto:|#)([^)]+)\)", re.IGNORECASE
)


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").rstrip()


def _project_urls(metadata) -> Dict[str, str]:
    urls: Dict[str, str] = {}
    for value in metadata.get_all("Project-URL", []):
        if "," not in value:
            continue
        label, url = value.split(",", 1)
        urls[label.strip()] = url.strip()
    return urls


def validate_wheel_names(names: List[str]) -> List[str]:
    """Return problems found in wheel member names."""
    problems: List[str] = []

    for member in REQUIRED_MEMBERS:
        if member not in names:
            problems.append(f"missing required member: {member}")

    normalized_names = [name.replace("\\", "/") for name in names]
    for filename in REQUIRED_LICENSE_FILES:
        suffix = f".dist-info/licenses/{filename}"
        if not any(name.endswith(suffix) for name in normalized_names):
            problems.append(f"missing packaged license file: {filename}")

    for name in normalized_names:
        top = name.split("/", 1)[0]
        base = name.rsplit("/", 1)[-1]
        parts = name.split("/")
        if top == "tests":
            problems.append(f"tests must not be packaged: {name}")
        if base == ".env":
            problems.append(f".env must not be packaged: {name}")
        if "__pycache__" in parts:
            problems.append(f"__pycache__ must not be packaged: {name}")
        if ".pytest_cache" in parts:
            problems.append(f".pytest_cache must not be packaged: {name}")
        if base.endswith(".log"):
            problems.append(f"log files must not be packaged: {name}")

    return problems


def validate_wheel_metadata(
    metadata_text: str, expected_readme: Optional[str] = None
) -> List[str]:
    """Validate identity, licensing, URLs, classifiers, and long description."""
    metadata = Parser().parsestr(metadata_text)
    problems: List[str] = []

    if metadata.get("Name") != EXPECTED_NAME:
        problems.append(
            f"wrong package name: expected {EXPECTED_NAME!r}, got {metadata.get('Name')!r}"
        )
    if metadata.get("Version") != EXPECTED_VERSION:
        problems.append(
            "wrong package version: "
            f"expected {EXPECTED_VERSION!r}, got {metadata.get('Version')!r}"
        )

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

    classifiers = set(metadata.get_all("Classifier", []))
    deprecated = [value for value in classifiers if value.startswith("License ::")]
    if deprecated:
        problems.append(f"deprecated license classifier present: {deprecated[0]}")
    for classifier in REQUIRED_CLASSIFIERS:
        if classifier not in classifiers:
            problems.append(f"missing classifier: {classifier}")

    urls = _project_urls(metadata)
    for label, expected in EXPECTED_PROJECT_URLS.items():
        if urls.get(label) != expected:
            problems.append(
                f"wrong {label} project URL: expected {expected!r}, got {urls.get(label)!r}"
            )
    for label, url in urls.items():
        if "/blob/main/" in url or "/tree/main/" in url:
            problems.append(f"project URL references unavailable main branch: {label}")

    payload = metadata.get_payload()
    if isinstance(payload, str):
        relative_link = _RELATIVE_MARKDOWN_LINK_RE.search(payload)
        if relative_link:
            problems.append(
                "long description contains relative Markdown link: "
                f"{relative_link.group(1)!r}"
            )
        if expected_readme is not None and _normalize_text(payload) != _normalize_text(
            expected_readme
        ):
            problems.append("wheel long description does not match current README.md")
    else:
        problems.append("wheel long description is missing or malformed")

    return problems


def _sdist_relative_names(names: Iterable[str]) -> List[str]:
    relative: List[str] = []
    for name in names:
        normalized = name.replace("\\", "/").lstrip("./")
        _, separator, remainder = normalized.partition("/")
        if separator and remainder:
            relative.append(remainder)
    return relative


def validate_sdist_names(names: List[str]) -> List[str]:
    """Validate the documented source-release file and directory contract."""
    relative = _sdist_relative_names(names)
    problems: List[str] = []

    for filename in REQUIRED_SDIST_FILES:
        if filename not in relative:
            problems.append(f"sdist missing required file: {filename}")
    for directory in REQUIRED_SDIST_DIRECTORIES:
        if not any(name.startswith(directory) for name in relative):
            problems.append(f"sdist missing required directory: {directory}")

    return problems


def _source_files(paths: Iterable[Path]) -> Iterable[Tuple[str, Path]]:
    for path in paths:
        if path.is_file():
            yield path.relative_to(ROOT).as_posix(), path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and "__pycache__" not in child.parts:
                    yield child.relative_to(ROOT).as_posix(), child


def validate_wheel_freshness(archive: zipfile.ZipFile) -> List[str]:
    """Reject a wheel containing source different from the current checkout."""
    problems: List[str] = []
    archive_names = set(archive.namelist())
    for relative, source in _source_files((ROOT / "flask_nacos",)):
        if relative not in archive_names:
            problems.append(f"wheel missing current source file: {relative}")
        elif archive.read(relative) != source.read_bytes():
            problems.append(f"wheel contains stale source file: {relative}")
    return problems


def validate_sdist_freshness(archive: tarfile.TarFile) -> List[str]:
    """Reject an sdist containing tracked release inputs that are stale."""
    problems: List[str] = []
    members = {name: member for name, member in ((m.name, m) for m in archive.getmembers())}
    member_names = list(members)
    if not member_names:
        return ["sdist is empty"]
    root_name = member_names[0].split("/", 1)[0]

    release_inputs = (
        ROOT / "flask_nacos",
        ROOT / "tests",
        ROOT / "examples",
        ROOT / "scripts",
        ROOT / "docs",
        *(ROOT / name for name in REQUIRED_SDIST_FILES),
    )
    for relative, source in _source_files(release_inputs):
        archive_name = f"{root_name}/{relative}"
        member = members.get(archive_name)
        if member is None:
            problems.append(f"sdist missing current source file: {relative}")
            continue
        extracted = archive.extractfile(member)
        if extracted is None or extracted.read() != source.read_bytes():
            problems.append(f"sdist contains stale source file: {relative}")
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

    if len(wheels) != 1:
        problems.append(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        problems.append(f"expected exactly one sdist, found {len(sdists)}")

    if len(wheels) == 1:
        with zipfile.ZipFile(wheels[0]) as archive:
            names = archive.namelist()
            metadata_names = [
                name for name in names if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                problems.append("wheel must contain exactly one .dist-info/METADATA file")
            else:
                metadata_text = archive.read(metadata_names[0]).decode("utf-8")
                readme = (ROOT / "README.md").read_text(encoding="utf-8")
                problems.extend(validate_wheel_metadata(metadata_text, readme))
            problems.extend(validate_wheel_names(names))
            problems.extend(validate_wheel_freshness(archive))

    if len(sdists) == 1:
        with tarfile.open(sdists[0], "r:gz") as archive:
            problems.extend(validate_sdist_names(archive.getnames()))
            problems.extend(validate_sdist_freshness(archive))

    if problems:
        print("[check_package] FAILED", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"[check_package] OK - wheel: {Path(wheels[0]).name}, "
        f"sdist: {Path(sdists[0]).name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
