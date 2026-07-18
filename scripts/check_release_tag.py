#!/usr/bin/env python
"""Require a release tag to exactly match the project's declared version."""

import os
import sys
from typing import Optional

from check_version import ROOT, check


def validate_tag(tag: Optional[str]) -> str:
    ok, versions, message = check(ROOT)
    if not ok:
        raise ValueError(message)
    version = versions["pyproject.toml"]
    expected = f"v{version}"
    if tag != expected:
        raise ValueError(f"release tag must be {expected!r}, got {tag!r}")
    return expected


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME")
    try:
        expected = validate_tag(tag)
    except ValueError as exc:
        print(f"[check_release_tag] FAILED - {exc}", file=sys.stderr)
        return 1
    print(f"[check_release_tag] OK - {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
