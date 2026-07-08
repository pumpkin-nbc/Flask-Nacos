"""Tests for the configuration center."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.config_center import load_config_to_flask


def test_get_config(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    content = nacos.get_config("application.yaml")
    assert content == "server:\n  port: 8000\n"
    fake_client.get_config.assert_called_once()
    args, _ = fake_client.get_config.call_args
    assert args[0] == "application.yaml"
    assert args[1] == "DEFAULT_GROUP"


def test_get_config_custom_group(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_CONFIG_GROUP": "CFG_GROUP"})
    nacos = FlaskNacos(app)

    nacos.get_config("application.yaml")
    args, _ = fake_client.get_config.call_args
    assert args[1] == "CFG_GROUP"


def test_get_config_explicit_group_wins(make_app, patched_create_client, fake_client):
    app = make_app({"NACOS_CONFIG_GROUP": "CFG_GROUP"})
    nacos = FlaskNacos(app)

    nacos.get_config("application.yaml", group="OVERRIDE")
    args, _ = fake_client.get_config.call_args
    assert args[1] == "OVERRIDE"


def test_load_config_to_flask_reserved():
    with pytest.raises(NotImplementedError):
        load_config_to_flask(None, None, {}, "application.yaml")
