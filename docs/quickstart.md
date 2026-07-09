# Quickstart

English | [简体中文](quickstart.zh-CN.md)

This guide gets you from install to a running Flask app integrated with Nacos.

See also: [Configuration](configuration.md) - [API Reference](api-reference.md) -
[Service Registration](service-registration.md) -
[Service Discovery](service-discovery.md) - [Health Check](health-check.md) -
[Production](production.md) - [Troubleshooting](troubleshooting.md).

## Install

```bash
pip install flask-nacos
```

For local development (tests, linting, type checking, building):

```bash
pip install -e ".[dev]"
```

## A local Nacos for testing

You can start a local Nacos with the bundled Compose file (for local testing
only, never for production):

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

It listens on `127.0.0.1:8848` with the default demo credentials `nacos/nacos`.

## Minimal app

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
)

nacos = FlaskNacos(app)
```

After initialization the extension instance is available at
`app.extensions["nacos"]`.

## Factory mode

```python
from flask import Flask
from flask_nacos import FlaskNacos

nacos = FlaskNacos()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    nacos.init_app(app)
    return app
```

## Service registration

With `NACOS_REGISTER_ENABLED` and `NACOS_AUTO_REGISTER` both `True`, the service
registers automatically during `init_app(app)`. You can also register manually:

```python
nacos.register_instance()
```

See [Service Registration](service-registration.md) for details.

## Service discovery

```python
instances = nacos.list_instances("user-service")
instance = nacos.get_one_healthy_instance("user-service", strategy="random")
```

See [Service Discovery](service-discovery.md) for filtering and strategies.

## Health check

```python
app.config["NACOS_HEALTH_CHECK_ENABLED"] = True
app.config["NACOS_HEALTH_CHECK_PATH"] = "/health/nacos"
```

See [Health Check](health-check.md) for the response format.

## Reading configuration

```python
content = nacos.get_config("application.yaml")
```

`get_config()` returns the raw configuration content string from Nacos as-is. It
does not perform any YAML, JSON, or dict parsing, and it does not write anything
into Flask `app.config`.
