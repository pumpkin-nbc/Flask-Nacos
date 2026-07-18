#!/usr/bin/env python
"""Scan the project for sensitive information before publishing.

Looks for likely-real secret assignments, private IP addresses, internal
domain names, and stray ``.env`` files. Uses value-based detection with an
allowlist so that field-name mentions (e.g. documenting ``NACOS_PASSWORD``)
and demo credentials (``nacos/nacos``) do not trip the scan.

Standard library only. Exits non-zero when anything suspicious is found.
"""

import re
import sys
from pathlib import Path
from typing import List, NamedTuple

ROOT = Path(__file__).resolve().parent.parent

# Directories that are never published or that contain synthetic fixtures.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".cursor",
    ".idea",
    "tests",
}

# Only scan text-ish files.
SCAN_SUFFIXES = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".yml",
    ".yaml",
    ".sh",
}

# Values that are safe (demo/placeholder/empty), compared case-insensitively.
ALLOWED_VALUES = {
    "",
    "nacos",
    "none",
    "null",
    "***",
    "changeme",
    "change-me",
    "your-password",
    "your_password",
    "your-token",
    "your_token",
    "xxx",
    "xxxx",
    "example",
    "placeholder",
    "secret",
    "password",
}

SECRET_KEYS = (
    "NACOS_PASSWORD",
    "NACOS_ACCESS_KEY",
    "NACOS_SECRET_KEY",
    "password",
    "passwd",
    "access_key",
    "secret_key",
)

_SECRET_RE = re.compile(
    r"(?i)\b(" + "|".join(re.escape(k) for k in SECRET_KEYS) + r")\b\s*[:=]\s*"
    r"""(['"])(?P<value>.*?)\2"""
)
_PRIVATE_IP_RE = re.compile(r"\b(?:192\.168|10\.10)\.\d{1,3}\.\d{1,3}\b")
_INTERNAL_DOMAIN_RE = re.compile(r"\b[a-z0-9-]+\.(?:corp|internal|intranet|lan)\b", re.IGNORECASE)


class Finding(NamedTuple):
    path: str
    lineno: int
    reason: str


def _is_placeholder(value: str) -> bool:
    stripped = value.strip()
    if stripped.lower() in ALLOWED_VALUES:
        return True
    # Env-var / template style references are not real secrets.
    if stripped.startswith("$") or "{{" in stripped or "${" in stripped:
        return True
    if stripped.startswith("<") and stripped.endswith(">"):
        return True
    return False


def _scan_line(line: str) -> List[str]:
    reasons: List[str] = []

    for match in _SECRET_RE.finditer(line):
        value = match.group("value")
        if not _is_placeholder(value):
            reasons.append(f"possible hardcoded secret for {match.group(1)!r}")

    if _PRIVATE_IP_RE.search(line):
        reasons.append("private IP address")

    if _INTERNAL_DOMAIN_RE.search(line):
        reasons.append("possible internal domain")

    return reasons


def scan_repo(root: Path = ROOT) -> List[Finding]:
    """Scan the repository and return a list of findings (empty means clean)."""
    findings: List[Finding] = []
    self_path = Path(__file__).resolve()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue

        rel = path.relative_to(root).as_posix()

        # A real .env file must never be present.
        if path.name == ".env":
            findings.append(Finding(rel, 0, ".env file present"))
            continue

        if path.resolve() == self_path:
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            for reason in _scan_line(line):
                findings.append(Finding(rel, lineno, reason))

    return findings


def main() -> int:
    findings = scan_repo()
    if not findings:
        print("[check_sensitive_info] OK - no sensitive information detected")
        return 0

    print("[check_sensitive_info] FAILED - potential sensitive information:", file=sys.stderr)
    for finding in findings:
        location = f"{finding.path}:{finding.lineno}" if finding.lineno else finding.path
        print(f"  - {location}: {finding.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
