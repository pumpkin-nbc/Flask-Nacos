"""Tests for default configuration loading and overrides."""

import pytest
from flask import Flask

from flask_nacos.config import DEFAULTS, load_config


def test_defaults_loaded():
    app = Flask(__name__)
    cfg = load_config(app)

    assert cfg["NACOS_ENABLED"] is True
    assert cfg["NACOS_SERVER_ADDR"] == "127.0.0.1:8848"
    assert cfg["NACOS_GROUP_NAME"] == "DEFAULT_GROUP"
    assert cfg["NACOS_FAIL_FAST"] is False
    assert cfg["NACOS_SERVICE_HEARTBEAT_INTERVAL"] == 5.0
    assert cfg["NACOS_LOG_ENABLED"] is False
    assert cfg["NACOS_LOG_DIR"] == "./logs"
    assert cfg["NACOS_LOG_FILENAME"] == "flask_nacos.log"
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


def test_legacy_log_file_setting_falls_back_to_log_directory():
    app = Flask(__name__)
    app.config["NACOS_LOG_FILE"] = "legacy-logs"

    cfg = load_config(app)

    assert cfg["NACOS_LOG_DIR"] == "legacy-logs"
    assert "NACOS_LOG_FILE" not in cfg


def test_canonical_log_directory_wins_over_legacy_setting():
    app = Flask(__name__)
    app.config.update(NACOS_LOG_DIR="canonical-logs", NACOS_LOG_FILE="legacy-logs")

    cfg = load_config(app)

    assert cfg["NACOS_LOG_DIR"] == "canonical-logs"


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


def test_heartbeat_interval_coercion():
    app = Flask(__name__)
    app.config.update(NACOS_SERVICE_HEARTBEAT_INTERVAL="2.5")
    cfg = load_config(app)

    assert cfg["NACOS_SERVICE_HEARTBEAT_INTERVAL"] == 2.5


def test_new_030_config_defaults():
    app = Flask(__name__)
    cfg = load_config(app)

    assert cfg["NACOS_RETRY_ENABLED"] is True
    assert cfg["NACOS_RETRY_TIMES"] == 3
    assert cfg["NACOS_RETRY_INTERVAL"] == 1.0
    assert cfg["NACOS_REQUEST_TIMEOUT"] == 5.0
    assert cfg["NACOS_HEALTH_CHECK_ENABLED"] is False
    assert cfg["NACOS_HEALTH_CHECK_PATH"] == "/health/nacos"
    assert cfg["NACOS_STATUS_ENABLED"] is True
    assert cfg["NACOS_AUTO_REGISTER_ON_INIT"] is True


def test_new_030_config_overrides():
    app = Flask(__name__)
    app.config.update(
        NACOS_RETRY_ENABLED="false",
        NACOS_RETRY_TIMES="5",
        NACOS_RETRY_INTERVAL="0.5",
        NACOS_REQUEST_TIMEOUT="10",
        NACOS_HEALTH_CHECK_ENABLED="true",
        NACOS_HEALTH_CHECK_PATH="/healthz",
        NACOS_AUTO_REGISTER_ON_INIT="false",
    )
    cfg = load_config(app)

    assert cfg["NACOS_RETRY_ENABLED"] is False
    assert cfg["NACOS_RETRY_TIMES"] == 5
    assert cfg["NACOS_RETRY_INTERVAL"] == 0.5
    assert cfg["NACOS_REQUEST_TIMEOUT"] == 10.0
    assert cfg["NACOS_HEALTH_CHECK_ENABLED"] is True
    assert cfg["NACOS_HEALTH_CHECK_PATH"] == "/healthz"
    assert cfg["NACOS_AUTO_REGISTER_ON_INIT"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("NACOS_RETRY_TIMES", True),
        ("NACOS_RETRY_TIMES", 1.5),
        ("NACOS_RETRY_TIMES", "invalid"),
        ("NACOS_RETRY_INTERVAL", True),
        ("NACOS_RETRY_INTERVAL", "invalid"),
        ("NACOS_REQUEST_TIMEOUT", True),
        ("NACOS_REQUEST_TIMEOUT", "invalid"),
    ],
)
def test_invalid_operational_numbers_are_preserved_for_validation(key, value):
    app = Flask(__name__)
    app.config[key] = value

    cfg = load_config(app)

    assert cfg[key] == value


def test_request_timeout_readable():
    app = Flask(__name__)
    app.config.update(NACOS_REQUEST_TIMEOUT=7.5)
    cfg = load_config(app)

    assert cfg["NACOS_REQUEST_TIMEOUT"] == 7.5


def test_new_040_config_defaults():
    app = Flask(__name__)
    cfg = load_config(app)

    assert cfg["NACOS_REGISTER_ONCE_PER_PROCESS"] is True
    assert cfg["NACOS_DEREGISTER_ON_EXIT"] is True
    assert cfg["NACOS_DISCOVERY_STRATEGY"] == "first"
    assert cfg["NACOS_DISCOVERY_CLUSTER"] is None
    assert cfg["NACOS_DISCOVERY_METADATA"] == {}
    assert cfg["NACOS_INSTANCE_NORMALIZE"] is True


def test_new_040_config_overrides():
    app = Flask(__name__)
    app.config.update(
        NACOS_REGISTER_ONCE_PER_PROCESS="false",
        NACOS_DEREGISTER_ON_EXIT="false",
        NACOS_DISCOVERY_STRATEGY="weight",
        NACOS_DISCOVERY_CLUSTER="CANARY",
        NACOS_DISCOVERY_METADATA={"version": "v1"},
        NACOS_INSTANCE_NORMALIZE="false",
    )
    cfg = load_config(app)

    assert cfg["NACOS_REGISTER_ONCE_PER_PROCESS"] is False
    assert cfg["NACOS_DEREGISTER_ON_EXIT"] is False
    assert cfg["NACOS_DISCOVERY_STRATEGY"] == "weight"
    assert cfg["NACOS_DISCOVERY_CLUSTER"] == "CANARY"
    assert cfg["NACOS_DISCOVERY_METADATA"] == {"version": "v1"}
    assert cfg["NACOS_INSTANCE_NORMALIZE"] is False


def test_mutable_metadata_is_isolated_between_apps():
    first = load_config(Flask("first"))
    second = load_config(Flask("second"))

    first["NACOS_SERVICE_METADATA"]["version"] = "v1"
    first["NACOS_DISCOVERY_METADATA"]["zone"] = "east"

    assert second["NACOS_SERVICE_METADATA"] == {}
    assert second["NACOS_DISCOVERY_METADATA"] == {}
    assert first["NACOS_SERVICE_METADATA"] is not second["NACOS_SERVICE_METADATA"]
    assert first["NACOS_DISCOVERY_METADATA"] is not second["NACOS_DISCOVERY_METADATA"]


def test_user_metadata_is_snapshotted():
    app = Flask(__name__)
    service_metadata = {"version": "v1"}
    discovery_metadata = {"zone": "east"}
    app.config.update(
        NACOS_SERVICE_METADATA=service_metadata,
        NACOS_DISCOVERY_METADATA=discovery_metadata,
    )

    cfg = load_config(app)
    service_metadata["version"] = "v2"
    discovery_metadata["zone"] = "west"

    assert cfg["NACOS_SERVICE_METADATA"] == {"version": "v1"}
    assert cfg["NACOS_DISCOVERY_METADATA"] == {"zone": "east"}
