"""Nacos SDK client creation, isolating SDK specific details."""

import logging
from typing import Any, Dict

from .exceptions import NacosClientError

logger = logging.getLogger("flask_nacos")


def create_client(config: Dict[str, Any]) -> Any:
    """Create the underlying synchronous Nacos client.

    Uses the classic synchronous ``nacos.NacosClient`` from ``nacos-sdk-python``
    (2.x line), which is well suited to a synchronous WSGI application. Any SDK
    specific import or construction detail is contained here so the rest of the
    extension only deals with a plain client object.
    """
    try:
        import nacos
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise NacosClientError(
            "nacos-sdk-python is required. Install it with 'pip install nacos-sdk-python'."
        ) from exc

    server_addresses = config["NACOS_SERVER_ADDR"]
    namespace = config.get("NACOS_NAMESPACE_ID") or ""

    kwargs: Dict[str, Any] = {"namespace": namespace}
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
