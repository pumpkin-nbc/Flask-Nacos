"""Nacos SDK client creation, isolating SDK specific details."""

import logging
import os
import tempfile
from typing import Any, Dict

from .exceptions import NacosClientError
from .logging import configure_sdk_loggers

logger = logging.getLogger("flask_nacos")


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
        and
        isinstance(configured_log_directory, str)
        and configured_log_directory.strip()
    ):
        candidate_log_dir = os.path.abspath(
            os.path.expanduser(configured_log_directory.strip())
        )
        sdk_log_dir = (
            candidate_log_dir
            if not os.path.exists(candidate_log_dir)
            or os.path.isdir(candidate_log_dir)
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
    logger.info(
        "Nacos client initialized (server_addr=%s, namespace=%s)",
        server_addresses,
        namespace or "<default>",
    )
    return client


__all__ = ["create_client"]
