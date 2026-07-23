#!/usr/bin/env python
"""Install and smoke-test both release distributions in isolated environments."""

import glob
import os
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

_CHECK_SCRIPT = """
from pathlib import Path

import flask_nacos
from flask import Flask
from flask_nacos import FlaskNacos

expected = {expected!r}
assert flask_nacos.__version__ == expected, (
    "version mismatch: %r != %r" % (flask_nacos.__version__, expected)
)
assert Path(flask_nacos.__file__).with_name("py.typed").is_file(), "py.typed missing"

app = Flask(__name__)
app.config.update(NACOS_ENABLED=False)
FlaskNacos(app)
assert "nacos" in app.extensions, "app.extensions['nacos'] missing"

print("[smoke] import + typing marker + init OK (version=%s)" % expected)
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


def _find_exactly_one(pattern: str, label: str) -> str:
    matches = sorted(glob.glob(str(DIST / pattern)))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected exactly one {label} ({pattern}) in dist/, found {len(matches)}"
        )
    return matches[0]


def _find_artifacts() -> List[Tuple[str, str]]:
    return [
        ("wheel", _find_exactly_one("*.whl", "wheel")),
        ("sdist", _find_exactly_one("*.tar.gz", "sdist")),
    ]


def _test_artifact(kind: str, artifact: str, expected: str, parent: Path) -> bool:
    venv_dir = parent / kind
    print(f"[smoke_test_package] creating {kind} test venv at {venv_dir}")
    venv.EnvBuilder(with_pip=True).create(str(venv_dir))
    py = _venv_python(venv_dir)

    install = subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "--no-cache-dir",
            artifact,
        ],
        check=False,
    )
    if install.returncode != 0:
        print(
            f"[smoke_test_package] FAILED - {kind} install failed",
            file=sys.stderr,
        )
        return False

    check = subprocess.run(
        [str(py), "-c", _CHECK_SCRIPT.format(expected=expected)], check=False
    )
    if check.returncode != 0:
        print(
            f"[smoke_test_package] FAILED - {kind} import/init check failed",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    try:
        artifacts = _find_artifacts()
        expected = _expected_version()
    except Exception as exc:
        print(f"[smoke_test_package] FAILED - {exc}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="flask-nacos-smoke-") as tmp:
        parent = Path(tmp)
        for kind, artifact in artifacts:
            if not _test_artifact(kind, artifact, expected, parent):
                return 1

    names = ", ".join(Path(path).name for _, path in artifacts)
    print(f"[smoke_test_package] OK - {names} install and import (v{expected})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
