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
    # With once-per-process True, repeat register_instance() calls are no-ops
    # within the same process.
    NACOS_REGISTER_ONCE_PER_PROCESS=True,
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


@app.route("/status")
def status():
    current = nacos.get_status()
    return jsonify(
        {
            "nacos_enabled": current.get("nacos_enabled", False),
            "client_initialized": current.get("client_initialized", False),
            "registered": current.get("registered", False),
            "service_name": current.get("service_name"),
            "service_port": current.get("service_port"),
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
