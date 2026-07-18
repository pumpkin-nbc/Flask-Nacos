"""Tests for the release-tooling scripts in scripts/."""

import importlib
import sys
from pathlib import Path

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


def test_scripts_are_import_safe(
    check_version,
    check_package,
    check_sensitive_info,
    check_docs,
    check_compatibility,
    check_api_snapshot,
    check_examples,
    smoke_test_package,
):
    assert check_version is not None
    assert check_package is not None
    assert check_sensitive_info is not None
    assert check_docs is not None
    assert check_compatibility is not None
    assert check_api_snapshot is not None
    assert check_examples is not None
    assert smoke_test_package is not None


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
    metadata = """\
Metadata-Version: 2.4
Name: flask-nacos
Version: 1.0.0
License-Expression: Apache-2.0
License-File: LICENSE
License-File: NOTICE
"""

    assert check_package.validate_wheel_metadata(metadata) == []


def test_validate_wheel_metadata_rejects_wrong_license(check_package):
    metadata = """\
Metadata-Version: 2.4
Name: flask-nacos
Version: 1.0.0
License-Expression: GPL-3.0-or-later
License-File: LICENSE
License-File: NOTICE
"""

    problems = check_package.validate_wheel_metadata(metadata)

    assert any("wrong License-Expression" in problem for problem in problems)


def test_validate_wheel_metadata_requires_both_license_files(check_package):
    metadata = """\
Metadata-Version: 2.4
Name: flask-nacos
Version: 1.0.0
License-Expression: Apache-2.0
License-File: LICENSE
"""

    problems = check_package.validate_wheel_metadata(metadata)

    assert "missing License-File metadata: NOTICE" in problems


def test_validate_wheel_metadata_rejects_deprecated_classifier(check_package):
    metadata = """\
Metadata-Version: 2.4
Name: flask-nacos
Version: 1.0.0
License-Expression: Apache-2.0
License-File: LICENSE
License-File: NOTICE
Classifier: License :: OSI Approved :: Apache Software License
"""

    problems = check_package.validate_wheel_metadata(metadata)

    assert any("deprecated license classifier" in problem for problem in problems)


def test_validate_sdist_names_requires_license_and_notice(check_package):
    assert check_package.validate_sdist_names(
        ["flask_nacos-1.0.0/LICENSE", "flask_nacos-1.0.0/NOTICE"]
    ) == []

    problems = check_package.validate_sdist_names(
        ["flask_nacos-1.0.0/LICENSE"]
    )
    assert "sdist missing license file: NOTICE" in problems
