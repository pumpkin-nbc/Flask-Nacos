"""Application factory usage of flask-nacos."""

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

nacos = FlaskNacos()


def create_app():
    app = Flask(__name__)
    app.config.update(
        NACOS_SERVER_ADDR="127.0.0.1:8848",
        NACOS_USERNAME="nacos",
        NACOS_PASSWORD="nacos",
        NACOS_SERVICE_NAME="fund-service",
        NACOS_SERVICE_IP="127.0.0.1",
        NACOS_SERVICE_PORT=5000,
        NACOS_AUTO_REGISTER=True,
        NACOS_AUTO_DEREGISTER=True,
        NACOS_FAIL_FAST=False,
    )

    nacos.init_app(app)

    @app.route("/")
    def index():
        return "Hello Flask-Nacos"

    @app.route("/config")
    def config():
        content = nacos.get_config("application.properties")
        return content or ""

    @app.route("/instances")
    def instances():
        return jsonify({"instances": nacos.list_instances("user-service")})

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
