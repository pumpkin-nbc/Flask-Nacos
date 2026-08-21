"""Documentation consistency tests."""

import ast
import importlib
import re
import sys
from pathlib import Path

import pytest

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


def _parse_as_python_38(code, filename):
    try:
        return ast.parse(code, filename=filename, feature_version=(3, 8))
    except TypeError:  # Python 3.8 accepts the minor version as an integer.
        return ast.parse(code, filename=filename, feature_version=8)


def test_expected_docs_exist():
    for name in EXPECTED_DOCS:
        assert (DOCS_DIR / name).is_file(), f"missing docs/{name}"


def test_root_changelogs_are_bilingual_and_version_aligned():
    english = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    chinese = (ROOT / "CHANGELOG.zh-CN.md").read_text(encoding="utf-8")
    version_pattern = r"^##\s+\[?([0-9]+\.[0-9]+\.[0-9]+)"

    assert "[简体中文](CHANGELOG.zh-CN.md)" in english
    assert "[English](CHANGELOG.md)" in chinese
    assert re.findall(version_pattern, english, re.MULTILINE) == re.findall(
        version_pattern, chinese, re.MULTILINE
    )


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
    assert "docs/service-registration.md" in readme


def test_service_registration_guides_include_lifecycle_flowcharts():
    english = (DOCS_DIR / "service-registration.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "service-registration.zh-CN.md").read_text(encoding="utf-8")
    shared_markers = (
        "register_instance(app)",
        "NACOS_AUTO_REGISTER",
        "NACOS_FAIL_FAST",
        "target_registered",
        "operation_running",
        "last_error",
        "NACOS_AUTO_DEREGISTER=False",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        "daemon",
        "single-flight",
        "flowchart TD",
    )
    for marker in shared_markers:
        assert marker in english
        assert marker in chinese
    assert english.count("```mermaid") == 2
    assert chinese.count("```mermaid") == 2

    english_code = re.findall(r"```python\n(.*?)```", english, re.DOTALL)
    chinese_code = re.findall(r"```python\n(.*?)```", chinese, re.DOTALL)
    assert english_code == chinese_code
    for index, code in enumerate(english_code):
        _parse_as_python_38(code, f"service-registration-{index}.py")


def test_auto_register_default_is_documented_as_true():
    english = {
        ROOT / "README.md": "`NACOS_AUTO_REGISTER` (default `True`)",
        DOCS_DIR / "configuration.md": "| `NACOS_AUTO_REGISTER` | bool | `True` |",
        DOCS_DIR / "production.md": "`NACOS_AUTO_REGISTER=True`",
        DOCS_DIR / "service-registration.md": "Automatic registration defaults to enabled",
    }
    chinese = {
        ROOT / "README.zh-CN.md": "`NACOS_AUTO_REGISTER`（默认 `True`）",
        DOCS_DIR / "configuration.zh-CN.md": "| `NACOS_AUTO_REGISTER` | bool | `True` |",
        DOCS_DIR / "production.zh-CN.md": "`NACOS_AUTO_REGISTER=True`",
        DOCS_DIR / "service-registration.zh-CN.md": "自动注册默认开启",
    }

    for path, marker in {**english, **chinese}.items():
        assert marker in path.read_text(encoding="utf-8")


def test_api_reference_snippets_are_bilingual_and_python_38_compatible():
    english = (DOCS_DIR / "api-reference.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "api-reference.zh-CN.md").read_text(encoding="utf-8")
    english_code = re.findall(r"```python\n(.*?)```", english, re.DOTALL)
    chinese_code = re.findall(r"```python\n(.*?)```", chinese, re.DOTALL)

    assert len(english_code) == len(chinese_code)
    for language, blocks in (("en", english_code), ("zh-CN", chinese_code)):
        for index, code in enumerate(blocks):
            _parse_as_python_38(code, f"api-reference-{language}-{index}.py")


def test_bilingual_compatibility_docs_match_ci_support_matrix():
    english = (DOCS_DIR / "compatibility.md").read_text(encoding="utf-8")
    chinese = (DOCS_DIR / "compatibility.zh-CN.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    for marker in ("3.14", "Flask `>=1.0`", "Flask 1.0.4", "Flask 3.0.x"):
        assert marker in english
        assert marker in chinese
    assert 'python-version: "3.14"' in workflow
    assert 'flask: "Flask==1.0.4 ' in workflow
    assert 'flask: "Flask==1.1.4 ' in workflow
    assert 'flask: "Flask>=3.0,<3.1"' in workflow


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
        "v1.1.1",
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
    example_source = (ROOT / "examples" / "complete_factory_app.py").read_text(encoding="utf-8")
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
        "NACOS_AUTO_DEREGISTER",
        "NACOS_LOG_CONSOLE_ENABLED",
        "NACOS_LOG_FILE_ENABLED",
        "NACOS_LOG_PATH",
        "NACOS_LOG_FILENAME",
        'gunicorn "examples.complete_factory_app:create_app()"',
    )

    for marker in shared_markers:
        assert marker in english
        assert marker in chinese

    environment_keys = set(re.findall(r'os\.environ\.get\(\s*"([A-Z0-9_]+)"', example_source))
    assert environment_keys
    for key in environment_keys:
        assert key in english
        assert key in chinese


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
    assert app_code.index("app.config.from_object") < app_code.index("extension_config(app)")
    assert app_code.index("extension_config(app)") < app_code.index("app.register_blueprint")


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
    beginner_source = (ROOT / "examples" / "beginner_app.py").read_text(encoding="utf-8")
    assert english_code.group(1).rstrip() == beginner_source.rstrip()
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


def test_bilingual_docs_describe_auto_registration_preflight():
    english_files = (
        ROOT / "README.md",
        DOCS_DIR / "service-registration.md",
        DOCS_DIR / "troubleshooting.md",
    )
    chinese_files = (
        ROOT / "README.zh-CN.md",
        DOCS_DIR / "service-registration.zh-CN.md",
        DOCS_DIR / "troubleshooting.zh-CN.md",
    )
    shared_markers = (
        "NACOS_SERVICE_NAME",
        "NACOS_AUTO_REGISTER",
        "NACOS_FAIL_FAST",
        "init_app(app)",
        "preload",
    )

    for path in english_files + chinese_files:
        text = path.read_text(encoding="utf-8")
        for marker in shared_markers:
            assert marker in text


@pytest.mark.parametrize(
    "removed_key",
    (
        "NACOS_AUTO_REGISTER_" + "ON_INIT",
        "NACOS_REGISTER_" + "ENABLED",
    ),
)
def test_removed_registration_keys_are_absent_from_current_tree(removed_key):
    text_roots = (
        ROOT / "flask_nacos",
        ROOT / "examples",
        ROOT / "docs",
        ROOT / "scripts",
        ROOT / "tests",
    )
    paths = [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CHANGELOG.zh-CN.md",
        ROOT / "pyproject.toml",
    ]
    for text_root in text_roots:
        paths.extend(
            path
            for path in text_root.rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".toml", ".yml", ".yaml"}
        )

    for path in paths:
        assert removed_key not in path.read_text(encoding="utf-8"), path


def test_bilingual_docs_describe_transient_lifecycle_recovery_without_remote_monitoring():
    english_files = (
        ROOT / "README.md",
        DOCS_DIR / "configuration.md",
        DOCS_DIR / "service-registration.md",
        DOCS_DIR / "production.md",
        DOCS_DIR / "troubleshooting.md",
        DOCS_DIR / "compatibility.md",
    )
    chinese_files = (
        ROOT / "README.zh-CN.md",
        DOCS_DIR / "configuration.zh-CN.md",
        DOCS_DIR / "service-registration.zh-CN.md",
        DOCS_DIR / "production.zh-CN.md",
        DOCS_DIR / "troubleshooting.zh-CN.md",
        DOCS_DIR / "compatibility.zh-CN.md",
    )

    for path in english_files:
        text = path.read_text(encoding="utf-8")
        assert "transient" in text.lower(), path
        assert "recovery" in text.lower(), path
    for path in chinese_files:
        text = path.read_text(encoding="utf-8")
        assert "瞬时" in text, path
        assert "自恢复" in text, path

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in english_files + chinese_files
    ).lower()
    assert "forever retry" not in combined
    assert "infinite retry" not in combined
    assert "无限重试" not in combined


def test_bilingual_docs_describe_safe_logging_and_multi_worker_identity():
    english_files = (
        ROOT / "README.md",
        DOCS_DIR / "configuration.md",
        DOCS_DIR / "production.md",
    )
    chinese_files = (
        ROOT / "README.zh-CN.md",
        DOCS_DIR / "configuration.zh-CN.md",
        DOCS_DIR / "production.zh-CN.md",
    )

    for path in english_files:
        text = path.read_text(encoding="utf-8")
        assert "SDK-native" in text or "Native SDK" in text
        assert "~/logs/nacos" in text
        assert "NACOS_LOG_PATH" in text
        assert "NACOS_LOG_FILE_ENABLED" in text
        assert "NACOS_LOG_FILENAME" in text

    for path in chinese_files:
        text = path.read_text(encoding="utf-8")
        assert "SDK 原生" in text
        assert "~/logs/nacos" in text
        assert "NACOS_LOG_PATH" in text
        assert "NACOS_LOG_FILE_ENABLED" in text
        assert "NACOS_LOG_FILENAME" in text

    for path in english_files + chinese_files:
        text = path.read_text(encoding="utf-8")
        assert "flask-nacos.log" in text

    for path in (english_files[0], english_files[2]):
        text = path.read_text(encoding="utf-8")
        assert "same IP and port" in text or "same service/group/cluster/IP/port" in text

    for path in (chinese_files[0], chinese_files[2]):
        text = path.read_text(encoding="utf-8")
        assert "相同 IP 和端口" in text or "相同服务身份与 IP:port" in text


def test_bilingual_docs_disclose_sdk_https_limit():
    for path in (
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        DOCS_DIR / "configuration.md",
        DOCS_DIR / "configuration.zh-CN.md",
        DOCS_DIR / "production.md",
        DOCS_DIR / "production.zh-CN.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "HTTPS" in text
        assert "certificate" in text or "证书" in text


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
