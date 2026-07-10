"""Basic (non-factory) usage of flask-nacos."""

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    NACOS_SERVICE_NAME="basic-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_DEREGISTER=True,
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
