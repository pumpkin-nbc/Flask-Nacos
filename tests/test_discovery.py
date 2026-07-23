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


def test_list_instances_normalized_returns_standard_dicts(
    make_app, patched_create_client
):
    app = make_app({"NACOS_INSTANCE_NORMALIZE": True})
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service")
    assert len(instances) == 2
    for inst in instances:
        assert set(inst.keys()) == {
            "ip",
            "port",
            "service_name",
            "cluster_name",
            "weight",
            "healthy",
            "enabled",
            "ephemeral",
            "metadata",
        }


def test_list_instances_raw_when_normalize_disabled(
    make_app, patched_create_client
):
    app = make_app({"NACOS_INSTANCE_NORMALIZE": False})
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service")
    assert len(instances) == 2
    # Raw SDK dicts keep the original camelCase keys and no normalization.
    assert "clusterName" in instances[0]
    assert "cluster_name" not in instances[0]


def test_list_instances_filter_by_cluster(
    make_app, patched_create_client, fake_client
):
    app = make_app()
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service", cluster="CANARY")
    assert len(instances) == 1
    assert instances[0]["port"] == 8001
    assert instances[0]["cluster_name"] == "CANARY"
    _, kwargs = fake_client.list_naming_instance.call_args
    assert kwargs["clusters"] == "CANARY"


@pytest.mark.parametrize(
    "arguments",
    [
        {"service_name": None},
        {"service_name": "users", "group": 1},
        {"service_name": "users", "group": "   "},
        {"service_name": "users", "cluster": 1},
        {"service_name": "users", "healthy_only": "true"},
        {"service_name": "users", "metadata": []},
    ],
)
def test_invalid_discovery_parameters_never_call_sdk(
    make_app, patched_create_client, fake_client, arguments
):
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.list_instances(**arguments) == []
    fake_client.list_naming_instance.assert_not_called()


def test_list_instances_filter_by_metadata(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service", metadata={"version": "v1"})
    assert len(instances) == 1
    assert instances[0]["port"] == 8000
    assert instances[0]["metadata"]["version"] == "v1"


def test_list_instances_filter_empty_result(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service", metadata={"version": "nope"})
    assert instances == []


def test_list_instances_cluster_defaults_from_config(make_app, patched_create_client):
    app = make_app({"NACOS_DISCOVERY_CLUSTER": "CANARY"})
    nacos = FlaskNacos(app)

    instances = nacos.list_instances("user-service")
    assert len(instances) == 1
    assert instances[0]["port"] == 8001


def test_explicit_empty_metadata_disables_configured_filter(
    make_app, patched_create_client
):
    app = make_app({"NACOS_DISCOVERY_METADATA": {"version": "v1"}})
    nacos = FlaskNacos(app)

    configured = nacos.list_instances("user-service")
    unfiltered = nacos.list_instances("user-service", metadata={})

    assert [instance["port"] for instance in configured] == [8000]
    assert [instance["port"] for instance in unfiltered] == [8000, 8001]
