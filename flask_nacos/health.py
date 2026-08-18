"""Optional Flask health-check route for flask-nacos.

The health route reports only the extension's internal state and never calls
the Nacos server, so it stays fast and cannot be slowed down by Nacos latency.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

from flask import jsonify

if TYPE_CHECKING:
    from flask import Flask

    from .extension import FlaskNacos

logger = logging.getLogger("flask_nacos")

HEALTH_ENDPOINT = "flask_nacos_health"


def build_health_payload(extension: "FlaskNacos") -> Dict[str, Any]:
    """Build the fixed, local-only health response."""
    status = extension.get_status()

    enabled = status["enabled"]
    registered = status["registered"]
    target_registered = status["target_registered"]
    operation_running = status["operation_running"]
    last_error = status["last_error"]

    if not enabled:
        overall = "disabled"
    elif registered == target_registered:
        overall = "ok"
    elif operation_running and last_error is None:
        overall = "ok"
    else:
        overall = "error"

    return {
        "status": overall,
        "enabled": enabled,
        "client_created": status["client_created"],
        "target_registered": target_registered,
        "registered": registered,
        "operation_running": operation_running,
        "last_error": last_error,
    }


def register_health_route(app: "Flask", extension: "FlaskNacos") -> bool:
    """Register the health-check route on ``app`` (idempotent).

    Returns ``True`` when the route was registered, ``False`` when it already
    existed and registration was skipped.
    """
    # Use the explicit target app rather than context-based extension
    # properties. ``init_app(app_b)`` may legitimately be called while an
    # ``app_a`` context is active.
    state = app.extensions.get("nacos") or {}
    cfg = state.get("config") or {}
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
