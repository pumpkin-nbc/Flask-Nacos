"""Complete Flask application-factory integration example.

Run locally after starting Nacos and setting any desired environment variables:

    python examples/complete_factory_app.py

The matching English and Chinese guides live in ``docs/complete-example.md``
and ``docs/complete-example.zh-CN.md``.
"""

import os

from flask import Flask, jsonify, request

from flask_nacos import FlaskNacos
from flask_nacos.exceptions import FlaskNacosError

nacos = FlaskNacos()


def create_app() -> Flask:
    """Create and configure a Flask application integrated with Nacos."""
    app = Flask(__name__)

    service_name = os.environ.get(
        "NACOS_SERVICE_NAME", "flask-nacos-complete-demo"
    )
    service_port = int(os.environ.get("NACOS_SERVICE_PORT", "5000"))
    service_group = os.environ.get("NACOS_SERVICE_GROUP", "DEFAULT_GROUP")

    app.config.update(
        NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR", "127.0.0.1:8848"),
        NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
        NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
        NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
        NACOS_ACCESS_KEY=os.environ.get("NACOS_ACCESS_KEY"),
        NACOS_SECRET_KEY=os.environ.get("NACOS_SECRET_KEY"),
        NACOS_SERVICE_NAME=service_name,
        NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP", "127.0.0.1"),
        NACOS_SERVICE_PORT=service_port,
        # Use the same default group for registration and discovery so the
        # service can discover itself when NACOS_SERVICE_GROUP is overridden.
        NACOS_GROUP_NAME=service_group,
        NACOS_SERVICE_GROUP=service_group,
        NACOS_CONFIG_ENABLED=True,
        NACOS_CONFIG_DATA_ID=os.environ.get(
            "NACOS_CONFIG_DATA_ID", "flask-nacos-demo.properties"
        ),
        NACOS_CONFIG_GROUP=os.environ.get("NACOS_CONFIG_GROUP", "DEFAULT_GROUP"),
        NACOS_REQUEST_TIMEOUT=float(
            os.environ.get("NACOS_REQUEST_TIMEOUT", "5.0")
        ),
        NACOS_AUTO_REGISTER=True,
        NACOS_AUTO_DEREGISTER=True,
        NACOS_REGISTER_ONCE_PER_PROCESS=True,
        NACOS_DEREGISTER_ON_EXIT=os.environ.get(
            "NACOS_DEREGISTER_ON_EXIT", "true"
        ),
        NACOS_HEALTH_CHECK_ENABLED=True,
        NACOS_HEALTH_CHECK_PATH="/health/nacos",
        NACOS_LOG_ENABLED=os.environ.get("NACOS_LOG_ENABLED", "false"),
        NACOS_LOG_CONSOLE_ENABLED=os.environ.get(
            "NACOS_LOG_CONSOLE_ENABLED", "true"
        ),
        NACOS_LOG_FILE_ENABLED=os.environ.get(
            "NACOS_LOG_FILE_ENABLED", "true"
        ),
        NACOS_LOG_PATH=os.environ.get("NACOS_LOG_PATH", "./logs"),
        NACOS_LOG_FILENAME=os.environ.get(
            "NACOS_LOG_FILENAME", "flask-nacos.log"
        ),
        # Keep the Flask app available while Nacos is temporarily unavailable.
        NACOS_FAIL_FAST=False,
    )

    nacos.init_app(app)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify(
            {
                "service": service_name,
                "message": "Flask-Nacos complete example is running",
                "endpoints": {
                    "health": "/health/nacos",
                    "status": "/api/nacos/status",
                    "config": "/api/nacos/config",
                    "instances": "/api/nacos/instances",
                },
            }
        )

    @app.route("/api/nacos/status", methods=["GET"])
    def nacos_status():
        status = nacos.get_status()
        return jsonify(
            {
                "nacos_enabled": status.get("nacos_enabled", False),
                "client_initialized": status.get("client_initialized", False),
                "registered": status.get("registered", False),
                "service_name": status.get("service_name"),
                "service_port": status.get("service_port"),
            }
        )

    @app.route("/api/nacos/config", methods=["GET"])
    def nacos_config():
        data_id = app.config["NACOS_CONFIG_DATA_ID"]
        try:
            # No data_id is passed: Flask-Nacos uses NACOS_CONFIG_DATA_ID.
            content = nacos.get_config()
        except FlaskNacosError as exc:
            return jsonify({"available": False, "data_id": data_id, "error": str(exc)}), 503

        if content is None:
            return (
                jsonify(
                    {
                        "available": False,
                        "data_id": data_id,
                        "error": "Nacos configuration is currently unavailable",
                    }
                ),
                503,
            )
        return jsonify({"available": True, "data_id": data_id, "content": content})

    @app.route("/api/nacos/instances", methods=["GET"])
    def nacos_instances():
        target_service = request.args.get("service") or service_name
        cluster = request.args.get("cluster") or None

        if nacos.get_client() is None:
            return (
                jsonify(
                    {
                        "available": False,
                        "service": target_service,
                        "error": "Nacos client is currently unavailable",
                    }
                ),
                503,
            )

        try:
            instances = nacos.list_instances(target_service, cluster=cluster)
        except FlaskNacosError as exc:
            return (
                jsonify(
                    {
                        "available": False,
                        "service": target_service,
                        "error": str(exc),
                    }
                ),
                503,
            )

        return jsonify(
            {
                "available": True,
                "service": target_service,
                "cluster": cluster,
                "count": len(instances),
                "instances": instances,
            }
        )

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("NACOS_SERVICE_PORT", "5000")),
    )
