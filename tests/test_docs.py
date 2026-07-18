"""Documentation consistency tests."""

import importlib
import re
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
    "complete-example.md",
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
    assert "docs/complete-example.md" in readme


def test_pypi_readme_uses_absolute_repository_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    relative = re.findall(r"\]\((?!https?://|mailto:|#)([^)]+)\)", readme)
    assert relative == []
    assert "https://github.com/pumpkin-nbc/Flask-Nacos/blob/master/README.zh-CN.md" in readme


def test_security_policy_exists_and_uses_private_reporting():
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "Report a vulnerability" in security
    assert "do not open a public issue" in security


def test_bilingual_release_guides_document_oidc_gates():
    english = (DOCS_DIR / "release.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "release.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "Trusted Publisher",
        "testpypi",
        "pypi",
        "release.yml",
        "pumpkin-nbc",
        "Flask-Nacos",
        "v1.0.0",
        "twine check --strict",
        "FLASK_NACOS_RUN_AUTH_INTEGRATION",
        "FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION",
        "SECURITY.md",
    )
    for marker in shared_markers:
        assert marker in english
        assert marker in chinese


def test_complete_example_guides_share_commands_and_defaults():
    english = (DOCS_DIR / "complete-example.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "complete-example.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "examples/complete_factory_app.py",
        "examples/docker-compose-nacos.yml up -d",
        "flask-nacos-complete-demo",
        "flask-nacos-demo.properties",
        "python examples/complete_factory_app.py",
        "/api/nacos/status",
        "/api/nacos/config",
        "/api/nacos/instances",
        "/health/nacos",
        'gunicorn "examples.complete_factory_app:create_app()"',
    )

    for marker in shared_markers:
        assert marker in english
        assert marker in chinese


def test_complete_guides_document_centralized_extension_initialization():
    english = (DOCS_DIR / "complete-example.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "complete-example.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "# app/extensions.py",
        "nacos = FlaskNacos()",
        "def extension_config(app):",
        "# app/app.py",
        "app.config.from_object(config_object)",
        "# app/routes.py",
        "from app.extensions import nacos",
        "with app.app_context():",
        'app.extensions["nacos"]',
        "NACOS_SERVICE_IP",
        "NACOS_REGISTER_ENABLED = False",
        "NACOS_AUTO_REGISTER = False",
    )

    for marker in shared_markers:
        assert marker in english
        assert marker in chinese

    english_blocks = re.findall(r"```python\n(.*?)```", english, re.DOTALL)
    chinese_blocks = re.findall(r"```python\n(.*?)```", chinese, re.DOTALL)
    assert english_blocks == chinese_blocks
    assert len(english_blocks) == 4

    for index, code in enumerate(english_blocks):
        compile(code, f"complete-example-{index}.py", "exec")

    app_code = next(code for code in english_blocks if code.startswith("# app/app.py"))
    assert app_code.index("app.config.from_object") < app_code.index(
        "extension_config(app)"
    )
    assert app_code.index("extension_config(app)") < app_code.index(
        "app.register_blueprint"
    )


def test_beginner_quickstarts_are_copyable_and_consistent():
    english = (DOCS_DIR / "quickstart.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "quickstart.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "examples/beginner_app.py",
        "flask-nacos-beginner",
        "flask-nacos-beginner.properties",
        "NACOS_ENABLED=true",
        "/nacos/status",
        "/health/nacos",
        "/nacos/config",
        "/nacos/instances",
        "flask-nacos-beginner-nacos",
        "nacos/nacos-server:v2.3.2",
        "docker stop flask-nacos-beginner-nacos",
        "docker rm flask-nacos-beginner-nacos",
        'NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR"',
        'NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP"',
        "203.0.113.10:8848",
        "203.0.113.20:3000",
        "NACOS_SERVICE_HEARTBEAT_INTERVAL",
        "Get-Credential",
        "Test-NetConnection",
        "NACOS_ACCESS_KEY",
    )

    for marker in shared_markers:
        assert marker in english
        assert marker in chinese

    english_code = re.search(r"```python\n(.*?)```", english, re.DOTALL)
    chinese_code = re.search(r"```python\n(.*?)```", chinese, re.DOTALL)
    assert english_code is not None
    assert chinese_code is not None
    assert english_code.group(1) == chinese_code.group(1)
    compile(english_code.group(1), "quickstart-app.py", "exec")


def test_complete_guides_document_opt_in_authentication_test():
    english = (DOCS_DIR / "complete-example.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "complete-example.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "FLASK_NACOS_RUN_AUTH_INTEGRATION",
        "FLASK_NACOS_TEST_SERVER_ADDR",
        "FLASK_NACOS_TEST_USERNAME",
        "FLASK_NACOS_TEST_PASSWORD",
        "FLASK_NACOS_TEST_NAMESPACE_ID",
        "tests/test_authenticated_integration.py",
        "FLASK_NACOS_TEST",
    )

    for marker in shared_markers:
        assert marker in english
        assert marker in chinese


def test_bilingual_docs_describe_strict_runtime_validation():
    english_files = (
        ROOT / "README.md",
        DOCS_DIR / "configuration.md",
        DOCS_DIR / "troubleshooting.md",
    )
    chinese_files = (
        ROOT / "README.zh-CN.md",
        DOCS_DIR / "configuration.zh-CN.md",
        DOCS_DIR / "troubleshooting.zh-CN.md",
    )
    shared_markers = (
        "NACOS_RETRY_TIMES",
        "NACOS_RETRY_INTERVAL",
        "NACOS_REQUEST_TIMEOUT",
        "NACOS_USERNAME",
        "NACOS_ACCESS_KEY",
        "NACOS_FAIL_FAST",
    )

    for path in english_files + chinese_files:
        text = path.read_text(encoding="utf-8")
        for marker in shared_markers:
            assert marker in text


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
