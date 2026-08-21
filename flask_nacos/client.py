"""Nacos SDK client creation, isolating SDK specific details."""

import logging
import os
import tempfile
import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from .exceptions import NacosClientError
from .logging import configure_sdk_loggers

logger = logging.getLogger("flask_nacos")

_HEARTBEAT_PARAMETER_NAMES = (
    "service_name",
    "ip",
    "port",
    "cluster_name",
    "weight",
    "metadata",
    "ephemeral",
    "group_name",
)
_HEARTBEAT_DEFAULT_GROUP = "DEFAULT_GROUP"
_HEARTBEAT_DEFAULT_CLUSTER = None
_HEARTBEAT_WARNING_INTERVAL_SECONDS = 60.0
_HEARTBEAT_UNKNOWN = "<unknown>"

_HeartbeatIdentity = Tuple[str, str, Optional[str], str, int]
_HeartbeatFailureType = Tuple[str, str]
_HeartbeatFailureState = Tuple[_HeartbeatFailureType, float]


def _extract_heartbeat_identity(
    args: Any, kwargs: Dict[str, Any]
) -> Optional[_HeartbeatIdentity]:
    """Best-effort extraction of the verified SDK heartbeat identity."""
    try:
        if len(args) > len(_HEARTBEAT_PARAMETER_NAMES):
            return None
        if any(name not in _HEARTBEAT_PARAMETER_NAMES for name in kwargs):
            return None

        values: Dict[str, Any] = {}
        for position, name in enumerate(_HEARTBEAT_PARAMETER_NAMES):
            has_position = position < len(args)
            has_keyword = name in kwargs
            if has_position and has_keyword:
                return None
            if has_keyword:
                values[name] = kwargs[name]
            elif has_position:
                values[name] = args[position]

        service_name = values.get("service_name")
        ip = values.get("ip")
        port = values.get("port")
        cluster_name = values.get("cluster_name", _HEARTBEAT_DEFAULT_CLUSTER)
        group_name = values.get("group_name", _HEARTBEAT_DEFAULT_GROUP)

        if type(service_name) is not str or not service_name.strip():
            return None
        if type(ip) is not str or not ip.strip():
            return None
        if type(port) is not int or not 1 <= port <= 65535:
            return None
        if type(group_name) is not str or not group_name.strip():
            return None
        if cluster_name is not None and (
            type(cluster_name) is not str or not cluster_name.strip()
        ):
            return None

        return service_name, group_name, cluster_name, ip, port
    except Exception:
        # Observability must not change the SDK call's result or exception.
        return None


def _heartbeat_failure_type(exc: BaseException) -> _HeartbeatFailureType:
    try:
        exc_type = type(exc)
        module = exc_type.__module__
        qualname = exc_type.__qualname__
        if type(module) is str and type(qualname) is str:
            return module, qualname
    except Exception:
        pass
    return "<unknown>", "Exception"


def _heartbeat_failure_action(
    failure_states: Dict[_HeartbeatIdentity, _HeartbeatFailureState],
    identity: _HeartbeatIdentity,
    failure_type: _HeartbeatFailureType,
    now: float,
) -> str:
    previous = failure_states.get(identity)
    if previous is None:
        failure_states[identity] = (failure_type, now)
        return "warning"

    previous_type, previous_warning = previous
    warning_due = now - previous_warning >= _HEARTBEAT_WARNING_INTERVAL_SECONDS
    if previous_type != failure_type or warning_due:
        failure_states[identity] = (failure_type, now)
        return "warning"
    return "debug"


def _heartbeat_success_action(
    failure_states: Dict[_HeartbeatIdentity, _HeartbeatFailureState],
    identity: _HeartbeatIdentity,
) -> str:
    if identity in failure_states:
        del failure_states[identity]
        return "info"
    return "debug"


def _emit_heartbeat_log(
    action: str,
    outcome: str,
    identity: Optional[_HeartbeatIdentity],
    error_type: Optional[str] = None,
) -> None:
    if identity is None:
        service_name = group_name = cluster_name = ip = _HEARTBEAT_UNKNOWN
        port: Any = _HEARTBEAT_UNKNOWN
    else:
        service_name, group_name, cluster, ip, port = identity
        cluster_name = cluster if cluster is not None else "<default>"

    try:
        log_method = getattr(logger, action)
        if outcome == "failed":
            log_method(
                "Nacos heartbeat failed "
                "(service=%s, ip=%s, port=%s, group=%s, cluster=%s, error_type=%s)",
                service_name,
                ip,
                port,
                group_name,
                cluster_name,
                error_type or "Exception",
            )
        elif outcome == "recovered":
            log_method(
                "Nacos heartbeat recovered "
                "(service=%s, ip=%s, port=%s, group=%s, cluster=%s)",
                service_name,
                ip,
                port,
                group_name,
                cluster_name,
            )
        else:
            log_method(
                "Nacos heartbeat succeeded "
                "(service=%s, ip=%s, port=%s, group=%s, cluster=%s)",
                service_name,
                ip,
                port,
                group_name,
                cluster_name,
            )
    except Exception:
        # A custom logger/handler must not change the heartbeat call contract.
        return


def _install_heartbeat_logging(client: Any) -> None:
    """Wrap SDK heartbeat calls with sanitized success/failure records."""
    if getattr(client, "_flask_nacos_heartbeat_logging", False):
        return

    send_heartbeat = getattr(client, "send_heartbeat", None)
    if not callable(send_heartbeat):
        return

    failure_states: Dict[_HeartbeatIdentity, _HeartbeatFailureState] = {}
    state_lock = Lock()

    def logged_send_heartbeat(*args: Any, **kwargs: Any) -> Any:
        identity = _extract_heartbeat_identity(args, kwargs)
        try:
            result = send_heartbeat(*args, **kwargs)
        except Exception as exc:
            # Do not include the exception message: SDK/network exceptions can
            # contain request parameters, tokens, signatures, or response data.
            failure_type = _heartbeat_failure_type(exc)
            action = "warning"
            if identity is not None:
                try:
                    now = time.monotonic()
                    with state_lock:
                        action = _heartbeat_failure_action(
                            failure_states, identity, failure_type, now
                        )
                except Exception:
                    action = "warning"
            _emit_heartbeat_log(action, "failed", identity, failure_type[1])
            raise

        action = "debug"
        if identity is not None:
            try:
                with state_lock:
                    action = _heartbeat_success_action(failure_states, identity)
            except Exception:
                action = "debug"
        outcome = "recovered" if action == "info" else "succeeded"
        _emit_heartbeat_log(action, outcome, identity)
        return result

    try:
        client.send_heartbeat = logged_send_heartbeat
        client._flask_nacos_heartbeat_logging = True
    except (AttributeError, TypeError):
        # Defensive compatibility for an SDK client implementation that
        # disallows instance attributes. Client creation must remain usable.
        logger.warning("Nacos heartbeat status logging is unavailable for this SDK client")


def create_client(config: Dict[str, Any]) -> Any:
    """Create the underlying synchronous Nacos client.

    Uses the classic synchronous ``nacos.NacosClient`` from ``nacos-sdk-python``
    (2.x line), which is well suited to a synchronous WSGI application. Any SDK
    specific import or construction detail is contained here so the rest of the
    extension only deals with a plain client object.
    """
    # The synchronous SDK always prepares ``logDir`` during construction, even
    # when its logger already has a handler. Point it at an existing controlled
    # directory so it never creates ``~/logs/nacos``. SDK logging itself stays
    # isolated by a NullHandler and cannot expose auth/configuration payloads.
    configure_sdk_loggers()

    try:
        import nacos
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise NacosClientError(
            "nacos-sdk-python is required. Install it with 'pip install nacos-sdk-python'."
        ) from exc

    server_addresses = config["NACOS_SERVER_ADDR"]
    namespace = config.get("NACOS_NAMESPACE_ID") or ""

    configured_log_directory = config.get("NACOS_LOG_PATH", "./logs")
    if (
        config.get("NACOS_LOG_ENABLED", False)
        and config.get("NACOS_LOG_FILE_ENABLED", True)
        and isinstance(configured_log_directory, str)
        and configured_log_directory.strip()
    ):
        candidate_log_dir = os.path.abspath(os.path.expanduser(configured_log_directory.strip()))
        sdk_log_dir = (
            candidate_log_dir
            if not os.path.exists(candidate_log_dir) or os.path.isdir(candidate_log_dir)
            else tempfile.gettempdir()
        )
    else:
        sdk_log_dir = tempfile.gettempdir()

    kwargs: Dict[str, Any] = {"namespace": namespace, "logDir": sdk_log_dir}
    if config.get("NACOS_USERNAME"):
        kwargs["username"] = config["NACOS_USERNAME"]
    if config.get("NACOS_PASSWORD"):
        kwargs["password"] = config["NACOS_PASSWORD"]
    if config.get("NACOS_ACCESS_KEY"):
        kwargs["ak"] = config["NACOS_ACCESS_KEY"]
    if config.get("NACOS_SECRET_KEY"):
        kwargs["sk"] = config["NACOS_SECRET_KEY"]

    try:
        client = nacos.NacosClient(server_addresses, **kwargs)
    except Exception as exc:
        raise NacosClientError("Failed to construct the Nacos SDK client") from exc
    _install_heartbeat_logging(client)
    logger.info(
        "Nacos client initialized (server_addr=%s, namespace=%s)",
        server_addresses,
        namespace or "<default>",
    )
    return client


__all__ = ["create_client"]
