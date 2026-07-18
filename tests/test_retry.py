"""Tests for the retry mechanism."""

import pytest

import flask_nacos.retry as retry_module
from flask_nacos import FlaskNacos
from flask_nacos.exceptions import (
    NacosConfigError,
    NacosDeregistrationError,
    NacosRegistrationError,
    NacosValidationError,
)


def test_register_retries_until_success(make_app, patched_create_client, fake_client):
    fake_client.add_naming_instance.side_effect = [RuntimeError("boom"), True]
    app = make_app({"NACOS_RETRY_ENABLED": True, "NACOS_RETRY_TIMES": 3})
    nacos = FlaskNacos(app)

    assert nacos.register_instance() is True
    assert fake_client.add_naming_instance.call_count == 2


def test_register_retries_sdk_false_until_success(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.side_effect = [False, True]
    nacos = FlaskNacos(make_app({"NACOS_RETRY_TIMES": 3}))

    assert nacos.register_instance() is True
    assert nacos.get_status()["registered"] is True
    assert fake_client.add_naming_instance.call_count == 2


def test_register_sdk_false_does_not_update_state(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.return_value = False
    nacos = FlaskNacos(
        make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": False})
    )

    assert nacos.register_instance() is False
    assert nacos.get_status()["registered"] is False
    assert fake_client.add_naming_instance.call_count == 2


def test_register_sdk_false_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    fake_client.add_naming_instance.return_value = False
    nacos = FlaskNacos(
        make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": True})
    )

    with pytest.raises(NacosRegistrationError):
        nacos.register_instance()
    assert nacos.get_status()["registered"] is False


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


def test_deregister_retries_sdk_false_until_success(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(make_app({"NACOS_RETRY_TIMES": 3}))
    nacos.register_instance()
    fake_client.remove_naming_instance.side_effect = [False, True]

    assert nacos.deregister_instance() is True
    assert nacos.get_status()["registered"] is False
    assert fake_client.remove_naming_instance.call_count == 2


def test_deregister_sdk_false_keeps_registered_state(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": False})
    )
    nacos.register_instance()
    fake_client.remove_naming_instance.return_value = False

    assert nacos.deregister_instance() is False
    assert nacos.get_status()["registered"] is True
    assert fake_client.remove_naming_instance.call_count == 2


def test_deregister_sdk_false_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app({"NACOS_RETRY_TIMES": 2, "NACOS_FAIL_FAST": True})
    )
    nacos.register_instance()
    fake_client.remove_naming_instance.return_value = False

    with pytest.raises(NacosDeregistrationError):
        nacos.deregister_instance()
    assert nacos.get_status()["registered"] is True


@pytest.mark.parametrize(
    "overrides",
    [
        {"NACOS_RETRY_TIMES": 0},
        {"NACOS_RETRY_TIMES": -1},
        {"NACOS_RETRY_TIMES": True},
        {"NACOS_RETRY_TIMES": 1.5},
        {"NACOS_RETRY_TIMES": float("nan")},
        {"NACOS_RETRY_TIMES": float("inf")},
        {"NACOS_RETRY_TIMES": "invalid"},
        {"NACOS_RETRY_INTERVAL": -1},
        {"NACOS_RETRY_INTERVAL": True},
        {"NACOS_RETRY_INTERVAL": float("nan")},
        {"NACOS_RETRY_INTERVAL": float("inf")},
        {"NACOS_RETRY_INTERVAL": "invalid"},
    ],
)
def test_invalid_retry_config_does_not_call_sdk(
    make_app, patched_create_client, fake_client, overrides
):
    nacos = FlaskNacos(make_app({**overrides, "NACOS_FAIL_FAST": False}))

    assert nacos.register_instance() is False
    fake_client.add_naming_instance.assert_not_called()


def test_invalid_retry_config_raises_when_fail_fast(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app({"NACOS_RETRY_TIMES": 1.5, "NACOS_FAIL_FAST": True})
    )

    with pytest.raises(NacosValidationError):
        nacos.register_instance()
    fake_client.add_naming_instance.assert_not_called()


def test_retry_numbers_are_ignored_when_retry_disabled(
    make_app, patched_create_client, fake_client
):
    nacos = FlaskNacos(
        make_app(
            {
                "NACOS_RETRY_ENABLED": False,
                "NACOS_RETRY_TIMES": 0,
                "NACOS_RETRY_INTERVAL": float("nan"),
            }
        )
    )

    assert nacos.register_instance() is True
    fake_client.add_naming_instance.assert_called_once()


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


def test_validation_error_is_not_retried(monkeypatch):
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
