#!/usr/bin/env python
"""Fail when the release version already exists on PyPI or TestPyPI."""

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from check_version import ROOT, check

INDEXES = {
    "pypi": "https://pypi.org",
    "testpypi": "https://test.pypi.org",
}


def _project_name(root: Path = ROOT) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    project = text.split("[project]", 1)[-1]
    match = re.search(r'^name\s*=\s*"([^"]+)"', project, re.MULTILINE)
    if not match:
        raise ValueError("could not read project name from pyproject.toml")
    return match.group(1)


def release_identity(root: Path = ROOT) -> Tuple[str, str]:
    ok, versions, message = check(root)
    if not ok:
        raise ValueError(message)
    return _project_name(root), versions["pyproject.toml"]


def ensure_version_available(index: str) -> Tuple[str, str]:
    name, version = release_identity()
    url = f"{INDEXES[index]}/pypi/{name}/{version}/json"
    try:
        response = urlopen(url, timeout=15)
    except HTTPError as exc:
        if exc.code == 404:
            return name, version
        raise RuntimeError(f"index preflight returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"index preflight failed: {exc.reason}") from exc
    else:
        response.close()
        raise ValueError(f"{name}=={version} already exists on {index}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("index", choices=sorted(INDEXES))
    args = parser.parse_args()
    try:
        name, version = ensure_version_available(args.index)
    except (RuntimeError, ValueError) as exc:
        print(f"[check_index_version] FAILED - {exc}", file=sys.stderr)
        return 1
    print(f"[check_index_version] OK - {name}=={version} is available on {args.index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
