"""Service discovery with flask-nacos.

Shows listing instances, filtering by cluster/metadata, and selecting a single
healthy instance with different strategies.
"""

from flask import Flask, jsonify

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    # This app only consumes discovery; it does not register itself.
    NACOS_REGISTER_ENABLED=False,
    NACOS_AUTO_REGISTER=False,
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


@app.route("/instances")
def instances():
    # All healthy instances of "user-service".
    return jsonify({"instances": nacos.list_instances("user-service")})


@app.route("/instances/canary")
def canary_instances():
    # Filter by cluster and metadata (e.g. a canary release tagged version=v2).
    return jsonify(
        {
            "instances": nacos.list_instances(
                "user-service",
                cluster="CANARY",
                metadata={"version": "v2"},
            )
        }
    )


@app.route("/one")
def one_instance():
    # Pick a single healthy instance using the "random" strategy.
    # Supported strategies: "first", "random", "weight".
    instance = nacos.get_one_healthy_instance("user-service", strategy="random")
    return jsonify({"instance": instance})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
