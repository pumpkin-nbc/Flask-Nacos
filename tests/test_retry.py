"""Tests for the retry mechanism."""

import pytest

import flask_nacos.retry as retry_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosConfigError


def test_register_retries_until_success(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = [RuntimeError("boom"), True]
    app = make_app({"NACOS_RETRY_ENABLED": True, "NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True
    assert fake_client.add_naming_instance.call_count == 2


def test_register_no_retry_when_disabled(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = RuntimeError("boom")
    app = make_app(
        {"NACOS_RETRY_ENABLED": False, "NACOS_RETRY_TIMES": 3, "NACOS_FAIL_FAST": False}
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is False
    assert fake_client.add_naming_instance.call_count == 1


def test_retry_times_controls_attempts(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = RuntimeError("boom")
    app = make_app(
        {"NACOS_RETRY_ENABLED": True, "NACOS_RETRY_TIMES": 4, "NACOS_FAIL_FAST": False}
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is False
    assert fake_client.add_naming_instance.call_count == 4


def test_retry_interval_is_read(make_app, patched_create_client):
    app = make_app({"NACOS_RETRY_INTERVAL": 2.5})
    nacos = FlaskNacos(app)
    assert nacos.config["NACOS_RETRY_INTERVAL"] == 2.5


def test_retry_interval_passed_to_sleep(monkeypatch, make_app, patched_create_client, fake_client):
    calls = []
    monkeypatch.setattr(retry_module, "_sleep", lambda seconds: calls.append(seconds))

    fake_client.add_naming_instance.side_effect = [RuntimeError("boom"), True]
    app = make_app(
        {"NACOS_RETRY_ENABLED": True, "NACOS_RETRY_TIMES": 3, "NACOS_RETRY_INTERVAL": 1.5}
    )
    nacos = FlaskNacos(app)
    nacos.register_instance()

    assert calls == [1.5]


def test_retry_final_failure_returns_default_when_not_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.list_naming_instance.side_effect = RuntimeError("boom")
    app = make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": False})
    nacos = FlaskNacos(app)

    assert nacos.list_instances("user-service") == []
    assert fake_client.list_naming_instance.call_count == 2


def test_retry_final_failure_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.get_config.side_effect = RuntimeError("boom")
    app = make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": True})
    nacos = FlaskNacos(app)

    with pytest.raises(NacosConfigError):
        nacos.get_config("application.yaml")
    assert fake_client.get_config.call_count == 2


def test_deregister_uses_retry(make_app, patched_create_client, fake_client):
    fake_client.remove_naming_instance.side_effect = [RuntimeError("boom"), True]
    app = make_app({"NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    assert nacos.deregister_instance() is True
    assert fake_client.remove_naming_instance.call_count == 2


def test_list_uses_retry(make_app, patched_create_client, fake_client):
    fake_client.list_naming_instance.side_effect = [
        RuntimeError("boom"),
        {"hosts": [{"ip": "127.0.0.1", "port": 9000, "healthy": True}]},
    ]
    app = make_app({"NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    result = nacos.list_instances("user-service")
    assert len(result) == 1
    assert fake_client.list_naming_instance.call_count == 2


def test_get_config_uses_retry(make_app, patched_create_client, fake_client):
    fake_client.get_config.side_effect = [RuntimeError("boom"), "content"]
    app = make_app({"NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    assert nacos.get_config("application.yaml") == "content"
    assert fake_client.get_config.call_count == 2
