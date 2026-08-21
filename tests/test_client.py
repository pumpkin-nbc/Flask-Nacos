"""Tests for isolated Nacos SDK client construction."""

import logging
import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import flask_nacos.client as client_module
from flask_nacos import FlaskNacos
from flask_nacos.client import create_client
from flask_nacos.exceptions import NacosClientError, NacosConfigError


def _config(**overrides):
    config = {
        "NACOS_SERVER_ADDR": "nacos.example:8848",
        "NACOS_NAMESPACE_ID": "tenant-a",
        "NACOS_USERNAME": None,
        "NACOS_PASSWORD": None,
        "NACOS_ACCESS_KEY": None,
        "NACOS_SECRET_KEY": None,
    }
    config.update(overrides)
    return config


def test_create_client_forwards_username_and_password(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    client = create_client(
        _config(
            NACOS_USERNAME="user",
            NACOS_PASSWORD="password",
        )
    )

    assert client is constructor.return_value
    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
        username="user",
        password="password",
    )


def test_create_client_forwards_access_key_authentication(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    client = create_client(
        _config(
            NACOS_ACCESS_KEY="access",
            NACOS_SECRET_KEY="secret",
        )
    )

    assert client is constructor.return_value
    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
        ak="access",
        sk="secret",
    )


def test_create_client_omits_empty_authentication(monkeypatch):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    create_client(_config(NACOS_NAMESPACE_ID=""))

    constructor.assert_called_once_with(
        "nacos.example:8848", namespace="", logDir=tempfile.gettempdir()
    )


def test_create_client_uses_configured_log_directory(monkeypatch, tmp_path):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))
    log_directory = tmp_path / "logs"

    create_client(_config(NACOS_LOG_ENABLED=True, NACOS_LOG_PATH=str(log_directory)))

    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=os.path.abspath(str(log_directory)),
    )


def test_create_client_does_not_pass_an_existing_file_as_log_directory(monkeypatch, tmp_path):
    constructor = MagicMock(return_value=object())
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))
    legacy_file = tmp_path / "logs"
    legacy_file.write_text("legacy", encoding="utf-8")

    create_client(_config(NACOS_LOG_ENABLED=True, NACOS_LOG_PATH=str(legacy_file)))

    constructor.assert_called_once_with(
        "nacos.example:8848",
        namespace="tenant-a",
        logDir=tempfile.gettempdir(),
    )


def test_create_client_wraps_constructor_failure(monkeypatch):
    constructor = MagicMock(side_effect=RuntimeError("invalid SDK setup"))
    monkeypatch.setitem(sys.modules, "nacos", SimpleNamespace(NacosClient=constructor))

    with pytest.raises(NacosClientError) as exc_info:
        create_client(_config())

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_create_client_wraps_missing_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "nacos", None)

    with pytest.raises(NacosClientError) as exc_info:
        create_client(_config())

    assert isinstance(exc_info.value.__cause__, ImportError)


def test_real_sdk_constructor_creates_no_home_or_temporary_log(monkeypatch, tmp_path):
    pytest.importorskip("nacos")
    fake_home = tmp_path / "home"
    sdk_temp = tmp_path / "temp"
    fake_home.mkdir()
    sdk_temp.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(sdk_temp))

    client = create_client(_config(NACOS_SERVER_ADDR="127.0.0.1:8848"))

    assert client is not None
    assert not (fake_home / "logs" / "nacos").exists()
    assert not (sdk_temp / "nacos-client-python.log").exists()


def test_real_sdk_does_not_create_configured_directory_when_logging_disabled(monkeypatch, tmp_path):
    pytest.importorskip("nacos")
    configured_directory = tmp_path / "disabled-logs"
    sdk_temp = tmp_path / "temp"
    sdk_temp.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(sdk_temp))

    client = create_client(
        _config(
            NACOS_SERVER_ADDR="127.0.0.1:8848",
            NACOS_LOG_ENABLED=False,
            NACOS_LOG_PATH=str(configured_directory),
        )
    )

    assert client is not None
    assert not configured_directory.exists()
    assert not (sdk_temp / "nacos-client-python.log").exists()


def test_heartbeat_wrapper_logs_success_and_preserves_result(monkeypatch):
    sdk_client = SimpleNamespace()
    sdk_client.send_heartbeat = MagicMock(return_value={"clientBeatInterval": 5000})
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)

    client_module._install_heartbeat_logging(sdk_client)
    result = sdk_client.send_heartbeat(
        "orders",
        "10.0.0.8",
        8080,
        "BLUE",
        1.0,
        {"zone": "a"},
        True,
        "PROD",
    )

    assert result == {"clientBeatInterval": 5000}
    safe_logger.debug.assert_called_once_with(
        "Nacos heartbeat succeeded "
        "(service=%s, ip=%s, port=%s, group=%s, cluster=%s)",
        "orders",
        "10.0.0.8",
        8080,
        "PROD",
        "BLUE",
    )
    safe_logger.info.assert_not_called()
    safe_logger.warning.assert_not_called()


def test_heartbeat_wrapper_logs_sanitized_failure_and_reraises(monkeypatch):
    credential = "must-not-appear-in-heartbeat-log"

    def fail_heartbeat(*args, **kwargs):
        raise RuntimeError(credential)

    sdk_client = SimpleNamespace(send_heartbeat=fail_heartbeat)
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    with pytest.raises(RuntimeError, match=credential):
        sdk_client.send_heartbeat(
            service_name="orders",
            ip="10.0.0.8",
            port=8080,
            group_name="PROD",
        )

    safe_logger.warning.assert_called_once_with(
        "Nacos heartbeat failed "
        "(service=%s, ip=%s, port=%s, group=%s, cluster=%s, error_type=%s)",
        "orders",
        "10.0.0.8",
        8080,
        "PROD",
        "<default>",
        "RuntimeError",
    )
    assert credential not in str(safe_logger.mock_calls)


def test_heartbeat_wrapper_is_installed_only_once(monkeypatch):
    sdk_client = SimpleNamespace(send_heartbeat=MagicMock(return_value={}))
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)

    client_module._install_heartbeat_logging(sdk_client)
    wrapped = sdk_client.send_heartbeat
    client_module._install_heartbeat_logging(sdk_client)

    assert sdk_client.send_heartbeat is wrapped
    sdk_client.send_heartbeat("orders", "127.0.0.1", 8080)
    safe_logger.debug.assert_called_once()
    safe_logger.info.assert_not_called()


def test_heartbeat_identity_positional_and_keyword_calls_match():
    positional = client_module._extract_heartbeat_identity(
        ("orders", "10.0.0.8", 8080, "BLUE", 1.0, {"zone": "a"}, True, "PROD"),
        {},
    )
    keyword = client_module._extract_heartbeat_identity(
        (),
        {
            "service_name": "orders",
            "ip": "10.0.0.8",
            "port": 8080,
            "cluster_name": "BLUE",
            "weight": 1.0,
            "metadata": {"zone": "a"},
            "ephemeral": True,
            "group_name": "PROD",
        },
    )

    assert positional == keyword == ("orders", "PROD", "BLUE", "10.0.0.8", 8080)


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((), {}),
        (("orders", "10.0.0.8"), {}),
        (("orders", "10.0.0.8", 8080), {"service_name": "duplicate"}),
        (("orders", "10.0.0.8", 8080, None, 1.0, None, True, "PROD", "extra"), {}),
        (("orders", "10.0.0.8", 8080), {"unknown": True}),
        (("", "10.0.0.8", 8080), {}),
        (("orders", "", 8080), {}),
        (("orders", "10.0.0.8", True), {}),
        (("orders", "10.0.0.8", 70000), {}),
        (("orders", "10.0.0.8", 8080), {"group_name": None}),
    ],
)
def test_heartbeat_identity_rejects_unknown_or_incomplete_layout(args, kwargs):
    assert client_module._extract_heartbeat_identity(args, kwargs) is None


def test_nonstandard_heartbeat_identity_is_stateless_and_does_not_collide(monkeypatch):
    class HostileIdentity:
        def __str__(self):
            raise AssertionError("identity must not be stringified")

        def __repr__(self):
            raise AssertionError("identity must not be represented")

        def __hash__(self):
            raise AssertionError("identity must not be hashed")

    first = HostileIdentity()
    second = HostileIdentity()
    outcomes = [RuntimeError("first-secret"), {"ok": True}, RuntimeError("second-secret")]

    def send_heartbeat(*_args, **_kwargs):
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    sdk_client = SimpleNamespace(send_heartbeat=send_heartbeat)
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    with pytest.raises(RuntimeError, match="first-secret"):
        sdk_client.send_heartbeat(first, "10.0.0.8", 8080)
    assert sdk_client.send_heartbeat(second, "10.0.0.9", 8081) == {"ok": True}
    with pytest.raises(RuntimeError, match="second-secret"):
        sdk_client.send_heartbeat(second, "10.0.0.9", 8081)

    assert safe_logger.warning.call_count == 2
    assert safe_logger.info.call_count == 0
    assert safe_logger.debug.call_count == 1
    assert all("<unknown>" in str(item) for item in safe_logger.mock_calls)
    assert "first-secret" not in str(safe_logger.mock_calls)
    assert "second-secret" not in str(safe_logger.mock_calls)


def test_heartbeat_failure_states_are_isolated_by_identity(monkeypatch):
    failures = {
        "orders-a": RuntimeError("private-a"),
    }

    def send_heartbeat(service_name, *_args, **_kwargs):
        failure = failures.get(service_name)
        if failure is not None:
            raise failure
        return {"ok": service_name}

    now = iter(float(value) for value in range(20))
    sdk_client = SimpleNamespace(send_heartbeat=send_heartbeat)
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(now))
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    with pytest.raises(RuntimeError):
        sdk_client.send_heartbeat("orders-a", "10.0.0.8", 8080, "BLUE")
    assert sdk_client.send_heartbeat("orders-b", "10.0.0.9", 8081, "GREEN") == {
        "ok": "orders-b"
    }

    failures["orders-b"] = ValueError("private-b")
    with pytest.raises(ValueError):
        sdk_client.send_heartbeat("orders-b", "10.0.0.9", 8081, "GREEN")

    failures.pop("orders-a")
    assert sdk_client.send_heartbeat("orders-a", "10.0.0.8", 8080, "BLUE") == {
        "ok": "orders-a"
    }
    with pytest.raises(ValueError):
        sdk_client.send_heartbeat("orders-b", "10.0.0.9", 8081, "GREEN")

    failures.pop("orders-b")
    assert sdk_client.send_heartbeat("orders-b", "10.0.0.9", 8081, "GREEN") == {
        "ok": "orders-b"
    }
    assert sdk_client.send_heartbeat("orders-b", "10.0.0.9", 8081, "GREEN") == {
        "ok": "orders-b"
    }

    assert safe_logger.warning.call_count == 2
    assert safe_logger.info.call_count == 2
    assert safe_logger.debug.call_count == 3
    assert safe_logger.info.call_args_list[0].args[-5:] == (
        "orders-a",
        "10.0.0.8",
        8080,
        "DEFAULT_GROUP",
        "BLUE",
    )
    assert safe_logger.info.call_args_list[1].args[-5:] == (
        "orders-b",
        "10.0.0.9",
        8081,
        "DEFAULT_GROUP",
        "GREEN",
    )


def test_heartbeat_failure_state_is_private_to_each_client(monkeypatch):
    first_fails = [True]

    def first_heartbeat(*_args, **_kwargs):
        if first_fails[0]:
            raise RuntimeError("private")
        return "first-ok"

    first_client = SimpleNamespace(send_heartbeat=first_heartbeat)
    second_client = SimpleNamespace(send_heartbeat=lambda *_a, **_k: "second-ok")
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(first_client)
    client_module._install_heartbeat_logging(second_client)
    args = ("orders", "10.0.0.8", 8080)

    with pytest.raises(RuntimeError):
        first_client.send_heartbeat(*args)
    assert second_client.send_heartbeat(*args) == "second-ok"
    assert safe_logger.info.call_count == 0

    first_fails[0] = False
    assert first_client.send_heartbeat(*args) == "first-ok"
    assert safe_logger.info.call_count == 1


def test_heartbeat_same_failure_is_throttled_and_type_change_warns(monkeypatch):
    sdk_client = SimpleNamespace()
    sdk_client.send_heartbeat = MagicMock(
        side_effect=[
            RuntimeError("private-1"),
            RuntimeError("private-2"),
            ValueError("private-3"),
            ValueError("private-4"),
            {"ok": True},
            {"ok": True},
        ]
    )
    safe_logger = MagicMock()
    now = iter([-1.0, 0.0, 9.0, 10.0, 19.0, 20.0, 80.0, 81.0, 82.0, 83.0,
                84.0, 85.0])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(now))
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)
    args = ("orders", "10.0.0.8", 8080)

    for exc_type in (RuntimeError, RuntimeError, ValueError, ValueError):
        with pytest.raises(exc_type):
            sdk_client.send_heartbeat(*args)
    assert sdk_client.send_heartbeat(*args) == {"ok": True}
    assert sdk_client.send_heartbeat(*args) == {"ok": True}

    assert safe_logger.warning.call_count == 3
    assert safe_logger.info.call_count == 1
    assert safe_logger.debug.call_count == 2
    safe_logger.info.assert_called_once_with(
        "Nacos heartbeat recovered "
        "(service=%s, ip=%s, port=%s, group=%s, cluster=%s)",
        "orders",
        "10.0.0.8",
        8080,
        "DEFAULT_GROUP",
        "<default>",
    )


def test_heartbeat_recovery_state_is_deleted():
    identity = ("orders", "DEFAULT_GROUP", None, "10.0.0.8", 8080)
    failure_type = ("builtins", "RuntimeError")
    failure_states = {}

    assert (
        client_module._heartbeat_failure_action(
            failure_states, identity, failure_type, 0.0
        )
        == "warning"
    )
    assert identity in failure_states
    assert client_module._heartbeat_success_action(failure_states, identity) == "info"
    assert identity not in failure_states
    assert client_module._heartbeat_success_action(failure_states, identity) == "debug"


def test_heartbeat_concurrent_recovery_emits_one_info_per_identity(monkeypatch):
    failing = {"orders-a", "orders-b"}
    state_guard = threading.Lock()

    def send_heartbeat(service_name, *_args, **_kwargs):
        with state_guard:
            should_fail = service_name in failing
        if should_fail:
            raise RuntimeError("private")
        return True

    sdk_client = SimpleNamespace(send_heartbeat=send_heartbeat)
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    for service, port in (("orders-a", 8080), ("orders-b", 8081)):
        with pytest.raises(RuntimeError):
            sdk_client.send_heartbeat(service, "10.0.0.8", port)
    with state_guard:
        failing.clear()

    calls = [
        ("orders-a" if index % 2 == 0 else "orders-b", 8080 if index % 2 == 0 else 8081)
        for index in range(40)
    ]
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(
            executor.map(
                lambda item: sdk_client.send_heartbeat(item[0], "10.0.0.8", item[1]),
                calls,
            )
        )

    assert results == [True] * 40
    assert safe_logger.info.call_count == 2
    recovered_services = {item.args[-5] for item in safe_logger.info.call_args_list}
    assert recovered_services == {"orders-a", "orders-b"}


def test_heartbeat_sdk_and_logger_calls_run_outside_state_lock(monkeypatch):
    class TrackingLock:
        def __init__(self):
            self._lock = threading.Lock()

        def __enter__(self):
            self._lock.acquire()
            return self

        def __exit__(self, *_args):
            self._lock.release()

        def locked(self):
            return self._lock.locked()

    tracking_lock = TrackingLock()

    outcomes = [RuntimeError("private"), True]

    def send_heartbeat(*_args, **_kwargs):
        assert tracking_lock.locked() is False
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    safe_logger = MagicMock()
    def assert_unlocked(*_args, **_kwargs):
        if tracking_lock.locked():
            pytest.fail("logger called while state lock held")

    safe_logger.warning.side_effect = assert_unlocked
    safe_logger.info.side_effect = assert_unlocked
    sdk_client = SimpleNamespace(send_heartbeat=send_heartbeat)
    monkeypatch.setattr(client_module, "Lock", lambda: tracking_lock)
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    with pytest.raises(RuntimeError):
        sdk_client.send_heartbeat("orders", "10.0.0.8", 8080)
    assert sdk_client.send_heartbeat("orders", "10.0.0.8", 8080) is True
    safe_logger.warning.assert_called_once()
    safe_logger.info.assert_called_once()


def test_heartbeat_observer_binding_reuses_one_wrapper_and_does_not_accumulate(
    monkeypatch,
):
    original = MagicMock(return_value={"clientBeatInterval": 5000})
    sdk_client = SimpleNamespace(send_heartbeat=original)
    safe_logger = MagicMock()
    first_events = []
    second_events = []
    monkeypatch.setattr(client_module, "logger", safe_logger)

    client_module._install_heartbeat_logging(sdk_client)
    wrapper = sdk_client.send_heartbeat
    assert client_module._set_heartbeat_observer(
        sdk_client, lambda *event: first_events.append(event)
    )
    assert client_module._set_heartbeat_observer(
        sdk_client, lambda *event: second_events.append(event)
    )
    client_module._install_heartbeat_logging(sdk_client)

    assert sdk_client.send_heartbeat is wrapper
    result = sdk_client.send_heartbeat("orders", "10.0.0.8", 8080)

    assert result == {"clientBeatInterval": 5000}
    original.assert_called_once_with("orders", "10.0.0.8", 8080)
    assert first_events == []
    assert len(second_events) == 1
    assert second_events[0][0] == (
        "orders",
        "DEFAULT_GROUP",
        None,
        "10.0.0.8",
        8080,
    )
    assert second_events[0][1] is True
    safe_logger.debug.assert_called_once()


def test_heartbeat_observer_failure_does_not_change_sdk_or_logging(monkeypatch):
    original = MagicMock(return_value="sdk-result")
    sdk_client = SimpleNamespace(send_heartbeat=original)
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)

    def broken_observer(*_event):
        raise RuntimeError("observer-private")

    assert client_module._set_heartbeat_observer(sdk_client, broken_observer)

    assert sdk_client.send_heartbeat("orders", "10.0.0.8", 8080) == "sdk-result"
    original.assert_called_once()
    safe_logger.debug.assert_called_once()
    assert "observer-private" not in str(safe_logger.mock_calls)


def test_heartbeat_clock_and_success_log_failures_preserve_sdk_result(monkeypatch):
    original = MagicMock(return_value="sdk-result")
    sdk_client = SimpleNamespace(send_heartbeat=original)
    observer = MagicMock()
    safe_logger = MagicMock()
    safe_logger.debug.side_effect = RuntimeError("logger-private")
    monkeypatch.setattr(client_module, "logger", safe_logger)
    monkeypatch.setattr(
        client_module.time,
        "monotonic",
        MagicMock(side_effect=RuntimeError("clock-private")),
    )
    monkeypatch.setattr(
        client_module.time,
        "time",
        MagicMock(side_effect=RuntimeError("wall-clock-private")),
    )
    assert client_module._set_heartbeat_observer(sdk_client, observer)

    assert sdk_client.send_heartbeat("orders", "127.0.0.1", 8080) == "sdk-result"
    original.assert_called_once()
    observer.assert_not_called()
    safe_logger.debug.assert_called_once()


def test_heartbeat_failure_log_error_preserves_original_sdk_exception(monkeypatch):
    failure = RuntimeError("sdk-original")
    sdk_client = SimpleNamespace(send_heartbeat=MagicMock(side_effect=failure))
    safe_logger = MagicMock()
    safe_logger.warning.side_effect = ValueError("logger-private")
    monkeypatch.setattr(client_module, "logger", safe_logger)
    client_module._install_heartbeat_logging(sdk_client)

    with pytest.raises(RuntimeError) as raised:
        sdk_client.send_heartbeat("orders", "127.0.0.1", 8080)

    assert raised.value is failure
    safe_logger.warning.assert_called_once()


def test_heartbeat_instrumentation_install_failure_keeps_sdk_client_usable(
    monkeypatch,
):
    class ReadOnlyHeartbeatClient:
        __slots__ = ()

        def send_heartbeat(self, *_args, **_kwargs):
            return "original-result"

    sdk_client = ReadOnlyHeartbeatClient()
    safe_logger = MagicMock()
    monkeypatch.setattr(client_module, "logger", safe_logger)

    assert client_module._install_heartbeat_instrumentation(sdk_client) is None
    assert sdk_client.send_heartbeat("orders", "127.0.0.1", 8080) == "original-result"
    safe_logger.warning.assert_called_once_with(
        "Nacos heartbeat instrumentation is unavailable for this SDK client"
    )


@pytest.mark.parametrize(
    "auth_config",
    [
        {"NACOS_USERNAME": "user"},
        {"NACOS_PASSWORD": "password"},
        {"NACOS_ACCESS_KEY": "access"},
        {"NACOS_SECRET_KEY": "secret"},
        {
            "NACOS_USERNAME": "user",
            "NACOS_PASSWORD": "password",
            "NACOS_ACCESS_KEY": "access",
            "NACOS_SECRET_KEY": "secret",
        },
        {"NACOS_USERNAME": 123, "NACOS_PASSWORD": "password"},
    ],
)
def test_invalid_authentication_fails_before_client_creation(
    make_app, patched_create_client, auth_config
):
    app = make_app({**auth_config, "NACOS_FAIL_FAST": True})

    with pytest.raises(NacosConfigError):
        FlaskNacos(app)

    assert patched_create_client["count"] == 0
    assert "nacos" not in app.extensions


def test_invalid_authentication_is_safe_when_not_fail_fast(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_USERNAME": "user",
            "NACOS_PASSWORD": "password",
            "NACOS_ACCESS_KEY": "access",
            "NACOS_SECRET_KEY": "secret",
            "NACOS_FAIL_FAST": False,
        }
    )

    extension = FlaskNacos(app)

    with app.app_context():
        assert extension.client is None
    assert patched_create_client["count"] == 0


def test_invalid_authentication_does_not_log_credentials(make_app, patched_create_client, caplog):
    credentials = (
        "private-auth-user",
        "private-auth-password",
        "private-auth-access-key",
        "private-auth-secret-key",
    )
    app = make_app(
        {
            "NACOS_USERNAME": credentials[0],
            "NACOS_PASSWORD": credentials[1],
            "NACOS_ACCESS_KEY": credentials[2],
            "NACOS_SECRET_KEY": credentials[3],
            "NACOS_FAIL_FAST": False,
            "NACOS_LOG_ENABLED": True,
            "NACOS_LOG_FILE_ENABLED": False,
        }
    )

    with caplog.at_level(logging.DEBUG, logger="flask_nacos"):
        extension = FlaskNacos(app)

    with app.app_context():
        assert extension.client is None
    output = "\n".join(record.getMessage() for record in caplog.records)
    assert all(value not in output for value in credentials)
    assert patched_create_client["count"] == 0
