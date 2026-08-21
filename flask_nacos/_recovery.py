"""Private failure classification for registration lifecycle recovery.

The classifier is intentionally conservative.  It only labels a failure as
transient when structured evidence says that waiting can reasonably help.
Unknown SDK and runtime failures keep the finite retry behaviour and never
enter long-lived recovery.
"""

import errno as errno_module
import importlib
import socket
from dataclasses import dataclass
from enum import Enum
from importlib import metadata as importlib_metadata
from typing import Any, List, Optional, Set, Tuple

from .exceptions import NacosConfigError

_EXCEPTION_CHAIN_MAX_DEPTH = 16
_TRANSIENT_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_DETERMINISTIC_HTTP_STATUSES = frozenset(
    {400, 401, 403, 404, 405, 406, 409, 410, 411, 412, 413, 414, 415, 416, 422}
)


def _available_errno(*names: str) -> Set[int]:
    values: Set[int] = set()
    for name in names:
        value = getattr(errno_module, name, None)
        if isinstance(value, int):
            values.add(value)
    return values


_TRANSIENT_ERRNOS = frozenset(
    _available_errno(
        "ECONNABORTED",
        "ECONNREFUSED",
        "ECONNRESET",
        "EHOSTDOWN",
        "EHOSTUNREACH",
        "ENETDOWN",
        "ENETRESET",
        "ENETUNREACH",
        "EPIPE",
        "ETIMEDOUT",
    )
)
_TRANSIENT_ERROR_CODES = frozenset(
    {
        "CLIENT_DISCONNECT",
        "CONNECTION_ABORTED",
        "CONNECTION_REFUSED",
        "CONNECTION_RESET",
        "HOST_UNREACHABLE",
        "NETWORK_UNREACHABLE",
        "REQUEST_TIMEOUT",
        "SERVER_UNAVAILABLE",
        "SERVICE_UNAVAILABLE",
        "TIMEOUT",
    }
)
_DETERMINISTIC_ERROR_CODES = frozenset(
    {
        "ACCESS_DENIED",
        "AUTH_FAILED",
        "AUTHENTICATION_FAILED",
        "FORBIDDEN",
        "INVALID_ARGUMENT",
        "INVALID_CONFIG",
        "INVALID_PARAMETER",
        "INVALID_PARAM",
        "NO_PERMISSION",
        "PARAMETER_ERROR",
        "PERMISSION_DENIED",
        "UNAUTHORIZED",
    }
)


class _LifecycleFailureClass(Enum):
    """Private recovery decision for one lifecycle failure."""

    TRANSIENT = "transient"
    DETERMINISTIC = "deterministic"
    UNKNOWN = "unknown"


class _LifecycleFailureStage(Enum):
    """The internal stage at which a lifecycle failure happened."""

    CLIENT_CREATE = "client_create"
    REGISTRATION_PREPARE = "registration_prepare"
    REGISTER_RPC = "register_rpc"
    COMPENSATING_DEREGISTER_RPC = "compensating_deregister_rpc"
    SYNC_DEREGISTER_RPC = "sync_deregister_rpc"
    EXIT_DEREGISTER_RPC = "exit_deregister_rpc"


@dataclass(frozen=True)
class _LifecycleFailure:
    """Sanitized classification used by the lifecycle owner."""

    failure_class: _LifecycleFailureClass
    safe_error_type: str


_BARE_SDK_EXCEPTION_WHITELIST = frozenset(
    {
        (
            "2.0.0",
            "nacos.exception",
            "NacosRequestException",
            _LifecycleFailureStage.REGISTER_RPC,
            "register",
        ),
        (
            "2.0.0",
            "nacos.exception",
            "NacosRequestException",
            _LifecycleFailureStage.COMPENSATING_DEREGISTER_RPC,
            "deregister",
        ),
        (
            "2.0.11",
            "nacos.exception",
            "NacosRequestException",
            _LifecycleFailureStage.CLIENT_CREATE,
            "register",
        ),
        (
            "2.0.11",
            "nacos.exception",
            "NacosRequestException",
            _LifecycleFailureStage.REGISTER_RPC,
            "register",
        ),
        (
            "2.0.11",
            "nacos.exception",
            "NacosRequestException",
            _LifecycleFailureStage.COMPENSATING_DEREGISTER_RPC,
            "deregister",
        ),
    }
)
_MISSING = object()


def _safe_error_type(exc: BaseException) -> str:
    try:
        name = type(exc).__name__
    except Exception:
        return "LifecycleFailure"
    return name if isinstance(name, str) and name else "LifecycleFailure"


def _safe_attr(value: Any, name: str) -> Tuple[Any, bool]:
    try:
        return getattr(value, name, _MISSING), True
    except Exception:
        return _MISSING, False


def _structured_integer(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isascii() and stripped.isdigit():
            try:
                return int(stripped)
            except (ValueError, OverflowError):
                return None
    return None


def _normalized_error_code(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper().replace("-", "_")
    return normalized or None


def _installed_sdk_version() -> Optional[str]:
    try:
        value = importlib_metadata.version("nacos-sdk-python")
    except Exception:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _installed_bare_request_exception_type() -> Any:
    try:
        module = importlib.import_module("nacos.exception")
        exception_type = module.NacosRequestException
        if not isinstance(exception_type, type) or not issubclass(exception_type, BaseException):
            return None
    except Exception:
        return None
    try:
        if (
            exception_type.__module__ != "nacos.exception"
            or exception_type.__name__ != "NacosRequestException"
        ):
            return None
    except Exception:
        return None
    return exception_type


def _exception_type_identity(exc: BaseException) -> Optional[Tuple[str, str]]:
    try:
        exception_type = type(exc)
        module = exception_type.__module__
        name = exception_type.__name__
    except Exception:
        return None
    if not isinstance(module, str) or not isinstance(name, str):
        return None
    return module, name


def _http_statuses(exc: BaseException) -> Tuple[List[int], bool]:
    statuses: List[int] = []
    complete = True
    for field_name in ("status_code", "http_status", "http_status_code", "status", "code"):
        value, ok = _safe_attr(exc, field_name)
        complete = complete and ok
        if value is not _MISSING:
            parsed = _structured_integer(value)
            if parsed is not None:
                statuses.append(parsed)

    response, ok = _safe_attr(exc, "response")
    complete = complete and ok
    if response is not _MISSING and response is not None:
        for field_name in ("status_code", "status", "code"):
            response_status, ok = _safe_attr(response, field_name)
            complete = complete and ok
            if response_status is not _MISSING:
                parsed = _structured_integer(response_status)
                if parsed is not None:
                    statuses.append(parsed)
    return statuses, complete


def _error_codes(exc: BaseException) -> Tuple[List[str], bool]:
    codes: List[str] = []
    complete = True
    for field_name in ("error_code", "code"):
        value, ok = _safe_attr(exc, field_name)
        complete = complete and ok
        if value is not _MISSING:
            normalized = _normalized_error_code(value)
            if normalized is not None:
                codes.append(normalized)
    return codes, complete


def _errno_value(exc: BaseException) -> Tuple[Optional[int], bool]:
    value, complete = _safe_attr(exc, "errno")
    if value is _MISSING or isinstance(value, bool) or not isinstance(value, int):
        return None, complete
    return value, complete


def _classify_lifecycle_failure(
    exc: BaseException,
    *,
    stage: _LifecycleFailureStage,
    direction: str,
) -> _LifecycleFailure:
    """Classify one failure without ever allowing classifier errors to escape."""
    safe_error_type = _safe_error_type(exc)
    try:
        deterministic = False
        transient = False
        traversal_complete = True
        bare_candidates: List[Tuple[Any, str, str]] = []
        pending: List[BaseException] = [exc]
        scheduled: Set[int] = {id(exc)}
        visited: Set[int] = set()
        depth = 0

        while pending and depth < _EXCEPTION_CHAIN_MAX_DEPTH:
            current = pending.pop()
            identity = id(current)
            scheduled.discard(identity)
            if identity in visited:
                traversal_complete = False
                continue
            visited.add(identity)
            depth += 1

            if isinstance(
                current,
                (NacosConfigError, ValueError, TypeError, ImportError, KeyError, AssertionError),
            ):
                deterministic = True
            if isinstance(current, PermissionError):
                deterministic = True
            if isinstance(current, (TimeoutError, socket.timeout, ConnectionError)):
                transient = True

            current_errno, complete = _errno_value(current)
            traversal_complete = traversal_complete and complete
            if isinstance(current, socket.gaierror):
                if current_errno == getattr(socket, "EAI_AGAIN", None):
                    transient = True
            elif current_errno in _TRANSIENT_ERRNOS:
                transient = True

            statuses, complete = _http_statuses(current)
            traversal_complete = traversal_complete and complete
            if any(status in _DETERMINISTIC_HTTP_STATUSES for status in statuses):
                deterministic = True
            if any(status in _TRANSIENT_HTTP_STATUSES for status in statuses):
                transient = True

            codes, complete = _error_codes(current)
            traversal_complete = traversal_complete and complete
            if any(code in _DETERMINISTIC_ERROR_CODES for code in codes):
                deterministic = True
            if any(code in _TRANSIENT_ERROR_CODES for code in codes):
                transient = True

            type_identity = _exception_type_identity(current)
            if type_identity is None:
                traversal_complete = False
            elif type_identity == ("nacos.exception", "NacosRequestException"):
                bare_candidates.append((type(current), type_identity[0], type_identity[1]))

            for chain_field in ("__cause__", "__context__"):
                chained, complete = _safe_attr(current, chain_field)
                traversal_complete = traversal_complete and complete
                if chained is _MISSING or chained is None:
                    continue
                if isinstance(chained, BaseException):
                    if id(chained) in visited:
                        traversal_complete = False
                    elif id(chained) in scheduled:
                        continue
                    else:
                        pending.append(chained)
                        scheduled.add(id(chained))
                else:
                    traversal_complete = False

        if pending:
            traversal_complete = False

        if deterministic:
            failure_class = _LifecycleFailureClass.DETERMINISTIC
        elif transient:
            failure_class = _LifecycleFailureClass.TRANSIENT
        elif traversal_complete and bare_candidates:
            sdk_version = _installed_sdk_version()
            installed_exception_type = _installed_bare_request_exception_type()
            whitelisted = any(
                (
                    sdk_version,
                    module,
                    name,
                    stage,
                    direction,
                )
                in _BARE_SDK_EXCEPTION_WHITELIST
                and candidate_type is installed_exception_type
                for candidate_type, module, name in bare_candidates
            )
            failure_class = (
                _LifecycleFailureClass.TRANSIENT
                if whitelisted
                else _LifecycleFailureClass.UNKNOWN
            )
        else:
            failure_class = _LifecycleFailureClass.UNKNOWN
    except Exception:
        failure_class = _LifecycleFailureClass.UNKNOWN

    return _LifecycleFailure(failure_class, safe_error_type)


def _synthetic_lifecycle_failure(
    safe_error_type: str,
    failure_class: _LifecycleFailureClass = _LifecycleFailureClass.UNKNOWN,
) -> _LifecycleFailure:
    """Create a sanitized failure for a local precondition/invariant."""
    return _LifecycleFailure(failure_class, safe_error_type)


__all__: List[str] = []
