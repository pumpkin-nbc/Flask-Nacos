"""No-network tests for the complete application-factory example."""

import importlib

import flask_nacos.extension as extension_module


def _load_example():
    return importlib.import_module("examples.complete_factory_app")


def test_complete_example_configuration_and_routes(
    monkeypatch, patched_create_client, fake_client
):
    monkeypatch.setenv("NACOS_SERVER_ADDR", "nacos.example.test:8848")
    monkeypatch.setenv("NACOS_NAMESPACE_ID", "example-namespace")
    monkeypatch.setenv("NACOS_USERNAME", "example-user")
    monkeypatch.setenv("NACOS_PASSWORD", "example-password")
    monkeypatch.setenv("NACOS_SERVICE_NAME", "orders-api")
    monkeypatch.setenv("NACOS_SERVICE_IP", "127.0.0.2")
    monkeypatch.setenv("NACOS_SERVICE_PORT", "5100")
    monkeypatch.setenv("NACOS_SERVICE_GROUP", "APP_GROUP")
    monkeypatch.setenv("NACOS_CONFIG_DATA_ID", "orders.properties")
    monkeypatch.setenv("NACOS_CONFIG_GROUP", "CONFIG_GROUP")
    monkeypatch.setenv("NACOS_REQUEST_TIMEOUT", "2.5")
    fake_client.get_config.return_value = "feature.enabled=true"

    example = _load_example()
    app = example.create_app()
    state = app.extensions["nacos"]
    cfg = state["config"]

    assert cfg["NACOS_SERVER_ADDR"] == "nacos.example.test:8848"
    assert cfg["NACOS_NAMESPACE_ID"] == "example-namespace"
    assert cfg["NACOS_SERVICE_NAME"] == "orders-api"
    assert cfg["NACOS_SERVICE_IP"] == "127.0.0.2"
    assert cfg["NACOS_SERVICE_PORT"] == 5100
    assert cfg["NACOS_GROUP_NAME"] == "APP_GROUP"
    assert cfg["NACOS_SERVICE_GROUP"] == "APP_GROUP"
    assert cfg["NACOS_REQUEST_TIMEOUT"] == 2.5
    assert cfg["NACOS_AUTO_REGISTER"] is True
    assert cfg["NACOS_AUTO_DEREGISTER"] is True
    assert cfg["NACOS_HEALTH_CHECK_ENABLED"] is True

    client = app.test_client()
    assert client.get("/").status_code == 200

    health = client.get("/health/nacos")
    assert health.status_code == 200
    assert health.get_json()["service_name"] == "orders-api"

    status = client.get("/api/nacos/status")
    assert status.status_code == 200
    assert status.get_json()["registered"] is True

    config_response = client.get("/api/nacos/config")
    assert config_response.status_code == 200
    assert config_response.get_json() == {
        "available": True,
        "content": "feature.enabled=true",
        "data_id": "orders.properties",
    }
    fake_client.get_config.assert_called_once_with(
        "orders.properties", "CONFIG_GROUP", timeout=2.5
    )

    instances = client.get(
        "/api/nacos/instances?service=users-api&cluster=CANARY"
    )
    assert instances.status_code == 200
    payload = instances.get_json()
    assert payload["available"] is True
    assert payload["service"] == "users-api"
    assert payload["cluster"] == "CANARY"
    assert payload["count"] == 1
    fake_client.list_naming_instance.assert_called_once_with(
        "users-api", group_name="APP_GROUP", healthy_only=True
    )


def test_complete_example_returns_safe_unavailable_responses(monkeypatch):
    def fail_to_create_client(config):
        raise RuntimeError("temporary connection failure with hidden credentials")

    monkeypatch.setattr(extension_module, "create_client", fail_to_create_client)
    monkeypatch.setenv("NACOS_USERNAME", "private-example-user")
    monkeypatch.setenv("NACOS_PASSWORD", "private-example-password")

    example = _load_example()
    app = example.create_app()
    client = app.test_client()

    health = client.get("/health/nacos")
    assert health.status_code == 200
    assert health.get_json()["status"] == "error"

    config_response = client.get("/api/nacos/config")
    assert config_response.status_code == 503
    instances_response = client.get("/api/nacos/instances")
    assert instances_response.status_code == 503

    combined = config_response.get_data(as_text=True) + instances_response.get_data(
        as_text=True
    )
    assert "private-example-user" not in combined
    assert "private-example-password" not in combined
