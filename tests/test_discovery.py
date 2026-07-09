"""Tests for service discovery."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosValidationError


def test_list_instances(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service")
    assert len(instances) == 2
    assert instances[0]["ip"] == "127.0.0.1"
    fake_client.list_naming_instance.assert_called_once()
    _, kwargs = fake_client.list_naming_instance.call_args
    assert kwargs["healthy_only"] is True
    assert kwargs["group_name"] == "DEFAULT_GROUP"


def test_list_instances_custom_group(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    nacos.list_instances("user-service", group="G2", healthy_only=False)
    _, kwargs = fake_client.list_naming_instance.call_args
    assert kwargs["group_name"] == "G2"
    assert kwargs["healthy_only"] is False


def test_get_one_healthy_instance(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service")
    assert instance is not None
    assert instance["port"] == 8000


def test_get_one_healthy_instance_empty(make_app, patched_create_client, fake_client):
    fake_client.list_naming_instance.return_value = {"hosts": []}
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.get_one_healthy_instance("user-service") is None


def test_list_instances_healthy_only_flag(make_app, patched_create_client, fake_client):
    app = make_app()
    nacos = FlaskNacos(app)

    nacos.list_instances("user-service", healthy_only=True)
    _, kwargs = fake_client.list_naming_instance.call_args
    assert kwargs["healthy_only"] is True

    nacos.list_instances("user-service", healthy_only=False)
    _, kwargs = fake_client.list_naming_instance.call_args
    assert kwargs["healthy_only"] is False


def test_list_instances_empty_result_returns_empty_list(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = {"hosts": []}
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.list_instances("user-service") == []


def test_list_instances_empty_service_name_returns_empty_when_not_fail_fast(
    make_app, patched_create_client
):
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.list_instances("") == []


def test_list_instances_empty_service_name_raises_when_fail_fast(
    make_app, patched_create_client
):
    app = make_app({"NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosValidationError):
        nacos.list_instances("")
