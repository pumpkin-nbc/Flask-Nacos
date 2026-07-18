"""Service registration, deregistration and discovery helpers.

Each helper operates on a plain ``(client, config)`` pair and raises the
relevant :mod:`flask_nacos.exceptions` error on failure. Fail-fast versus
log-only handling is decided by the caller (the extension).
"""

import logging
from typing import Any, Dict, List, Optional

from . import discovery
from .config import validate_registration_config
from .exceptions import (
    NacosDeregistrationError,
    NacosDiscoveryError,
    NacosRegistrationError,
    NacosValidationError,
)
from .utils import get_local_ip

logger = logging.getLogger("flask_nacos")


def resolve_instance_identity(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the service name/ip/port/group used to identify this instance."""
    validate_registration_config(config)

    ip = config.get("NACOS_SERVICE_IP")
    if not ip:
        ip = get_local_ip()
        if not ip:
            raise NacosValidationError(
                "NACOS_SERVICE_IP is not set and local IP auto-detection failed"
            )

    return {
        "service_name": config["NACOS_SERVICE_NAME"],
        "ip": ip,
        "port": int(config["NACOS_SERVICE_PORT"]),
        "cluster_name": config.get("NACOS_SERVICE_CLUSTER") or "DEFAULT",
        "group_name": config.get("NACOS_SERVICE_GROUP") or "DEFAULT_GROUP",
    }


def register_instance(client: Any, config: Dict[str, Any]) -> bool:
    """Register the current service instance with Nacos."""
    identity = resolve_instance_identity(config)
    ephemeral = config.get("NACOS_SERVICE_EPHEMERAL", True)
    registration_options: Dict[str, Any] = {
        "cluster_name": identity["cluster_name"],
        "weight": config.get("NACOS_SERVICE_WEIGHT", 1.0),
        "metadata": config.get("NACOS_SERVICE_METADATA") or {},
        "enable": config.get("NACOS_SERVICE_ENABLED", True),
        "healthy": config.get("NACOS_SERVICE_HEALTHY", True),
        "ephemeral": ephemeral,
        "group_name": identity["group_name"],
    }
    if ephemeral:
        registration_options["heartbeat_interval"] = config.get(
            "NACOS_SERVICE_HEARTBEAT_INTERVAL", 5.0
        )
    logger.info(
        "Registering service instance (service=%s, ip=%s, port=%s, group=%s, "
        "ephemeral=%s)",
        identity["service_name"],
        identity["ip"],
        identity["port"],
        identity["group_name"],
        ephemeral,
    )
    try:
        result = client.add_naming_instance(
            identity["service_name"],
            identity["ip"],
            identity["port"],
            **registration_options,
        )
    except Exception as exc:
        raise NacosRegistrationError(
            "Failed to register service instance: Nacos SDK add_naming_instance "
            f"call failed (service={identity['service_name']}, ip={identity['ip']}, "
            f"port={identity['port']}, group={identity['group_name']})"
        ) from exc

    if result is not True:
        raise NacosRegistrationError(
            "Failed to register service instance: Nacos SDK "
            "add_naming_instance returned an unsuccessful result "
            f"(service={identity['service_name']}, ip={identity['ip']}, "
            f"port={identity['port']}, group={identity['group_name']})"
        )

    logger.info(
        "Service registered (service=%s, ip=%s, port=%s, group=%s)",
        identity["service_name"],
        identity["ip"],
        identity["port"],
        identity["group_name"],
    )
    return True


def deregister_instance(client: Any, config: Dict[str, Any]) -> bool:
    """Deregister the current service instance from Nacos."""
    identity = resolve_instance_identity(config)
    logger.info(
        "Deregistering service instance (service=%s, ip=%s, port=%s, group=%s)",
        identity["service_name"],
        identity["ip"],
        identity["port"],
        identity["group_name"],
    )
    try:
        result = client.remove_naming_instance(
            identity["service_name"],
            identity["ip"],
            identity["port"],
            cluster_name=identity["cluster_name"],
            ephemeral=config.get("NACOS_SERVICE_EPHEMERAL", True),
            group_name=identity["group_name"],
        )
    except Exception as exc:
        raise NacosDeregistrationError(
            "Failed to deregister service instance: Nacos SDK remove_naming_instance "
            f"call failed (service={identity['service_name']}, ip={identity['ip']}, "
            f"port={identity['port']}, group={identity['group_name']})"
        ) from exc

    if result is not True:
        raise NacosDeregistrationError(
            "Failed to deregister service instance: Nacos SDK "
            "remove_naming_instance returned an unsuccessful result "
            f"(service={identity['service_name']}, ip={identity['ip']}, "
            f"port={identity['port']}, group={identity['group_name']})"
        )

    logger.info(
        "Service deregistered (service=%s, ip=%s, port=%s, group=%s)",
        identity["service_name"],
        identity["ip"],
        identity["port"],
        identity["group_name"],
    )
    return True


def list_instances(
    client: Any,
    config: Dict[str, Any],
    service_name: str,
    group: Optional[str] = None,
    healthy_only: bool = True,
    cluster: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Return the list of instances for ``service_name``.

    The raw SDK hosts are filtered by ``cluster``/``metadata`` (when provided)
    and, when ``NACOS_INSTANCE_NORMALIZE`` is enabled, each surviving instance is
    converted to a standard dict. A single instance that fails normalization is
    logged and skipped rather than failing the whole discovery call.
    """
    if not service_name:
        logger.error("Service discovery failed: service_name is required")
        raise NacosValidationError(
            "Service discovery failed: service_name is empty (a non-empty "
            "service name is required)"
        )

    group_name = group or config.get("NACOS_GROUP_NAME") or "DEFAULT_GROUP"
    try:
        result = client.list_naming_instance(
            service_name,
            group_name=group_name,
            healthy_only=healthy_only,
        )
    except Exception as exc:
        logger.error("Service discovery failed for %s", service_name)
        raise NacosDiscoveryError(
            "Service discovery failed: Nacos SDK list_naming_instance call failed "
            f"(service={service_name}, group={group_name})"
        ) from exc

    instances = discovery.extract_instances(result)

    filtered = discovery.filter_instances(instances, cluster, metadata)

    if config.get("NACOS_INSTANCE_NORMALIZE", True):
        normalized: List[Dict[str, Any]] = []
        for inst in filtered:
            try:
                normalized.append(discovery.normalize_instance(inst))
            except Exception as exc:
                logger.warning("Skipping instance; normalization failed: %s", exc)
        output: List[Any] = normalized
    else:
        output = filtered

    logger.info(
        "Service discovery succeeded (service=%s, group=%s, healthy_only=%s, "
        "cluster=%s, count=%d)",
        service_name,
        group_name,
        healthy_only,
        cluster,
        len(output),
    )
    return output


def get_one_healthy_instance(
    client: Any,
    config: Dict[str, Any],
    service_name: str,
    group: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return a single healthy instance for ``service_name`` (or ``None``)."""
    instances = list_instances(
        client, config, service_name, group=group, healthy_only=True
    )
    if not instances:
        return None
    return instances[0]


__all__ = [
    "resolve_instance_identity",
    "register_instance",
    "deregister_instance",
    "list_instances",
    "get_one_healthy_instance",
]
