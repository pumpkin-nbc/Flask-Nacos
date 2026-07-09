"""Static checks for the example applications (no import, no network)."""

import py_compile
import re
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

EXAMPLE_FILES = [
    "basic_app.py",
    "factory_app.py",
    "service_registration.py",
    "service_discovery.py",
    "health_check_app.py",
    "production_config.py",
]

PRIVATE_IP_RE = r"\b(?:192\.168|10\.10)\.\d{1,3}\.\d{1,3}\b"


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_exists(filename):
    assert (EXAMPLES_DIR / filename).is_file()


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_compiles(filename):
    path = EXAMPLES_DIR / filename
    # Compile-only static check: verifies syntax without executing the module.
    py_compile.compile(str(path), doraise=True)


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_has_no_private_ip(filename):
    text = (EXAMPLES_DIR / filename).read_text(encoding="utf-8")
    assert re.search(PRIVATE_IP_RE, text) is None


def test_docker_compose_example_exists_and_is_clean():
    compose = EXAMPLES_DIR / "docker-compose-nacos.yml"
    assert compose.is_file()
    text = compose.read_text(encoding="utf-8")
    assert re.search(PRIVATE_IP_RE, text) is None
