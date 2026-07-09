"""Static checks for the example applications (no import, no network)."""

import py_compile
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"

EXAMPLE_FILES = [
    "basic_app.py",
    "factory_app.py",
    "service_discovery.py",
    "health_check_app.py",
]


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_exists(filename):
    assert (EXAMPLES_DIR / filename).is_file()


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_compiles(filename):
    path = EXAMPLES_DIR / filename
    # Compile-only static check: verifies syntax without executing the module.
    py_compile.compile(str(path), doraise=True)
