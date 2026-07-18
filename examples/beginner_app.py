"""Beginner-friendly, single-file Flask-Nacos example."""

import os

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

SERVICE_NAME = "flask-nacos-beginner"
CONFIG_DATA_ID = "flask-nacos-beginner.properties"
DEFAULT_GROUP = "DEFAULT_GROUP"

app = Flask(__name__)
app.config.update(
    # The first run needs only Python. Enable this after local Nacos starts.
    NACOS_ENABLED=os.environ.get("NACOS_ENABLED", "false"),
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME=SERVICE_NAME,
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
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
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


def _not_ready(feature: str):
    if nacos.get_status()["nacos_enabled"]:
        hint = "Check that Nacos is running, then check the Flask logs."
    else:
        hint = "Start Nacos, set NACOS_ENABLED=true, and restart this app."
    return jsonify({"available": False, "feature": feature, "hint": hint}), 503


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
    return jsonify(nacos.get_status())


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
    app.run(host="127.0.0.1", port=5000)
