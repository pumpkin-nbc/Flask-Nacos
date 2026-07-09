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


def test_get_config_returns_raw_string_without_parsing(
    make_app, patched_create_client, fake_client
):
    raw = "server:\n  port: 8000\nname: demo\n"
    fake_client.get_config.return_value = raw
    app = make_app()
    nacos = FlaskNacos(app)

    content = nacos.get_config("application.yaml")
    # The exact raw string is returned; no YAML/JSON/dict parsing is performed.
    assert content == raw
    assert isinstance(content, str)


def test_get_config_does_not_parse_json(make_app, patched_create_client, fake_client):
    raw = '{"a": 1, "b": [1, 2, 3]}'
    fake_client.get_config.return_value = raw
    app = make_app()
    nacos = FlaskNacos(app)

    content = nacos.get_config("application.json")
    assert content == raw
    assert isinstance(content, str)
    assert not isinstance(content, dict)
