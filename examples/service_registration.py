"""Service registration with flask-nacos.

Shows automatic registration during init_app, manual register/deregister, and
the once-per-process behavior. Run against a local Nacos (see
examples/docker-compose-nacos.yml).
"""

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    NACOS_SERVICE_NAME="registration-demo",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    # Auto-register on init_app (default). Set to False to register manually.
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_REGISTER_ON_INIT=True,
    NACOS_AUTO_DEREGISTER=True,
    # With once-per-process True, repeat register_instance() calls are no-ops
    # within the same process.
    NACOS_REGISTER_ONCE_PER_PROCESS=True,
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


@app.route("/register", methods=["POST"])
def register():
    # Idempotent: calling this repeatedly in the same process is a no-op.
    ok = nacos.register_instance()
    return jsonify({"registered": ok})


@app.route("/deregister", methods=["POST"])
def deregister():
    ok = nacos.deregister_instance()
    return jsonify({"deregistered": ok})


@app.route("/status")
def status():
    return jsonify(nacos.get_status())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
