"""Tests for discovery.extract_instances() and its use in list_instances."""

import pytest

from flask_nacos import FlaskNacos
from flask_nacos.discovery import extract_instances
from flask_nacos.exceptions import NacosDiscoveryError


class _ObjInstance:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_extract_from_plain_list():
    data = [{"ip": "10.0.0.1", "port": 8000}, {"ip": "10.0.0.2", "port": 8001}]
    assert extract_instances(data) is data


def test_extract_from_list_of_objects():
    objs = [_ObjInstance(ip="10.0.0.1", port=8000)]
    assert extract_instances(objs) == objs


def test_extract_from_hosts_dict():
    hosts = [{"ip": "10.0.0.1", "port": 8000}]
    assert extract_instances({"hosts": hosts}) == hosts


def test_extract_from_instances_dict():
    instances = [{"ip": "10.0.0.1", "port": 8000}]
    assert extract_instances({"instances": instances}) == instances


def test_extract_from_data_hosts():
    hosts = [{"ip": "10.0.0.1", "port": 8000}]
    assert extract_instances({"data": {"hosts": hosts}}) == hosts


def test_extract_from_data_instances():
    instances = [{"ip": "10.0.0.1", "port": 8000}]
    assert extract_instances({"data": {"instances": instances}}) == instances


def test_extract_from_data_list():
    instances = [{"ip": "10.0.0.1", "port": 8000}]
    assert extract_instances({"data": instances}) == instances


def test_extract_none_returns_empty():
    assert extract_instances(None) == []


def test_extract_empty_list_returns_empty():
    assert extract_instances([]) == []


def test_extract_empty_dict_returns_empty():
    assert extract_instances({}) == []


def test_extract_unrecognized_shape_raises():
    with pytest.raises(NacosDiscoveryError):
        extract_instances("not-a-valid-response")


def test_list_instances_handles_data_hosts(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = {
        "data": {
            "hosts": [
                {"ip": "127.0.0.1", "port": 8000, "healthy": True},
                {"ip": "127.0.0.1", "port": 8001, "healthy": True},
            ]
        }
    }
    app = make_app()
    nacos = FlaskNacos(app)

    result = nacos.list_instances("user-service")
    assert {r["port"] for r in result} == {8000, 8001}


def test_list_instances_unrecognized_shape_default_empty(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = "garbage"
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.list_instances("user-service") == []


def test_list_instances_unrecognized_shape_fail_fast_raises(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = "garbage"
    app = make_app({"NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosDiscoveryError):
        nacos.list_instances("user-service")
