"""Optional Flask health-check route for flask-nacos.

The health route reports only the extension's internal state and never calls
the Nacos server, so it stays fast and cannot be slowed down by Nacos latency.
"""

import logging
from typing import Any, Dict

from flask import jsonify

logger = logging.getLogger("flask_nacos")

HEALTH_ENDPOINT = "flask_nacos_health"


def build_health_payload(extension) -> Dict[str, Any]:
    """Build the health-check response body from the extension state."""
    status = extension.get_status()

    nacos_enabled = status.get("nacos_enabled", False)
    client_initialized = status.get("client_initialized", False)

    if not nacos_enabled:
        overall = "disabled"
    elif not client_initialized:
        overall = "error"
    else:
        overall = "ok"

    payload: Dict[str, Any] = {
        "status": overall,
        "nacos_enabled": nacos_enabled,
        "client_initialized": client_initialized,
        "registered": status.get("registered", False),
    }

    # Only include instance identity fields when they are known.
    for key in ("service_name", "service_ip", "service_port"):
        value = status.get(key)
        if value is not None:
            payload[key] = value

    return payload


def register_health_route(app, extension) -> bool:
    """Register the health-check route on ``app`` (idempotent).

    Returns ``True`` when the route was registered, ``False`` when it already
    existed and registration was skipped.
    """
    cfg = extension.config or {}
    path = cfg.get("NACOS_HEALTH_CHECK_PATH") or "/health/nacos"

    if HEALTH_ENDPOINT in app.view_functions:
        logger.info("Health check route already registered; skipping (path=%s)", path)
        return False

    existing_paths = {rule.rule for rule in app.url_map.iter_rules()}
    if path in existing_paths:
        logger.info("Health check path %s already in use; skipping registration", path)
        return False

    def _health_view():
        return jsonify(build_health_payload(extension))

    app.add_url_rule(path, endpoint=HEALTH_ENDPOINT, view_func=_health_view, methods=["GET"])
    logger.info("Health check route registered (path=%s)", path)
    return True


__all__ = ["register_health_route", "build_health_payload", "HEALTH_ENDPOINT"]
