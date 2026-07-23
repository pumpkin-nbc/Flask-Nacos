"""Beginner-friendly, single-file Flask-Nacos example."""

import os

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

SERVICE_NAME = "flask-nacos-beginner"
CONFIG_DATA_ID = "flask-nacos-beginner.properties"
DEFAULT_GROUP = "DEFAULT_GROUP"

app = Flask(__name__)
app.config.update(
    # The first run needs only Python. Enable this after Nacos starts.
    NACOS_ENABLED=os.environ.get("NACOS_ENABLED", "false"),
    # Address of the Nacos server that this Flask process connects to.
    NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR", "127.0.0.1:8848"),
    NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
    NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
    NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
    NACOS_ACCESS_KEY=os.environ.get("NACOS_ACCESS_KEY"),
    NACOS_SECRET_KEY=os.environ.get("NACOS_SECRET_KEY"),
    NACOS_SERVICE_NAME=SERVICE_NAME,
    # Address advertised to consumers; this is not the Nacos server address.
    NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP", "127.0.0.1"),
    NACOS_SERVICE_PORT=3000,
    NACOS_SERVICE_HEARTBEAT_INTERVAL=5.0,
    NACOS_GROUP_NAME=DEFAULT_GROUP,
    NACOS_SERVICE_GROUP=DEFAULT_GROUP,
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_DEREGISTER=True,
    NACOS_CONFIG_ENABLED=True,
    NACOS_CONFIG_DATA_ID=CONFIG_DATA_ID,
    NACOS_CONFIG_GROUP=DEFAULT_GROUP,
    NACOS_REQUEST_TIMEOUT=5.0,
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
    NACOS_LOG_ENABLED=os.environ.get("NACOS_LOG_ENABLED", "false"),
    NACOS_LOG_LEVEL=os.environ.get("NACOS_LOG_LEVEL", "INFO"),
    NACOS_LOG_DIR=os.environ.get("NACOS_LOG_DIR", "./logs"),
    NACOS_LOG_FILENAME=os.environ.get(
        "NACOS_LOG_FILENAME", "flask_nacos.log"
    ),
    # Temporarily set NACOS_FAIL_FAST=true when an exact startup error is needed.
    NACOS_FAIL_FAST=os.environ.get("NACOS_FAIL_FAST", "false"),
)

nacos = FlaskNacos(app)


def _not_ready(feature: str):
    if nacos.get_status()["nacos_enabled"]:
        hint = "Check the Nacos address, authentication, namespace, and Flask logs."
    else:
        hint = "Start Nacos, set NACOS_ENABLED=true, and restart this app."
    return jsonify({"available": False, "feature": feature, "hint": hint}), 503


def _public_status():
    """Return only status fields that are safe to expose over HTTP."""
    status = nacos.get_status()
    return {
        "nacos_enabled": status.get("nacos_enabled", False),
        "client_initialized": status.get("client_initialized", False),
        "registered": status.get("registered", False),
        "service_name": status.get("service_name"),
        "service_port": status.get("service_port"),
    }


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "message": "Your Flask-Nacos beginner app is running.",
            "nacos_enabled": nacos.get_status()["nacos_enabled"],
            "next": [
                "/nacos/status",
                "/health/nacos",
                "/nacos/config",
                "/nacos/instances",
            ],
        }
    )


@app.route("/nacos/status", methods=["GET"])
def nacos_status():
    return jsonify(_public_status())


@app.route("/nacos/config", methods=["GET"])
def nacos_config():
    if nacos.get_client() is None:
        return _not_ready("config")
    content = nacos.get_config()  # Uses NACOS_CONFIG_DATA_ID by default.
    if content is None:
        return _not_ready("config")
    return jsonify(
        {"available": True, "data_id": CONFIG_DATA_ID, "content": content}
    )


@app.route("/nacos/instances", methods=["GET"])
def nacos_instances():
    if nacos.get_client() is None:
        return _not_ready("discovery")
    instances = nacos.list_instances(SERVICE_NAME)
    return jsonify(
        {
            "available": True,
            "service": SERVICE_NAME,
            "count": len(instances),
            "instances": instances,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000)
