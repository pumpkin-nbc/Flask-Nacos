"""Tests for the release-tooling scripts in scripts/."""

import importlib
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(scope="module")
def check_version():
    return importlib.import_module("check_version")


@pytest.fixture(scope="module")
def check_package():
    return importlib.import_module("check_package")


@pytest.fixture(scope="module")
def check_sensitive_info():
    return importlib.import_module("check_sensitive_info")


@pytest.fixture(scope="module")
def check_docs():
    return importlib.import_module("check_docs")


@pytest.fixture(scope="module")
def check_compatibility():
    return importlib.import_module("check_compatibility")


@pytest.fixture(scope="module")
def check_api_snapshot():
    return importlib.import_module("check_api_snapshot")


@pytest.fixture(scope="module")
def check_examples():
    return importlib.import_module("check_examples")


@pytest.fixture(scope="module")
def smoke_test_package():
    return importlib.import_module("smoke_test_package")


@pytest.fixture(scope="module")
def check_release_tag():
    return importlib.import_module("check_release_tag")


@pytest.fixture(scope="module")
def check_index_version():
    return importlib.import_module("check_index_version")


def _valid_metadata(body="# Flask-Nacos\n", extra_headers=""):
    metadata = """\
Metadata-Version: 2.4
Name: flask-nacos
Version: 1.0.0
License-Expression: Apache-2.0
License-File: LICENSE
License-File: NOTICE
Classifier: Operating System :: OS Independent
Classifier: Typing :: Typed
Project-URL: Changelog, https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/CHANGELOG.md
Project-URL: Documentation, https://github.com/pumpkin-nbc/Flask-Nacos/tree/master/docs
Project-URL: Security, https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/SECURITY.md
"""
    if extra_headers:
        metadata += extra_headers + "\n"
    return metadata + "\n" + body


def _valid_sdist_names():
    root = "flask_nacos-1.0.0"
    files = [
        "README.md",
        "README.zh-CN.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "LICENSE",
        "NOTICE",
        "pyproject.toml",
        "flask_nacos/__init__.py",
        "tests/test_package.py",
        "examples/basic_app.py",
        "scripts/check_package.py",
        "docs/release.md",
    ]
    return [f"{root}/{name}" for name in files]


def test_scripts_are_import_safe(
    check_version,
    check_package,
    check_sensitive_info,
    check_docs,
    check_compatibility,
    check_api_snapshot,
    check_examples,
    smoke_test_package,
    check_release_tag,
    check_index_version,
):
    assert check_version is not None
    assert check_package is not None
    assert check_sensitive_info is not None
    assert check_docs is not None
    assert check_compatibility is not None
    assert check_api_snapshot is not None
    assert check_examples is not None
    assert smoke_test_package is not None
    assert check_release_tag is not None
    assert check_index_version is not None


def test_version_check_passes_with_100(check_version):
    ok, versions, message = check_version.check(ROOT)
    assert ok, message
    assert versions["pyproject.toml"] == "1.0.0"
    assert versions["flask_nacos/__init__.py"] == "1.0.0"
    assert versions["CHANGELOG.md"] == "1.0.0"


def test_docs_check_is_clean(check_docs):
    problems = check_docs.scan(ROOT)
    assert problems == [], f"unexpected doc problems: {problems}"


def test_compatibility_check_is_clean(check_compatibility):
    problems = check_compatibility.scan(ROOT)
    assert problems == [], f"unexpected compatibility problems: {problems}"


def test_api_snapshot_is_clean(check_api_snapshot):
    problems = check_api_snapshot.scan()
    assert problems == [], f"unexpected API snapshot problems: {problems}"


def test_examples_check_is_clean(check_examples):
    problems = check_examples.scan()
    assert problems == [], f"unexpected example problems: {problems}"


def test_smoke_test_package_has_entrypoint(smoke_test_package):
    assert callable(smoke_test_package.main)


def test_sensitive_scan_is_clean(check_sensitive_info):
    findings = check_sensitive_info.scan_repo(ROOT)
    assert findings == [], f"unexpected findings: {findings}"


def test_validate_wheel_names_accepts_good_wheel(check_package):
    good = [
        "flask_nacos/__init__.py",
        "flask_nacos/extension.py",
        "flask_nacos/py.typed",
        "flask_nacos-0.6.0.dist-info/METADATA",
        "flask_nacos-0.6.0.dist-info/licenses/LICENSE",
        "flask_nacos-0.6.0.dist-info/licenses/NOTICE",
    ]
    assert check_package.validate_wheel_names(good) == []


def test_validate_wheel_names_rejects_tests(check_package):
    names = [
        "flask_nacos/__init__.py",
        "flask_nacos/extension.py",
        "flask_nacos/py.typed",
        "tests/test_packaging.py",
    ]
    problems = check_package.validate_wheel_names(names)
    assert any("tests" in problem for problem in problems)


def test_validate_wheel_names_rejects_env_file(check_package):
    names = [
        "flask_nacos/__init__.py",
        "flask_nacos/extension.py",
        "flask_nacos/py.typed",
        ".env",
    ]
    problems = check_package.validate_wheel_names(names)
    assert any(".env" in problem for problem in problems)


def test_validate_wheel_names_requires_py_typed(check_package):
    names = [
        "flask_nacos/__init__.py",
        "flask_nacos/extension.py",
    ]
    problems = check_package.validate_wheel_names(names)
    assert any("py.typed" in problem for problem in problems)


def test_validate_wheel_names_requires_license_and_notice(check_package):
    names = [
        "flask_nacos/__init__.py",
        "flask_nacos/extension.py",
        "flask_nacos/py.typed",
        "flask_nacos-1.0.0.dist-info/METADATA",
    ]

    problems = check_package.validate_wheel_names(names)

    assert "missing packaged license file: LICENSE" in problems
    assert "missing packaged license file: NOTICE" in problems


def test_validate_wheel_metadata_accepts_apache_2(check_package):
    metadata = _valid_metadata()
    assert check_package.validate_wheel_metadata(metadata) == []


def test_validate_wheel_metadata_rejects_wrong_license(check_package):
    metadata = _valid_metadata().replace(
        "License-Expression: Apache-2.0", "License-Expression: GPL-3.0-or-later"
    )

    problems = check_package.validate_wheel_metadata(metadata)

    assert any("wrong License-Expression" in problem for problem in problems)


def test_validate_wheel_metadata_requires_both_license_files(check_package):
    metadata = _valid_metadata().replace("License-File: NOTICE\n", "")

    problems = check_package.validate_wheel_metadata(metadata)

    assert "missing License-File metadata: NOTICE" in problems


def test_validate_wheel_metadata_rejects_deprecated_classifier(check_package):
    metadata = _valid_metadata(
        extra_headers="Classifier: License :: OSI Approved :: Apache Software License"
    )

    problems = check_package.validate_wheel_metadata(metadata)

    assert any("deprecated license classifier" in problem for problem in problems)


def test_validate_sdist_names_requires_license_and_notice(check_package):
    names = _valid_sdist_names()
    assert check_package.validate_sdist_names(names) == []

    problems = check_package.validate_sdist_names(
        [name for name in names if not name.endswith("/NOTICE")]
    )
    assert "sdist missing required file: NOTICE" in problems


def test_validate_sdist_names_requires_bilingual_readme_and_release_dirs(
    check_package,
):
    names = _valid_sdist_names()
    without_chinese = [name for name in names if not name.endswith("README.zh-CN.md")]
    problems = check_package.validate_sdist_names(without_chinese)
    assert "sdist missing required file: README.zh-CN.md" in problems

    without_docs = [name for name in names if "/docs/" not in name]
    problems = check_package.validate_sdist_names(without_docs)
    assert "sdist missing required directory: docs/" in problems


def test_validate_wheel_metadata_rejects_relative_readme_link(check_package):
    problems = check_package.validate_wheel_metadata(
        _valid_metadata("Read the [guide](docs/quickstart.md).\n")
    )
    assert any("relative Markdown link" in problem for problem in problems)


def test_validate_wheel_metadata_rejects_stale_readme(check_package):
    problems = check_package.validate_wheel_metadata(
        _valid_metadata("current\n"), expected_readme="new\n"
    )
    assert "wheel long description does not match current README.md" in problems


def test_validate_wheel_metadata_rejects_main_branch_url(check_package):
    metadata = _valid_metadata().replace("/blob/master/", "/blob/main/")
    problems = check_package.validate_wheel_metadata(metadata)
    assert any("unavailable main branch" in problem for problem in problems)


def test_release_tag_must_match_version(check_release_tag):
    assert check_release_tag.validate_tag("v1.0.0") == "v1.0.0"
    with pytest.raises(ValueError, match="release tag must be"):
        check_release_tag.validate_tag("v1.0.1")


def test_index_preflight_accepts_404(check_index_version, monkeypatch):
    def missing(*_args, **_kwargs):
        raise HTTPError("https://example.invalid", 404, "not found", None, None)

    monkeypatch.setattr(check_index_version, "urlopen", missing)
    assert check_index_version.ensure_version_available("pypi") == (
        "flask-nacos",
        "1.0.0",
    )


def test_index_preflight_rejects_existing_version(check_index_version, monkeypatch):
    class Response:
        def close(self):
            return None

    monkeypatch.setattr(check_index_version, "urlopen", lambda *_a, **_k: Response())
    with pytest.raises(ValueError, match="already exists"):
        check_index_version.ensure_version_available("testpypi")


def test_release_workflow_uses_protected_oidc_publish_jobs():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    assert "workflow_dispatch:" in workflow
    assert '      - "v*"' in workflow
    assert "name: testpypi" in workflow
    assert "name: pypi" in workflow
    assert workflow.count("id-token: write") == 2
    assert workflow.count("pypa/gh-action-pypi-publish@release/v1") == 2
    assert "scripts/check_release_tag.py" in workflow
    assert "scripts/check_index_version.py testpypi" in workflow
    assert "scripts/check_index_version.py pypi" in workflow
    assert "PYPI_API_TOKEN" not in workflow
    assert "twine upload" not in workflow
