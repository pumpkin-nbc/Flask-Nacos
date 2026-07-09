"""Tests for healthy-instance selection strategies."""

import pytest

import flask_nacos.discovery as discovery_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosDiscoveryError


def test_strategy_first(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service", strategy="first")
    assert instance["port"] == 8000


def test_strategy_random(make_app, patched_create_client, monkeypatch):
    monkeypatch.setattr(discovery_module.random, "choice", lambda seq: seq[-1])
    app = make_app()
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service", strategy="random")
    assert instance["port"] == 8001


def test_strategy_weight(make_app, patched_create_client, monkeypatch):
    captured = {}

    def _fake_choices(population, weights=None, k=1):
        captured["weights"] = weights
        return [population[1]]

    monkeypatch.setattr(discovery_module.random, "choices", _fake_choices)
    app = make_app()
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service", strategy="weight")
    assert instance["port"] == 8001
    assert captured["weights"] == [1.0, 1.0]


def test_strategy_weight_all_non_positive_degrades_to_first(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.return_value = {
        "hosts": [
            {"ip": "127.0.0.1", "port": 8000, "healthy": True, "weight": 0.0},
            {"ip": "127.0.0.1", "port": 8001, "healthy": True, "weight": 0.0},
        ]
    }
    app = make_app()
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service", strategy="weight")
    assert instance["port"] == 8000


def test_default_strategy_from_config(make_app, patched_create_client, monkeypatch):
    monkeypatch.setattr(discovery_module.random, "choice", lambda seq: seq[-1])
    app = make_app({"NACOS_DISCOVERY_STRATEGY": "random"})
    nacos = FlaskNacos(app)

    instance = nacos.get_one_healthy_instance("user-service")
    assert instance["port"] == 8001


def test_unsupported_strategy_returns_none_when_not_fail_fast(
    make_app, patched_create_client
):
    app = make_app({"NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.get_one_healthy_instance("user-service", strategy="bogus") is None


def test_unsupported_strategy_raises_when_fail_fast(make_app, patched_create_client):
    app = make_app({"NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosDiscoveryError):
        nacos.get_one_healthy_instance("user-service", strategy="bogus")


def test_no_healthy_instance_returns_none(make_app, patched_create_client, fake_client):
    fake_client.list_naming_instance.return_value = {"hosts": []}
    app = make_app()
    nacos = FlaskNacos(app)

    assert nacos.get_one_healthy_instance("user-service", strategy="weight") is None
