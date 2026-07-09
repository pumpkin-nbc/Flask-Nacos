# Release Guide

English | [简体中文](release.zh-CN.md)

This document describes how to cut a release of **flask-nacos** to TestPyPI and
PyPI. The process is intentionally manual and gated by automated checks so that
no broken or sensitive artifact is ever published.

## 1. Pre-release preparation

Before starting a release:

- Make sure `main`/`master` is green in CI.
- Confirm the working tree is clean (`git status`).
- Review the diff since the last tag and make sure the public API is unchanged
  or that any changes are intentional and documented.

## 2. Version bump rule

**Every release must bump the version.** Versions on PyPI are immutable — you
can never re-upload the same version. Keep these three in sync:

- `pyproject.toml` → `[project].version`
- `flask_nacos/__init__.py` → `__version__`
- `CHANGELOG.md` → the newest `## X.Y.Z` heading

The `scripts/check_version.py` script enforces this consistency and runs in CI.

## 3. CHANGELOG rules

- Add a new `## X.Y.Z` section at the top of `CHANGELOG.md` for the release.
- Group entries under **Added**, **Changed**, **Fixed**, and **Notes** as
  appropriate.
- The newest heading must match the version in `pyproject.toml` and
  `__version__`.

## 4. Local pre-release checks

Run the one-shot script from the repository root:

```bash
bash scripts/release_check.sh
```

This runs, in order: `ruff`, `mypy`, `pytest`, `check_version.py`,
`check_sensitive_info.py`, a clean rebuild (`python -m build`),
`twine check dist/*`, and `check_package.py`. It never uploads anything.

You can also run the steps explicitly:

```bash
python -m ruff check .
python -m mypy flask_nacos
python -m pytest
python scripts/check_version.py
python scripts/check_sensitive_info.py
rm -rf dist build ./*.egg-info
python -m build
python -m twine check dist/*
python scripts/check_package.py
```

## 5. Publish to TestPyPI

TestPyPI is a sandbox for validating the upload and install flow:

```bash
python -m twine upload --repository testpypi dist/*
```

Then verify the install from TestPyPI in a fresh virtual environment:

```bash
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos
python -c "import flask_nacos; print(flask_nacos.__version__)"
```

## 6. Publish to PyPI

Once TestPyPI looks good:

```bash
python -m twine upload dist/*
```

## 7. Releasing via GitHub Actions

The `Release` workflow (`.github/workflows/release.yml`) can perform the upload
for you. Trigger it manually from the **Actions** tab (`workflow_dispatch`) and
choose the target index:

- `testpypi` (default) — safe sandbox.
- `pypi` — real release; must be chosen explicitly.

The workflow reruns all pre-release checks before uploading.

## 8. GitHub Secrets setup

Configure API tokens as repository secrets (Settings → Secrets and variables →
Actions):

- `TEST_PYPI_API_TOKEN` — a TestPyPI API token.
- `PYPI_API_TOKEN` — a PyPI API token.

Tokens are passed to `twine` via `TWINE_USERNAME=__token__` and
`TWINE_PASSWORD=<secret>`. Never hardcode tokens in files or logs.

## 9. Failure & rollback notes

- Versions on PyPI/TestPyPI are **immutable**. You cannot overwrite a version.
- If a bad artifact is published, **yank** the release on PyPI (this hides it
  from new installs without breaking existing pins), then **bump the version**
  and publish a fixed release.
- There is no "delete and re-upload the same version" path — always move
  forward with a new version number.

## 10. Post-release verification

After publishing to PyPI, verify from a clean environment:

```bash
pip install flask-nacos
python -c "import flask_nacos; print(flask_nacos.__version__)"
```

Confirm the reported version matches the release, then tag the commit if that
is part of your workflow.
