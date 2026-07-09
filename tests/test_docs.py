"""Documentation consistency tests."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
DOCS_DIR = ROOT / "docs"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

check_docs = importlib.import_module("check_docs")

EXPECTED_DOCS = [
    "quickstart.md",
    "configuration.md",
    "api-reference.md",
    "service-registration.md",
    "service-discovery.md",
    "health-check.md",
    "production.md",
    "troubleshooting.md",
    "release.md",
    "changelog.md",
]

FORBIDDEN = ("get_config_as_dict", "load_config_to_flask")


def test_expected_docs_exist():
    for name in EXPECTED_DOCS:
        assert (DOCS_DIR / name).is_file(), f"missing docs/{name}"


def test_readme_links_and_docs_cross_links_resolve():
    assert check_docs.check_links(ROOT) == []


def test_example_references_exist():
    assert check_docs.check_example_refs(ROOT) == []


def test_docs_do_not_describe_unsupported_features():
    assert check_docs.check_forbidden(ROOT) == []


def test_readme_references_docs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/quickstart.md" in readme
    assert "docs/configuration.md" in readme
    assert "docs/api-reference.md" in readme


def test_readme_has_no_forbidden_identifiers():
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{name} must not mention {token}"
