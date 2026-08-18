"""Tests for lifecycle and non-lifecycle retry boundaries."""

import time

import pytest

import flask_nacos.retry as retry_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import NacosRegistrationError, NacosValidationError
from tests.helpers import wait_registered, wait_until


def test_register_worker_retries_until_success(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = [RuntimeError("boom"), True]
    app = make_app(
        {
            "NACOS_RETRY_ENABLED": True,
            "NACOS_RETRY_TIMES": 3,
            "NACOS_RETRY_INTERVAL": 0,
        }
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_registered(nacos, app)
    assert fake_client.add_naming_instance.call_count == 2


def test_register_worker_retries_sdk_false_and_reports_exhaustion(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.return_value = False
    app = make_app(
        {
            "NACOS_RETRY_TIMES": 2,
            "NACOS_RETRY_INTERVAL": 0,
            "NACOS_FAIL_FAST": True,
        }
    )
    nacos = FlaskNacos(app)

    assert nacos.register_instance(app) is None
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    status = nacos.get_status(app)
    assert status["registered"] is False
    assert status["target_registered"] is True
    assert status["last_error"] == NacosRegistrationError.__name__
    assert fake_client.add_naming_instance.call_count == 2


def test_register_worker_does_not_retry_when_disabled(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = RuntimeError("boom")
    app = make_app({"NACOS_RETRY_ENABLED": False, "NACOS_RETRY_TIMES": 9})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    assert fake_client.add_naming_instance.call_count == 1


def test_retry_wait_is_interrupted_by_deregister(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = RuntimeError("boom")
    app = make_app(
        {
            "NACOS_RETRY_ENABLED": True,
            "NACOS_RETRY_TIMES": 3,
            "NACOS_RETRY_INTERVAL": 30.0,
        }
    )
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_until(lambda: fake_client.add_naming_instance.call_count == 1)

    started = time.monotonic()
    assert nacos.deregister_instance(app) is True
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    assert time.monotonic() - started < 1.0
    assert nacos.get_status(app)["registered"] is False
    assert fake_client.add_naming_instance.call_count == 1


def test_explicit_register_retries_after_previous_exhaustion(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = [False, True]
    app = make_app({"NACOS_RETRY_ENABLED": False})
    nacos = FlaskNacos(app)

    nacos.register_instance(app)
    wait_until(lambda: nacos.get_status(app)["operation_running"] is False)
    first_generation = app.extensions["nacos"]["_runtime"].operation_generation
    nacos.register_instance(app)
    wait_registered(nacos, app)

    assert app.extensions["nacos"]["_runtime"].operation_generation == first_generation + 1
    assert fake_client.add_naming_instance.call_count == 2


@pytest.mark.parametrize("fail_fast", [False, True])
def test_sync_deregister_runtime_failure_returns_false_without_retry_or_raise(
    make_app, patched_create_client, fake_client, fail_fast
):
    app = make_app({"NACOS_FAIL_FAST": fail_fast, "NACOS_RETRY_TIMES": 5})
    nacos = FlaskNacos(app)
    nacos.register_instance(app)
    wait_registered(nacos, app)
    fake_client.remove_naming_instance.return_value = False

    assert nacos.deregister_instance(app) is False
    assert fake_client.remove_naming_instance.call_count == 1
    assert nacos.get_status(app)["registered"] is True
    assert nacos.get_status(app)["operation_running"] is False


def test_discovery_keeps_existing_general_retry(make_app, patched_create_client, fake_client):
    fake_client.list_naming_instance.side_effect = [
        RuntimeError("boom"),
        {"hosts": [{"ip": "127.0.0.1", "port": 9000, "healthy": True}]},
    ]
    app = make_app({"NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    with app.app_context():
        result = nacos.list_instances("user-service")
    assert len(result) == 1
    assert fake_client.list_naming_instance.call_count == 2


def test_config_center_keeps_existing_general_retry(make_app, patched_create_client, fake_client):
    fake_client.get_config.side_effect = [RuntimeError("boom"), "content"]
    app = make_app({"NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    with app.app_context():
        assert nacos.get_config("application.yaml") == "content"
    assert fake_client.get_config.call_count == 2


def test_general_retry_does_not_retry_validation_error(monkeypatch):
    calls = []
    sleeps = []
    monkeypatch.setattr(retry_module, "_sleep", lambda seconds: sleeps.append(seconds))

    def invalid_operation():
        calls.append(True)
        raise NacosValidationError("invalid input")

    with pytest.raises(NacosValidationError):
        retry_module.run_with_retry(
            invalid_operation,
            "invalid operation",
            {
                "NACOS_RETRY_ENABLED": True,
                "NACOS_RETRY_TIMES": 3,
                "NACOS_RETRY_INTERVAL": 1.0,
            },
        )

    assert len(calls) == 1
    assert sleeps == []
