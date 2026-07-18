# Python Beginner Quickstart

English | [简体中文](quickstart.zh-CN.md)

This tutorial assumes no prior Flask, virtual-environment, or Nacos experience.
The first run needs only Python. After that works, you will start Nacos and try
registration, health, configuration, and discovery one step at a time.

Already comfortable with Flask? Go to the
[Complete Integration Example](complete-example.md).

## Six concepts in plain language

| Name | Beginner explanation |
| --- | --- |
| Flask app | Your Python web application. |
| Nacos client | The client Flask-Nacos creates to communicate with Nacos. |
| Registration | Telling Nacos this service's name, IP, and port. |
| Config center | Reading a piece of configuration text from Nacos. |
| Discovery | Looking up reachable instances by service name. |
| Health check | Local extension/client state; not a remote Nacos probe. |

## Stage one: run Flask without Nacos

### 1. Check Python

Windows PowerShell:

```powershell
py --version
```

If `py` is unavailable, try `python --version`. On macOS/Linux:

```bash
python3 --version
```

Continue with Python 3.8 through 3.13. If the command is missing, install Python
from [python.org](https://www.python.org/downloads/). On Windows, select
“Add Python to PATH” during installation.

### 2. Create a project and virtual environment

Windows PowerShell:

```powershell
mkdir flask-nacos-demo
cd flask-nacos-demo
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install flask-nacos
```

Use `python` instead of `py` if that is the command available on your computer.

macOS/Linux:

```bash
mkdir flask-nacos-demo
cd flask-nacos-demo
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install flask-nacos
```

These commands use the virtual environment's Python directly, so activation is
not required and PowerShell execution-policy errors are avoided.

### 3. Create `app.py`

Create `app.py` inside `flask-nacos-demo` and copy this complete program:

```python
import os

from flask import Flask, jsonify
from flask_nacos import FlaskNacos

SERVICE_NAME = "flask-nacos-beginner"
CONFIG_DATA_ID = "flask-nacos-beginner.properties"
DEFAULT_GROUP = "DEFAULT_GROUP"

app = Flask(__name__)
app.config.update(
    NACOS_ENABLED=os.environ.get("NACOS_ENABLED", "false"),
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME=SERVICE_NAME,
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_GROUP_NAME=DEFAULT_GROUP,
    NACOS_SERVICE_GROUP=DEFAULT_GROUP,
    NACOS_AUTO_REGISTER=True,
    NACOS_AUTO_DEREGISTER=True,
    NACOS_CONFIG_ENABLED=True,
    NACOS_CONFIG_DATA_ID=CONFIG_DATA_ID,
    NACOS_CONFIG_GROUP=DEFAULT_GROUP,
    NACOS_REQUEST_TIMEOUT=5.0,
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
    NACOS_FAIL_FAST=False,
)

nacos = FlaskNacos(app)


def not_ready(feature):
    if nacos.get_status()["nacos_enabled"]:
        hint = "Check that Nacos is running, then check the Flask logs."
    else:
        hint = "Start Nacos, set NACOS_ENABLED=true, and restart this app."
    return jsonify({"available": False, "feature": feature, "hint": hint}), 503


@app.route("/")
def index():
    return jsonify(
        message="Your Flask-Nacos beginner app is running.",
        nacos_enabled=nacos.get_status()["nacos_enabled"],
        next=["/nacos/status", "/health/nacos", "/nacos/config", "/nacos/instances"],
    )


@app.route("/nacos/status")
def nacos_status():
    return jsonify(nacos.get_status())


@app.route("/nacos/config")
def nacos_config():
    if nacos.get_client() is None:
        return not_ready("config")
    content = nacos.get_config()
    if content is None:
        return not_ready("config")
    return jsonify(available=True, data_id=CONFIG_DATA_ID, content=content)


@app.route("/nacos/instances")
def nacos_instances():
    if nacos.get_client() is None:
        return not_ready("discovery")
    instances = nacos.list_instances(SERVICE_NAME)
    return jsonify(
        available=True,
        service=SERVICE_NAME,
        count=len(instances),
        instances=instances,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

Repository users can instead run
[`examples/beginner_app.py`](../examples/beginner_app.py), which has the same
behavior.

### 4. First run: leave Nacos disabled

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py
```

macOS/Linux:

```bash
.venv/bin/python app.py
```

After `Running on http://127.0.0.1:5000` appears, open:

- <http://127.0.0.1:5000/>
- <http://127.0.0.1:5000/nacos/status>
- <http://127.0.0.1:5000/health/nacos>

The expected status includes:

```json
{
  "nacos_enabled": false,
  "client_initialized": false,
  "registered": false
}
```

`"status": "disabled"` from the health endpoint is also correct. This proves
that Python, Flask, Flask-Nacos, and your program work. Press `Ctrl+C` to stop it.

## Stage two: connect to Nacos

### 5. Start local Nacos

Make sure Docker Desktop is running, then check `docker --version`.

Windows PowerShell:

```powershell
docker run --name flask-nacos-beginner-nacos -e MODE=standalone -e NACOS_AUTH_ENABLE=false -p 8848:8848 -p 9848:9848 -d nacos/nacos-server:v2.3.2
```

The same command works in macOS/Linux shells:

```bash
docker run --name flask-nacos-beginner-nacos -e MODE=standalone -e NACOS_AUTH_ENABLE=false -p 8848:8848 -p 9848:9848 -d nacos/nacos-server:v2.3.2
```

The first run downloads the image. Check readiness with:

```powershell
docker ps --filter name=flask-nacos-beginner-nacos
```

After its state becomes `Up`, wait about 30–60 seconds and open
<http://127.0.0.1:8848/nacos>. If it is not ready yet, run
`docker logs flask-nacos-beginner-nacos` to inspect startup progress.
Authentication is disabled only for this learning container; never use it in
production.

### 6. Enable Nacos and run Flask again

Windows PowerShell:

```powershell
$env:NACOS_ENABLED = "true"
.\.venv\Scripts\python.exe app.py
```

macOS/Linux:

```bash
export NACOS_ENABLED="true"
.venv/bin/python app.py
```

Open <http://127.0.0.1:5000/nacos/status>. The important fields should be:

```json
{
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true,
  "service_name": "flask-nacos-beginner",
  "service_port": 5000
}
```

The client is initialized and `FlaskNacos(app)` registered the service. The
Nacos console should list `flask-nacos-beginner`. The health endpoint should now
report `"status": "ok"`; it still reports local extension state, not remote
Nacos availability.

### 7. Publish and read configuration

Keep Flask running and open another PowerShell window:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8848/nacos/v1/cs/configs" `
  -Body @{
    dataId = "flask-nacos-beginner.properties"
    group = "DEFAULT_GROUP"
    content = "greeting=hello-from-nacos"
  }
```

macOS/Linux:

```bash
curl -X POST "http://127.0.0.1:8848/nacos/v1/cs/configs" \
  --data-urlencode "dataId=flask-nacos-beginner.properties" \
  --data-urlencode "group=DEFAULT_GROUP" \
  --data-urlencode "content=greeting=hello-from-nacos"
```

After `true` is returned, open <http://127.0.0.1:5000/nacos/config>. Expect:

```json
{
  "available": true,
  "data_id": "flask-nacos-beginner.properties",
  "content": "greeting=hello-from-nacos"
}
```

`get_config()` returns the raw string. Flask-Nacos does not parse it or write it
into `app.config`.

### 8. Discover the registered service

Open <http://127.0.0.1:5000/nacos/instances>. After a second or two, `count`
should be at least `1`, with an instance like:

```json
{
  "ip": "127.0.0.1",
  "port": 5000,
  "healthy": true
}
```

The service is `flask-nacos-beginner` in `DEFAULT_GROUP`. An empty list usually
means the service/group differs, registration is not visible yet, or Nacos is
temporarily unavailable.

### 9. Stop and clean up

Press `Ctrl+C` in the Flask window. On normal Python shutdown, Flask-Nacos
deregisters the instance registered by this extension.

All platforms:

```powershell
docker stop flask-nacos-beginner-nacos
docker rm flask-nacos-beginner-nacos
```

Clear the PowerShell variable with `Remove-Item Env:NACOS_ENABLED`, or use
`unset NACOS_ENABLED` in Bash.

## Quick troubleshooting

| Symptom | Fix |
| --- | --- |
| `py` / `python` not found | Install Python and add it to PATH; use `python3` on macOS/Linux. |
| `Activate.ps1` is blocked | Do not activate; run `.venv\Scripts\python.exe` directly. |
| `No module named flask_nacos` | Install and run with the same `.venv` Python. |
| Port 5000 is occupied | Stop its current process, or change both configured and Flask ports. |
| Port 8848 is occupied | Stop the existing Nacos or connect to it instead. |
| `docker` not found | Install/start Docker Desktop; stage one still works without it. |
| `registered` is `false` | Check the environment variable, container state, and Flask logs. |
| Config endpoint returns 503 | Check Nacos and ensure data ID/group exactly match the tutorial. |

See [Troubleshooting](troubleshooting.md) for more cases.

## Next steps

- [Complete Integration Example](complete-example.md): factory mode and env vars.
- [Configuration](configuration.md): every `NACOS_*` setting.
- [API Reference](api-reference.md): public method parameters and returns.
- [Production](production.md): Gunicorn, containers, workers, and security.
