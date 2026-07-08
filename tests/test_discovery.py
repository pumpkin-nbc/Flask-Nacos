"""Tests for service discovery."""

from flask_nacos import FlaskNacos


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
