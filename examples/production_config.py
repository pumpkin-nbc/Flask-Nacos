"""Production-oriented configuration for flask-nacos.

Reads sensitive and environment-specific values from environment variables
instead of hardcoding them, and configures explicit service identity and
lifecycle behavior suitable for multi-worker deployments (Gunicorn/uWSGI).

Run with, for example:

    gunicorn "production_config:create_app()" -w 4 -b 0.0.0.0:5000
"""

import os

from flask import Flask

from flask_nacos import FlaskNacos

nacos = FlaskNacos()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR", "127.0.0.1:8848"),
        NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
        # Inject credentials via environment variables; never hardcode secrets.
        NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
        NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
        # Explicit service identity is strongly recommended in production.
        NACOS_SERVICE_NAME=os.environ.get("NACOS_SERVICE_NAME", "prod-service"),
        NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP", "127.0.0.1"),
        NACOS_SERVICE_PORT=int(os.environ.get("NACOS_SERVICE_PORT", "5000")),
        # Workers sharing this IP:port map to one Nacos instance. Do not let an
        # individual worker remove that shared endpoint during graceful exit.
        NACOS_AUTO_REGISTER=True,
        NACOS_AUTO_REGISTER_ON_INIT=True,
        NACOS_REGISTER_ONCE_PER_PROCESS=True,
        NACOS_DEREGISTER_ON_EXIT=False,
        NACOS_LOG_ENABLED=os.environ.get("NACOS_LOG_ENABLED", "false"),
        NACOS_LOG_DIR=os.environ.get("NACOS_LOG_DIR", "./logs"),
        NACOS_LOG_FILENAME=os.environ.get(
            "NACOS_LOG_FILENAME", "flask_nacos.log"
        ),
        # Do not crash the app if Nacos is temporarily unavailable.
        NACOS_FAIL_FAST=False,
    )
    nacos.init_app(app)
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
