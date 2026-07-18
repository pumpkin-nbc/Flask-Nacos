"""Nacos configuration center helpers."""

import logging
from typing import Any, Dict, Optional

from .exceptions import NacosConfigError, NacosValidationError
from .utils import validate_request_timeout

logger = logging.getLogger("flask_nacos")


def get_config(
    client: Any,
    config: Dict[str, Any],
    data_id: Optional[str],
    group: Optional[str] = None,
) -> Optional[str]:
    """Fetch the raw content of a config item from Nacos.

    ``group`` defaults to ``NACOS_CONFIG_GROUP`` (falling back to the connection
    level group) when not provided.
    """
    if not data_id:
        raise NacosValidationError("data_id is required to fetch config from Nacos")

    if client is None:
        raise NacosConfigError(
            "Cannot get config: Nacos client is not available "
            "(NACOS_ENABLED=False or client initialization failed)"
        )

    group_name = (
        group
        or config.get("NACOS_CONFIG_GROUP")
        or config.get("NACOS_GROUP_NAME")
        or "DEFAULT_GROUP"
    )
    timeout = validate_request_timeout(config.get("NACOS_REQUEST_TIMEOUT", 5.0))
    try:
        content = client.get_config(
            data_id,
            group_name,
            timeout=timeout,
        )
    except Exception as exc:
        logger.error("Config read failed (data_id=%s, group=%s)", data_id, group_name)
        raise NacosConfigError(
            f"Failed to get config from Nacos: SDK get_config call failed "
            f"(data_id={data_id}, group={group_name})"
        ) from exc

    logger.info("Config loaded (data_id=%s, group=%s)", data_id, group_name)
    return content


def load_config_to_flask(
    client: Any,
    app,
    config: Dict[str, Any],
    data_id: str,
    group: Optional[str] = None,
) -> Optional[str]:
    """Reserved for a future release.

    Will parse the Nacos config content and merge it into ``app.config``.
    Not implemented in v0.1.0.
    """
    raise NotImplementedError(
        "load_config_to_flask is reserved for a future release of flask-nacos"
    )


__all__ = ["get_config", "load_config_to_flask"]
