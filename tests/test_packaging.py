"""Packaging and public-surface guard tests."""

from pathlib import Path

import flask_nacos
from flask_nacos import FlaskNacos


def test_py_typed_marker_present():
    package_dir = Path(flask_nacos.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_version_is_080():
    assert flask_nacos.__version__ == "0.8.0"


def test_no_get_config_as_dict_on_public_surface():
    assert not hasattr(FlaskNacos, "get_config_as_dict")
    assert "get_config_as_dict" not in flask_nacos.__all__


def test_no_load_config_to_flask_on_extension():
    assert not hasattr(FlaskNacos, "load_config_to_flask")


def test_get_config_still_present():
    assert hasattr(FlaskNacos, "get_config")
