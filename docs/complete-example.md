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
gunicorn "examples.complete_factory_app:create_app()" -w 4 -b 0.0.0.0:5000
```

Each worker executes `create_app()`. `NACOS_REGISTER_ONCE_PER_PROCESS=True`
prevents repeated SDK registration in one worker, and the process-aware lock is
recreated after a fork. Workers sharing one IP and port advertise the same Nacos
instance identity, so coordinate registration and deregistration at the
deployment level if independently restarting one worker must not remove that
shared endpoint.

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
