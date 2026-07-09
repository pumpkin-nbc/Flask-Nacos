"""Tests for get_status() runtime inspection."""

from flask_nacos import FlaskNacos


def test_get_status_fields(make_app, patched_create_client):
    app = make_app({"NACOS_SERVICE_NAME": "fund-service", "NACOS_SERVICE_PORT": 5000})
    nacos = FlaskNacos(app)

    status = nacos.get_status()
    assert status["nacos_enabled"] is True
    assert status["client_initialized"] is True
    assert status["service_name"] == "fund-service"
    assert status["service_ip"] == "127.0.0.1"
    assert status["service_port"] == 5000
    assert status["server_addr"] == "127.0.0.1:8848"
    assert status["namespace_id"] == ""
    assert "registered" in status


def test_get_status_registered_flag(make_app, patched_create_client):
    app = make_app({"NACOS_AUTO_REGISTER": True})
    nacos = FlaskNacos(app)
    assert nacos.get_status()["registered"] is True


def test_get_status_process_and_discovery_fields(make_app, patched_create_client):
    import flask_nacos.lifecycle as lifecycle_module

    app = make_app(
        {
            "NACOS_AUTO_REGISTER": True,
            "NACOS_DISCOVERY_STRATEGY": "weight",
            "NACOS_HEALTH_CHECK_ENABLED": True,
        }
    )
    nacos = FlaskNacos(app)

    status = nacos.get_status()
    assert status["current_pid"] == lifecycle_module.current_pid()
    assert status["registered_pid"] == lifecycle_module.current_pid()
    assert status["register_once_per_process"] is True
    assert status["deregister_on_exit"] is True
    assert status["discovery_strategy"] == "weight"
    assert status["instance_normalize"] is True
    assert status["health_check_enabled"] is True
    assert status["health_check_path"] == "/health/nacos"


def test_get_status_registered_pid_none_before_register(make_app, patched_create_client):
    app = make_app({"NACOS_AUTO_REGISTER": False})
    nacos = FlaskNacos(app)
    assert nacos.get_status()["registered_pid"] is None


def test_get_status_disabled(make_app, patched_create_client):
    app = make_app({"NACOS_ENABLED": False})
    nacos = FlaskNacos(app)

    status = nacos.get_status()
    assert status["nacos_enabled"] is False
    assert status["client_initialized"] is False
    assert status["registered"] is False


def test_get_status_excludes_secrets(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_PASSWORD": "super-secret-password",
            "NACOS_ACCESS_KEY": "AK-1234567890",
            "NACOS_SECRET_KEY": "SK-abcdefghij",
        }
    )
    nacos = FlaskNacos(app)

    status = nacos.get_status()
    keys = set(status.keys())
    assert "NACOS_PASSWORD" not in keys
    assert "NACOS_ACCESS_KEY" not in keys
    assert "NACOS_SECRET_KEY" not in keys

    values = "".join(str(v) for v in status.values())
    assert "super-secret-password" not in values
    assert "AK-1234567890" not in values
    assert "SK-abcdefghij" not in values
