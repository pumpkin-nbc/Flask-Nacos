"""Tests for default configuration loading and overrides."""

from flask import Flask

from flask_nacos.config import DEFAULTS, load_config


def test_defaults_loaded():
    app = Flask(__name__)
    cfg = load_config(app)

    assert cfg["NACOS_ENABLED"] is True
    assert cfg["NACOS_SERVER_ADDR"] == "127.0.0.1:8848"
    assert cfg["NACOS_GROUP_NAME"] == "DEFAULT_GROUP"
    assert cfg["NACOS_FAIL_FAST"] is False
    # Every default key should be present.
    for key in DEFAULTS:
        assert key in cfg


def test_user_overrides_defaults():
    app = Flask(__name__)
    app.config.update(
        NACOS_SERVER_ADDR="10.0.0.1:8848",
        NACOS_GROUP_NAME="MY_GROUP",
        NACOS_SERVICE_PORT="9000",
    )
    cfg = load_config(app)

    assert cfg["NACOS_SERVER_ADDR"] == "10.0.0.1:8848"
    assert cfg["NACOS_GROUP_NAME"] == "MY_GROUP"
    # String port coerced to int.
    assert cfg["NACOS_SERVICE_PORT"] == 9000


def test_bool_coercion_from_string():
    app = Flask(__name__)
    app.config.update(NACOS_ENABLED="false", NACOS_FAIL_FAST="true")
    cfg = load_config(app)

    assert cfg["NACOS_ENABLED"] is False
    assert cfg["NACOS_FAIL_FAST"] is True


def test_weight_coercion():
    app = Flask(__name__)
    app.config.update(NACOS_SERVICE_WEIGHT="2.5")
    cfg = load_config(app)

    assert cfg["NACOS_SERVICE_WEIGHT"] == 2.5
