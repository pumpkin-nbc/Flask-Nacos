#!/usr/bin/env bash
#
# One-shot pre-release checks for flask-nacos.
#
# Runs linting, type checks, tests, version/sensitive-info checks, builds the
# distributions, verifies them with twine, and inspects the package contents.
# It NEVER uploads to PyPI -- publishing is a separate, explicit step (see
# docs/release.md).
#
# Usage:
#   bash scripts/release_check.sh
#
set -euo pipefail

# Resolve the repo root (parent of this script's directory).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# Prefer the project virtualenv's Python if present, else fall back to python3.
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  PY="python3"
fi

echo "==> Using Python: ${PY}"

echo "==> [1/13] Ruff lint"
"${PY}" -m ruff check .

echo "==> [2/13] Mypy type check"
"${PY}" -m mypy flask_nacos

echo "==> [3/13] Pytest"
"${PY}" -m pytest

echo "==> [4/13] Version consistency"
"${PY}" scripts/check_version.py

echo "==> [5/13] Sensitive information scan"
"${PY}" scripts/check_sensitive_info.py

echo "==> [6/13] Documentation checks"
"${PY}" scripts/check_docs.py

echo "==> [7/13] Compatibility checks"
"${PY}" scripts/check_compatibility.py

echo "==> [8/13] Public API snapshot check"
"${PY}" scripts/check_api_snapshot.py

echo "==> [9/13] Examples check"
"${PY}" scripts/check_examples.py

echo "==> [10/13] Clean previous build artifacts"
rm -rf dist build ./*.egg-info

echo "==> [11/13] Build distributions"
"${PY}" -m build

echo "==> [12/13] Twine check + package content check"
"${PY}" -m twine check dist/*
"${PY}" scripts/check_package.py

echo "==> [13/13] Package smoke test"
"${PY}" scripts/smoke_test_package.py

echo "==> All pre-release checks passed. Publishing is a separate step (see docs/release.md)."
