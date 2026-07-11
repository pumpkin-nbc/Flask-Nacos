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
    "compatibility.md",
    "1.0-checklist.md",
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


def test_readme_only_mentions_forbidden_identifiers_with_negation():
    # The README may state that these identifiers are NOT provided, but must
    # never describe them as available capabilities. A forbidden token is only
    # allowed on a line that also contains a negation marker (same rule as
    # check_docs.check_forbidden).
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            has_negation = any(marker in lowered for marker in check_docs.NEGATION_MARKERS)
            for token in FORBIDDEN:
                if token in line:
                    assert has_negation, (
                        f"{name}:{lineno} mentions {token} without a negation marker"
                    )
