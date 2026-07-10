#!/usr/bin/env python
"""Smoke-test the built wheel in an isolated temporary virtual environment.

Builds nothing itself: it expects ``python -m build`` to have produced a wheel
under ``dist/``. It then creates a throwaway venv (never the project ``.venv``),
installs the wheel there, and runs a subprocess that imports the package and
performs a minimal, offline initialization.

Verifies that the installed package:

- imports as ``flask_nacos`` and exposes ``FlaskNacos``;
- initializes on a Flask app with ``NACOS_ENABLED=False`` (no network);
- registers ``app.extensions["nacos"]``;
- reports the expected ``__version__``.

No real Nacos, no credentials. Exits non-zero on any failure.
"""

import glob
import os
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

_CHECK_SCRIPT = """
import flask_nacos
from flask_nacos import FlaskNacos
from flask import Flask

expected = {expected!r}
assert flask_nacos.__version__ == expected, (
    "version mismatch: %r != %r" % (flask_nacos.__version__, expected)
)

app = Flask(__name__)
app.config.update(NACOS_ENABLED=False)
nacos = FlaskNacos(app)
assert "nacos" in app.extensions, "app.extensions['nacos'] missing"

print("[smoke] import + init OK (version=%s)" % flask_nacos.__version__)
"""


def _expected_version() -> str:
    init_py = (ROOT / "flask_nacos" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_py)
    if not match:
        raise RuntimeError("could not read __version__ from flask_nacos/__init__.py")
    return match.group(1)


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _find_wheel() -> str:
    wheels = sorted(glob.glob(str(DIST / "*.whl")))
    if not wheels:
        raise FileNotFoundError("no wheel (*.whl) found in dist/; run `python -m build` first")
    return wheels[-1]


def main() -> int:
    try:
        wheel = _find_wheel()
        expected = _expected_version()
    except Exception as exc:
        print(f"[smoke_test_package] FAILED - {exc}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="flask-nacos-smoke-") as tmp:
        venv_dir = Path(tmp) / "venv"
        print(f"[smoke_test_package] creating temp venv at {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(str(venv_dir))
        py = _venv_python(venv_dir)

        install = subprocess.run(
            [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", wheel],
        )
        if install.returncode != 0:
            print("[smoke_test_package] FAILED - wheel install failed", file=sys.stderr)
            return 1

        check = subprocess.run([str(py), "-c", _CHECK_SCRIPT.format(expected=expected)])
        if check.returncode != 0:
            print("[smoke_test_package] FAILED - import/init check failed", file=sys.stderr)
            return 1

    print(f"[smoke_test_package] OK - {Path(wheel).name} installs and imports (v{expected})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
