# Complete Flask Integration Example

English | [简体中文](complete-example.zh-CN.md)

This guide runs the application-factory example from a local Nacos server to
service registration, configuration reads, discovery, health checks, and
runtime status. The complete source is
[`examples/complete_factory_app.py`](../examples/complete_factory_app.py).

See also: [Quickstart](quickstart.md) - [Configuration](configuration.md) -
[API Reference](api-reference.md) - [Production](production.md).

## 1. Install

Install the released package:

```bash
python -m pip install flask-nacos
```

When running from a repository checkout, install it in editable mode instead:

```bash
python -m pip install -e .
```

The example uses only Flask, Flask-Nacos, and the synchronous Nacos SDK 2.x
installed by the package. It does not require dotenv or a YAML parser.

## 2. Start a local Nacos server

The bundled Compose file starts a standalone Nacos 2.x server for local testing:

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

Wait until the container is ready, then open
<http://127.0.0.1:8848/nacos>. The bundled development configuration disables
authentication; do not reuse it in production.

## 3. Publish a test configuration

The example reads `flask-nacos-demo.properties` from `DEFAULT_GROUP` by default.
Publish a value through the Nacos OpenAPI.

### Bash

```bash
curl -X POST "http://127.0.0.1:8848/nacos/v1/cs/configs" \
  --data-urlencode "dataId=flask-nacos-demo.properties" \
  --data-urlencode "group=DEFAULT_GROUP" \
  --data-urlencode $'content=greeting=hello-from-nacos\nfeature.enabled=true'
```

### PowerShell

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8848/nacos/v1/cs/configs" `
  -Body @{
    dataId = "flask-nacos-demo.properties"
    group = "DEFAULT_GROUP"
    content = "greeting=hello-from-nacos`nfeature.enabled=true"
  }
```

A successful publication returns `true`.

## 4. Configure the Flask service

The defaults work with the bundled local server. Environment variables let the
same code target another Nacos deployment without hardcoding credentials.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `NACOS_SERVER_ADDR` | `127.0.0.1:8848` | Nacos server address. |
| `NACOS_NAMESPACE_ID` | empty | Namespace ID. |
| `NACOS_USERNAME` / `NACOS_PASSWORD` | empty | Username/password authentication. |
| `NACOS_ACCESS_KEY` / `NACOS_SECRET_KEY` | empty | Access-key authentication. |
| `NACOS_SERVICE_NAME` | `flask-nacos-complete-demo` | Registered service name. |
| `NACOS_SERVICE_IP` | `127.0.0.1` | Address advertised to consumers. |
| `NACOS_SERVICE_PORT` | `5000` | Advertised and local development port. |
| `NACOS_SERVICE_GROUP` | `DEFAULT_GROUP` | Registration and default discovery group. |
| `NACOS_CONFIG_DATA_ID` | `flask-nacos-demo.properties` | Default config data ID. |
| `NACOS_CONFIG_GROUP` | `DEFAULT_GROUP` | Config group. |
| `NACOS_REQUEST_TIMEOUT` | `5.0` | Config-read timeout in seconds. |
| `FLASK_HOST` | `127.0.0.1` | Local development bind address. |

`NACOS_SERVER_ADDR` is where this Flask process finds Nacos.
`NACOS_SERVICE_IP` is the Flask address advertised to consumers. For example,
with Nacos at `203.0.113.10:8848` and Flask at `203.0.113.20:5000`, configure
those values separately. The server address is not the registered service IP.

Example Bash configuration:

```bash
export NACOS_SERVER_ADDR="127.0.0.1:8848"
export NACOS_SERVICE_NAME="flask-nacos-complete-demo"
export NACOS_SERVICE_IP="127.0.0.1"
export NACOS_SERVICE_PORT="5000"
export NACOS_CONFIG_DATA_ID="flask-nacos-demo.properties"
```

Equivalent PowerShell configuration:

```powershell
$env:NACOS_SERVER_ADDR = "127.0.0.1:8848"
$env:NACOS_SERVICE_NAME = "flask-nacos-complete-demo"
$env:NACOS_SERVICE_IP = "127.0.0.1"
$env:NACOS_SERVICE_PORT = "5000"
$env:NACOS_CONFIG_DATA_ID = "flask-nacos-demo.properties"
```

Set credentials only through your environment or secret manager when the Nacos
server requires them. Never commit real credentials to application config.
Use the namespace ID rather than its display name. The username/password flow
is shown in the [Quickstart](quickstart.md#connecting-to-an-existing-authenticated-nacos);
AK/SK can be supplied with `NACOS_ACCESS_KEY` and `NACOS_SECRET_KEY` instead.

### Integrate with an existing Flask extension registry

If the application already keeps Flask extensions in `app/extensions.py`, add
Flask-Nacos to the same module. Create the extension object at import time, but
do not connect it to an application until `extension_config(app)` runs:

```python
# app/extensions.py
from flask_nacos import FlaskNacos

nacos = FlaskNacos()


def extension_config(app):
    """Initialize all Flask extensions for this application."""
    # db.init_app(app)
    # redis_client.init_app(app)
    nacos.init_app(app)
```

Load the selected Flask configuration before initializing extensions. This
ensures the Nacos client and automatic registration see the final service name,
IP, port, namespace, and authentication settings. Register blueprints and APIs
afterwards:

```python
# app/app.py
from flask import Flask

from app.extensions import extension_config
from app.routes import api


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)
    extension_config(app)
    app.register_blueprint(api)
    return app
```

Business modules import the global `nacos` extension object just as they import
other Flask extensions. Calls made by a request automatically select the current
Flask application:

```python
# app/routes.py
from flask import Blueprint, current_app, jsonify

from app.extensions import nacos

api = Blueprint("api", __name__)


@api.route("/nacos/status", methods=["GET"])
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


@api.route("/nacos/config", methods=["GET"])
def nacos_config():
    return jsonify({"content": nacos.get_config()})


@api.route("/nacos/instances", methods=["GET"])
def nacos_instances():
    service_name = current_app.config["NACOS_SERVICE_NAME"]
    return jsonify({"instances": nacos.list_instances(service_name)})


def read_config_in_background(app):
    with app.app_context():
        return nacos.get_config()
```

The status route uses a field allowlist. Do not return the complete
`get_status()` mapping from a public API because it contains deployment details
such as the Nacos address, namespace, service IP, and process identifiers.

Celery tasks, worker threads, and standalone scripts need the corresponding
`app.app_context()` unless their integration already supplies one. The
`app.extensions["nacos"]` entry is an internal state mapping containing
`config` and `client`; it is not the `FlaskNacos` object. Application code should
import `nacos` from `app.extensions` as shown above.

Keep Nacos values in the Flask configuration class or environment variables,
not in `app/extensions.py`. `NACOS_SERVICE_IP` remains optional: when automatic
registration is enabled and it is unset, Flask-Nacos attempts local IP
detection. If the application only reads configuration or discovers other
services, disable automatic registration and omit the registration identity:

```python
NACOS_REGISTER_ENABLED = False
NACOS_AUTO_REGISTER = False
```

## 5. Run the application

```bash
python examples/complete_factory_app.py
```

During `create_app()` Flask-Nacos creates the SDK client, registers the service,
and installs `/health/nacos`. Registration is idempotent in the current process.
The exit handler deregisters only an instance successfully registered by this
application when the process exits normally.

The example deliberately uses `NACOS_FAIL_FAST=False`: a temporary Nacos outage
does not prevent Flask from starting. Nacos-dependent example endpoints return
a safe response instead of exposing credentials or an SDK traceback.

## 6. Verify every integration point

Application index and endpoint list:

```bash
curl http://127.0.0.1:5000/
```

Internal extension status, without a Nacos network call:

```bash
curl http://127.0.0.1:5000/api/nacos/status
```

Health route installed by Flask-Nacos:

```bash
curl http://127.0.0.1:5000/health/nacos
```

The health route reports client initialization state; it is not a remote Nacos
server probe.

Read the default config data ID. The route calls `nacos.get_config()` without a
data ID so `NACOS_CONFIG_DATA_ID` is used:

```bash
curl http://127.0.0.1:5000/api/nacos/config
```

Discover the current service or select another service and cluster:

```bash
curl http://127.0.0.1:5000/api/nacos/instances
curl "http://127.0.0.1:5000/api/nacos/instances?service=user-service&cluster=CANARY"
```

An empty instance list is a valid discovery result. With fail-fast disabled,
SDK discovery failures also use the library's safe `[]` fallback; use logs and
external monitoring when distinguishing an outage from an empty service is
operationally important.

Stop the development server with `Ctrl+C`. On graceful interpreter shutdown the
registered instance is deregistered. You can then stop local Nacos:

```bash
docker compose -f examples/docker-compose-nacos.yml down
```

## 7. Production and multi-worker deployment

Run the factory with Gunicorn on platforms where Gunicorn is supported:

```bash
export NACOS_DEREGISTER_ON_EXIT="false"
gunicorn "examples.complete_factory_app:create_app()" -w 4 -b 0.0.0.0:5000
```

Each worker executes `create_app()`. `NACOS_REGISTER_ONCE_PER_PROCESS=True`
prevents repeated SDK registration in one worker, and the process-aware lock is
recreated after a fork. Workers sharing one IP and port advertise the same Nacos
instance identity, not one instance per worker. Set
`NACOS_DEREGISTER_ON_EXIT=False` for that shared endpoint, or use one external
coordinator to own registration and deregistration.

Native SDK logging is always silent because it may include sensitive request or
configuration data. `NACOS_LOG_*` controls only Flask-Nacos safety logs; by
default neither `~/logs/nacos` nor a log file is created. Enable logging with
`NACOS_LOG_ENABLED=True`; console and rotating-file output are then enabled by
default. The file defaults to `./logs/flask-nacos.log`, and
`NACOS_LOG_PATH`/`NACOS_LOG_FILENAME` can override both parts.

The synchronous SDK 2.x client does not provide reliable HTTPS certificate-
verification controls. Production HTTPS deployments should use a trusted
network or a certificate-validating TLS proxy/sidecar.

For production:

- advertise an IP or DNS endpoint reachable by consumers, not `127.0.0.1`;
- store credentials in a secret manager and enable Nacos authentication;
- choose fail-fast and retry settings according to application startup policy;
- use readiness/monitoring that checks actual Nacos-dependent operations when
  remote availability matters;
- do not use the bundled standalone Compose configuration.

## 8. Optional real authentication test

The normal test suite never contacts an external service. To verify a dedicated,
non-production username/password-protected Nacos, explicitly enable the opt-in
test. It creates a uniquely named temporary config in `FLASK_NACOS_TEST`, reads
it through Flask-Nacos, and removes it in cleanup. The account therefore needs
config read/write permission.

PowerShell:

```powershell
$credential = Get-Credential
$env:FLASK_NACOS_RUN_AUTH_INTEGRATION = "1"
$env:FLASK_NACOS_TEST_SERVER_ADDR = "nacos.example.com:8848"
$env:FLASK_NACOS_TEST_NAMESPACE_ID = "your-namespace-id"
$env:FLASK_NACOS_TEST_USERNAME = $credential.UserName
$env:FLASK_NACOS_TEST_PASSWORD = $credential.GetNetworkCredential().Password
python -m pytest tests/test_authenticated_integration.py -q
```

Bash:

```bash
export FLASK_NACOS_RUN_AUTH_INTEGRATION="1"
export FLASK_NACOS_TEST_SERVER_ADDR="nacos.example.com:8848"
export FLASK_NACOS_TEST_NAMESPACE_ID="your-namespace-id"
read -r -p "Nacos username: " FLASK_NACOS_TEST_USERNAME
read -r -s -p "Nacos password: " FLASK_NACOS_TEST_PASSWORD; echo
export FLASK_NACOS_TEST_USERNAME FLASK_NACOS_TEST_PASSWORD
python -m pytest tests/test_authenticated_integration.py -q
```

Without the enable flag or required variables, this test is reported as skipped.
