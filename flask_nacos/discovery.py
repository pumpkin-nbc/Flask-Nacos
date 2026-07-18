"""Service-discovery helpers: instance normalization, filtering and selection.

These helpers work on the raw hosts returned by the Nacos SDK (dicts or
attribute-style objects) as well as on already-normalized dicts, so they can be
reused across the discovery pipeline.
"""

import logging
import math
import random
from typing import Any, Dict, List, Optional

from .exceptions import NacosDiscoveryError
from .utils import to_bool

logger = logging.getLogger("flask_nacos")

SUPPORTED_STRATEGIES = ("first", "random", "weight")

_MISSING = object()

# Keys that may hold the list of instances in a Nacos SDK response dict.
_HOSTS_KEYS = ("hosts", "instances")


def extract_instances(response: Any) -> List[Any]:
    """Extract the list of instances from a Nacos SDK response.

    Different SDK versions/shapes are tolerated:

    - ``None`` or an empty list -> ``[]``
    - a ``list`` -> returned as-is
    - a ``dict`` with ``hosts`` or ``instances`` -> that list
    - a ``dict`` with ``data`` holding either a list, or a nested dict with
      ``hosts``/``instances`` -> that list

    Raises :class:`NacosDiscoveryError` for a fundamentally unrecognized shape
    so the caller can honor ``NACOS_FAIL_FAST``.
    """
    if response is None:
        return []

    if isinstance(response, list):
        return response

    if isinstance(response, dict):
        for key in _HOSTS_KEYS:
            value = response.get(key)
            if isinstance(value, list):
                return value

        data = response.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in _HOSTS_KEYS:
                value = data.get(key)
                if isinstance(value, list):
                    return value

        # An empty/instance-less dict (e.g. {} or {"hosts": None}) is treated as
        # "no instances" rather than an error.
        if not response or any(k in response for k in _HOSTS_KEYS + ("data",)):
            return []

    raise NacosDiscoveryError(
        f"Unrecognized Nacos discovery response shape: {type(response).__name__}"
    )


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

    Optional fields fall back to sensible defaults. A missing or malformed
    endpoint raises ``NacosDiscoveryError`` so callers can skip that single bad
    instance without failing the complete discovery result.
    """
    if instance is None:
        raise NacosDiscoveryError("Cannot normalize a None instance")

    try:
        ip = _get_field(instance, ("ip",), None)
        if not isinstance(ip, str) or not ip.strip():
            raise NacosDiscoveryError("Discovered instance must have a non-empty IP")
        ip = ip.strip()

        port_value = _get_field(instance, ("port",), None)
        if isinstance(port_value, bool):
            raise NacosDiscoveryError("Discovered instance port must be an integer")
        if isinstance(port_value, float) and (
            not math.isfinite(port_value) or not port_value.is_integer()
        ):
            raise NacosDiscoveryError("Discovered instance port must be an integer")
        try:
            port = int(port_value)
        except (TypeError, ValueError, OverflowError):
            raise NacosDiscoveryError("Discovered instance port must be an integer")
        if not 1 <= port <= 65535:
            raise NacosDiscoveryError(
                "Discovered instance port must be in range 1-65535"
            )

        metadata = _get_field(instance, ("metadata",), {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            metadata = dict(metadata)

        weight_value = _get_field(instance, ("weight",), 1.0)
        try:
            weight = 1.0 if isinstance(weight_value, bool) else float(weight_value)
        except (TypeError, ValueError, OverflowError):
            weight = 1.0
        if not math.isfinite(weight):
            weight = 1.0

        return {
            "ip": ip,
            "port": port,
            "service_name": _get_field(
                instance, ("service_name", "serviceName"), None
            ),
            "cluster_name": _get_field(
                instance, ("cluster_name", "clusterName"), "DEFAULT"
            ),
            "weight": weight,
            "healthy": to_bool(_get_field(instance, ("healthy",), True), True),
            "enabled": to_bool(_get_field(instance, ("enabled",), True), True),
            "ephemeral": to_bool(_get_field(instance, ("ephemeral",), True), True),
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
        weight_value = _get_field(inst, ("weight",), 1.0)
        try:
            weight = 1.0 if isinstance(weight_value, bool) else float(weight_value)
        except (TypeError, ValueError, OverflowError):
            weight = 1.0
        if not math.isfinite(weight):
            weight = 1.0
        weights.append(weight if weight > 0 else 0.0)

    if not any(w > 0 for w in weights):
        logger.info("All instance weights <= 0; weight strategy degraded to 'first'")
        return instances[0]

    return random.choices(instances, weights=weights, k=1)[0]


__all__ = [
    "extract_instances",
    "normalize_instance",
    "filter_instances",
    "select_instance",
    "SUPPORTED_STRATEGIES",
]
