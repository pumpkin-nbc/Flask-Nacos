"""Packaging and public-surface guard tests."""

from pathlib import Path

import flask_nacos
from flask_nacos import FlaskNacos

ROOT = Path(__file__).resolve().parent.parent


def test_py_typed_marker_present():
    package_dir = Path(flask_nacos.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_version_is_100():
    assert flask_nacos.__version__ == "1.0.1"


def test_no_get_config_as_dict_on_public_surface():
    assert not hasattr(FlaskNacos, "get_config_as_dict")
    assert "get_config_as_dict" not in flask_nacos.__all__


def test_no_load_config_to_flask_on_extension():
    assert not hasattr(FlaskNacos, "load_config_to_flask")


def test_get_config_still_present():
    assert hasattr(FlaskNacos, "get_config")


def test_source_license_files_are_apache_2():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notice_text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "Copyright 2026 Pumpkin" in notice_text
    assert 'license = "Apache-2.0"' in pyproject_text
    assert 'license-files = ["LICENSE", "NOTICE"]' in pyproject_text
    assert "License ::" not in pyproject_text
