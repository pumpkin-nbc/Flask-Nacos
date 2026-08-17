"""Service registration with flask-nacos.

Registration and deregistration are lifecycle operations, so this example runs
them only in the trusted startup/shutdown flow. It deliberately does not expose
unauthenticated HTTP management endpoints.
"""

import os

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR", "127.0.0.1:8848"),
    NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
    NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
    NACOS_SERVICE_NAME=os.environ.get("NACOS_SERVICE_NAME", "registration-demo"),
    NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP", "127.0.0.1"),
    NACOS_SERVICE_PORT=int(os.environ.get("NACOS_SERVICE_PORT", "5000")),
    # Auto-register during trusted application initialization.
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_REGISTER_ON_INIT=True,
    NACOS_AUTO_DEREGISTER=True,
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


@app.route("/status")
def status():
    current = nacos.get_status()
    return jsonify(
        {
            "enabled": current.get("enabled", False),
            "client_created": current.get("client_created", False),
            "target_registered": current.get("target_registered", False),
            "registered": current.get("registered", False),
            "operation_running": current.get("operation_running", False),
            "last_error": current.get("last_error"),
            "service_name": current.get("service_name"),
            "service_port": current.get("service_port"),
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
