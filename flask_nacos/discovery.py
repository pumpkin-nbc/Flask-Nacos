"""Service-discovery helpers: instance normalization, filtering and selection.

These helpers work on the raw hosts returned by the Nacos SDK (dicts or
attribute-style objects) as well as on already-normalized dicts, so they can be
reused across the discovery pipeline.
"""

import logging
import random
from typing import Any, Dict, List, Optional

from .exceptions import NacosDiscoveryError

logger = logging.getLogger("flask_nacos")

SUPPORTED_STRATEGIES = ("first", "random", "weight")

_MISSING = object()


def _get_field(instance: Any, keys, default: Any = None) -> Any:
    """Read a field from a dict or an attribute-style object.

    ``keys`` is an iterable of candidate names (to cover both ``camelCase`` and
    ``snake_case`` variants returned by different SDK versions). The first
    present, non-``None`` value wins.
    """
    for key in keys:
        if isinstance(instance, dict):
            value = instance.get(key, _MISSING)
        else:
            value = getattr(instance, key, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return default


def normalize_instance(instance: Any) -> Dict[str, Any]:
    """Convert a Nacos SDK instance (dict or object) into a standard dict.

    Missing fields fall back to sensible defaults. Raises ``NacosDiscoveryError``
    only when ``instance`` is fundamentally unusable (e.g. ``None``) so that the
    caller can log and skip a single bad instance without failing discovery.
    """
    if instance is None:
        raise NacosDiscoveryError("Cannot normalize a None instance")

    try:
        metadata = _get_field(instance, ("metadata",), {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        weight = _get_field(instance, ("weight",), 1.0)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1.0

        port = _get_field(instance, ("port",), None)
        if port is not None:
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = None

        return {
            "ip": _get_field(instance, ("ip",), None),
            "port": port,
            "service_name": _get_field(
                instance, ("service_name", "serviceName"), None
            ),
            "cluster_name": _get_field(
                instance, ("cluster_name", "clusterName"), "DEFAULT"
            ),
            "weight": weight,
            "healthy": bool(_get_field(instance, ("healthy",), True)),
            "enabled": bool(_get_field(instance, ("enabled",), True)),
            "ephemeral": bool(_get_field(instance, ("ephemeral",), True)),
            "metadata": metadata,
        }
    except NacosDiscoveryError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise NacosDiscoveryError(f"Failed to normalize instance: {exc}") from exc


def _matches_filters(
    instance: Any, cluster: Optional[str], metadata: Optional[Dict[str, Any]]
) -> bool:
    if cluster:
        inst_cluster = _get_field(
            instance, ("cluster_name", "clusterName"), "DEFAULT"
        )
        if inst_cluster != cluster:
            return False

    if metadata:
        inst_metadata = _get_field(instance, ("metadata",), {}) or {}
        if not isinstance(inst_metadata, dict):
            return False
        for key, value in metadata.items():
            if inst_metadata.get(key) != value:
                return False

    return True


def filter_instances(
    instances: List[Any],
    cluster: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """Filter ``instances`` by cluster and/or metadata key/value pairs.

    A falsy ``cluster``/``metadata`` means "no filtering" for that dimension.
    """
    if not cluster and not metadata:
        return list(instances)
    return [i for i in instances if _matches_filters(i, cluster, metadata)]


def select_instance(
    instances: List[Dict[str, Any]], strategy: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Select a single instance from ``instances`` using ``strategy``.

    Supported strategies: ``first``, ``random``, ``weight``. Returns ``None`` for
    an empty list; raises ``NacosDiscoveryError`` for an unsupported strategy.
    """
    strategy = strategy or "first"
    if strategy not in SUPPORTED_STRATEGIES:
        raise NacosDiscoveryError(
            f"Unsupported discovery strategy: {strategy!r} "
            f"(supported: {', '.join(SUPPORTED_STRATEGIES)})"
        )

    if not instances:
        return None

    logger.debug("Selecting healthy instance using strategy=%s", strategy)

    if strategy == "first":
        return instances[0]

    if strategy == "random":
        return random.choice(instances)

    # strategy == "weight"
    weights = []
    for inst in instances:
        weight = _get_field(inst, ("weight",), 1.0)
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1.0
        weights.append(weight if weight > 0 else 0.0)

    if not any(w > 0 for w in weights):
        logger.info("All instance weights <= 0; weight strategy degraded to 'first'")
        return instances[0]

    return random.choices(instances, weights=weights, k=1)[0]


__all__ = [
    "normalize_instance",
    "filter_instances",
    "select_instance",
    "SUPPORTED_STRATEGIES",
]
