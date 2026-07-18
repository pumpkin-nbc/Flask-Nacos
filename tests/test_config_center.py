"""Tests for the configuration center."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.config_center import load_config_to_flask
from flask_nacos.exceptions import NacosValidationError


def test_get_config(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    content = nacos.get_config("application.yaml")
    assert content == "server:\n  port: 8000\n"
    fake_client.get_config.assert_called_once()
    args, kwargs = fake_client.get_config.call_args
    assert args[0] == "application.yaml"
    assert args[1] == "DEFAULT_GROUP"
    assert kwargs["timeout"] == 5.0


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


def test_get_config_uses_default_data_id_and_timeout(
    make_app, patched_create_client, fake_client
):
    app = make_app(
        {"NACOS_CONFIG_DATA_ID": "defaults.yaml", "NACOS_REQUEST_TIMEOUT": 2.5}
    )
    nacos = FlaskNacos(app)

    assert nacos.get_config() == "server:\n  port: 8000\n"
    fake_client.get_config.assert_called_once_with(
        "defaults.yaml", "DEFAULT_GROUP", timeout=2.5
    )


def test_get_config_disabled_skips_sdk_even_without_client(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_ENABLED": False, "NACOS_CONFIG_ENABLED": False})
    nacos = FlaskNacos(app)

    assert nacos.get_config() is None
    fake_client.get_config.assert_not_called()


def test_missing_default_data_id_honors_fail_fast(
    make_app, patched_create_client, fake_client
):
    app = make_app({"NACOS_CONFIG_DATA_ID": None, "NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosValidationError):
        nacos.get_config()
    fake_client.get_config.assert_not_called()


@pytest.mark.parametrize(
    "timeout",
    [0, -1, True, float("nan"), float("inf"), "invalid"],
)
def test_invalid_request_timeout_does_not_call_sdk(
    make_app, patched_create_client, fake_client, timeout
):
    nacos = FlaskNacos(
        make_app({"NACOS_REQUEST_TIMEOUT": timeout, "NACOS_FAIL_FAST": False})
    )

    assert nacos.get_config("application.yaml") is None
    fake_client.get_config.assert_not_called()


def test_invalid_request_timeout_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app(
            {"NACOS_REQUEST_TIMEOUT": float("inf"), "NACOS_FAIL_FAST": True}
        )
    )

    with pytest.raises(NacosValidationError):
        nacos.get_config("application.yaml")
    fake_client.get_config.assert_not_called()


def test_request_timeout_is_ignored_when_config_center_disabled(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app(
            {
                "NACOS_CONFIG_ENABLED": False,
                "NACOS_REQUEST_TIMEOUT": float("nan"),
            }
        )
    )

    assert nacos.get_config("application.yaml") is None
    fake_client.get_config.assert_not_called()
