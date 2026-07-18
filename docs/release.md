# Release Guide

English | [简体中文](release.zh-CN.md)

This guide publishes **flask-nacos** through GitHub Actions and PyPI Trusted
Publishing. Local commands prepare and inspect artifacts, but never upload
them.

## 1. Release invariants

- Release from the default `master` branch after its complete CI matrix passes.
- Keep `[project].version`, `flask_nacos.__version__`, the newest changelog
  heading, and the `vX.Y.Z` tag identical.
- PyPI versions are immutable. If a release is wrong, yank it, increment the
  version, and publish a new release; never try to overwrite it.
- Do not publish when either opt-in real-Nacos integration test fails.

## 2. One-time GitHub and index setup

Create two GitHub Environments:

- `testpypi`: used by the manual rehearsal job.
- `pypi`: require a trusted reviewer and restrict deployment to protected tags
  matching `v*`.

In both PyPI and TestPyPI, create a Pending Trusted Publisher with these exact
values:

| Field | Value |
| --- | --- |
| PyPI project | `flask-nacos` |
| GitHub owner | `pumpkin-nbc` |
| Repository | `Flask-Nacos` |
| Workflow | `release.yml` |
| Environment | `pypi` or `testpypi` |

A pending publisher does not reserve the package name. Complete the release
soon after configuration. The workflow uses short-lived OIDC credentials and
does not require `PYPI_API_TOKEN` or `TEST_PYPI_API_TOKEN`. After OIDC succeeds,
delete any old repository secrets and revoke their tokens on both indexes.

Enable GitHub Private Vulnerability Reporting so the process documented in
[`SECURITY.md`](../SECURITY.md) is available.

## 3. Validate against a non-production Nacos

Use a dedicated account with configuration read/write permission. Inject all
values through environment variables and never commit credentials.

```powershell
$env:FLASK_NACOS_RUN_AUTH_INTEGRATION = "1"
$env:FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION = "1"
$env:FLASK_NACOS_TEST_SERVER_ADDR = "nacos-test.example:8848"
$env:FLASK_NACOS_TEST_USERNAME = "<test-user>"
$env:FLASK_NACOS_TEST_PASSWORD = "<test-password>"
$env:FLASK_NACOS_TEST_NAMESPACE_ID = "<optional-namespace-id>"
.venv\Scripts\python -m pytest tests/test_authenticated_integration.py tests/test_heartbeat_integration.py -v
```

```bash
export FLASK_NACOS_RUN_AUTH_INTEGRATION="1"
export FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION="1"
export FLASK_NACOS_TEST_SERVER_ADDR="nacos-test.example:8848"
export FLASK_NACOS_TEST_USERNAME="<test-user>"
read -s FLASK_NACOS_TEST_PASSWORD && export FLASK_NACOS_TEST_PASSWORD
export FLASK_NACOS_TEST_NAMESPACE_ID="<optional-namespace-id>"
.venv/bin/python -m pytest tests/test_authenticated_integration.py tests/test_heartbeat_integration.py -v
```

The authentication test publishes, reads, and removes a unique temporary
configuration. The heartbeat test registers a unique ephemeral service, waits
35 seconds by default, confirms it remains healthy, and deregisters it in a
`finally` block.

## 4. Clean local verification

Run from the repository root:

```bash
bash scripts/release_check.sh
```

The script runs Ruff, mypy, pytest, version, sensitive-information,
documentation, compatibility, API and example checks; removes old build
artifacts; builds wheel and sdist; runs `twine check --strict`; verifies
metadata, contents and source freshness; then installs both artifacts in
separate temporary environments.

Confirm that `git status` contains no unintended tracked or untracked release
input. Local notes outside Hatch's explicit sdist include list do not enter the
package, but must still be reviewed deliberately.

## 5. Merge the release commit

Open a pull request from `develop` to `master`. Do not publish from `develop`.
After review, merge and confirm every Python/Flask CI matrix job and the quality
job pass on the resulting `master` commit.

## 6. TestPyPI rehearsal

From the Actions tab on `master`, run the **Release** workflow manually. Manual
dispatch is TestPyPI-only; the workflow rejects any branch other than `master`,
rebuilds from a clean checkout, verifies that `1.0.0` does not already exist,
and publishes the checked artifacts through the `testpypi` environment.

Verify installation in clean Python 3.8 and 3.13 environments:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos==1.0.0
python -c "from flask_nacos import FlaskNacos; import flask_nacos; print(flask_nacos.__version__)"
```

Also inspect the TestPyPI project page: README links, project URLs, Apache-2.0
expression, `LICENSE`, `NOTICE`, and the English/Chinese entry points must all
be correct.

## 7. PyPI release

Create the protected tag on the verified `master` commit and push it:

```bash
git switch master
git pull --ff-only origin master
git tag -a v1.0.0 -m "Flask-Nacos v1.0.0"
git push origin v1.0.0
```

The tag workflow checks that the tag is on `master` and exactly matches all
version declarations. It rebuilds and validates the artifacts, then pauses at
the protected `pypi` environment. Review the commit and artifacts before
approving the deployment. The publish action generates PEP 740 attestations by
default.

## 8. Post-release verification

Install from PyPI in a fresh environment:

```bash
python -m pip install flask-nacos==1.0.0
python -c "from flask_nacos import FlaskNacos; import flask_nacos; print(flask_nacos.__version__)"
```

Confirm the PyPI files, hashes, provenance, license expression, license files,
project URLs, README links, and version. Then create a GitHub Release named
`Flask-Nacos v1.0.0` from `v1.0.0`, using the matching changelog section as the
release notes.

## 9. Failure handling

- Before upload, fix the cause and rebuild from a clean checkout.
- If TestPyPI already contains the version, increment the test release version;
  TestPyPI files are also immutable.
- If PyPI received a bad release, yank it, fix the issue, increment the version,
  and publish again.
- Never move a tag after a successful PyPI upload.
