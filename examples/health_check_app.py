"""Health-check route with flask-nacos.

Enabling ``NACOS_HEALTH_CHECK_ENABLED`` auto-registers a Flask route that
reports the extension's internal state without ever calling the Nacos server.

Try it once running:

    curl http://127.0.0.1:5002/health/nacos
"""

from flask import Flask

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    NACOS_SERVICE_NAME="health-demo-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5002,
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_DEREGISTER=True,
    # Register the health-check route at the given path.
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


@app.route("/")
def index():
    return "Flask-Nacos health check demo"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002)
