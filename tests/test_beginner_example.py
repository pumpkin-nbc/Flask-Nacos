"""No-network tests for the beginner Flask-Nacos example."""

import runpy
from pathlib import Path

import flask_nacos.extension as extension_module

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "beginner_app.py"


def _load_example():
    return runpy.run_path(str(EXAMPLE), run_name="flask_nacos_beginner_example")


def test_beginner_example_runs_without_nacos(monkeypatch):
    monkeypatch.delenv("NACOS_ENABLED", raising=False)

    def unexpected_client(config):
        raise AssertionError("disabled first run must not create a Nacos client")

    monkeypatch.setattr(extension_module, "create_client", unexpected_client)
    module = _load_example()
    app = module["app"]
    client = app.test_client()

    home = client.get("/")
    assert home.status_code == 200
    assert home.get_json()["nacos_enabled"] is False

    status = client.get("/nacos/status")
    assert status.status_code == 200
    assert status.get_json()["client_initialized"] is False

    health = client.get("/health/nacos")
    assert health.status_code == 200
    assert health.get_json()["status"] == "disabled"

    config = client.get("/nacos/config")
    assert config.status_code == 503
    assert config.get_json()["feature"] == "config"
    assert "NACOS_ENABLED=true" in config.get_json()["hint"]

    instances = client.get("/nacos/instances")
    assert instances.status_code == 503
    assert instances.get_json()["feature"] == "discovery"


def test_beginner_example_covers_registration_config_and_discovery(
    monkeypatch, patched_create_client, fake_client
):
    monkeypatch.setenv("NACOS_ENABLED", "true")
    fake_client.get_config.return_value = "greeting=hello-from-nacos"
    module = _load_example()
    app = module["app"]
    client = app.test_client()

    cfg = app.extensions["nacos"]["config"]
    assert cfg["NACOS_ENABLED"] is True
    assert cfg["NACOS_SERVICE_NAME"] == "flask-nacos-beginner"
    assert cfg["NACOS_SERVICE_PORT"] == 5000
    assert cfg["NACOS_CONFIG_DATA_ID"] == "flask-nacos-beginner.properties"
    fake_client.add_naming_instance.assert_called_once()

    status = client.get("/nacos/status").get_json()
    assert status["client_initialized"] is True
    assert status["registered"] is True

    health = client.get("/health/nacos")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    config = client.get("/nacos/config")
    assert config.status_code == 200
    assert config.get_json() == {
        "available": True,
        "content": "greeting=hello-from-nacos",
        "data_id": "flask-nacos-beginner.properties",
    }
    fake_client.get_config.assert_called_once_with(
        "flask-nacos-beginner.properties", "DEFAULT_GROUP", timeout=5.0
    )

    instances = client.get("/nacos/instances")
    assert instances.status_code == 200
    payload = instances.get_json()
    assert payload["service"] == "flask-nacos-beginner"
    assert payload["count"] == 2
    fake_client.list_naming_instance.assert_called_once_with(
        "flask-nacos-beginner", group_name="DEFAULT_GROUP", healthy_only=True
    )


def test_beginner_example_hides_client_failure_details(monkeypatch):
    monkeypatch.setenv("NACOS_ENABLED", "true")

    def fail_to_create_client(config):
        raise RuntimeError("temporary failure containing hidden-example-token")

    monkeypatch.setattr(extension_module, "create_client", fail_to_create_client)
    module = _load_example()
    client = module["app"].test_client()

    status = client.get("/nacos/status")
    assert status.status_code == 200
    assert status.get_json()["client_initialized"] is False

    responses = [client.get("/nacos/config"), client.get("/nacos/instances")]
    assert all(response.status_code == 503 for response in responses)
    combined = "".join(response.get_data(as_text=True) for response in responses)
    assert "hidden-example-token" not in combined
