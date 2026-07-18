# Python 初学者快速开始

[English](quickstart.md) | 简体中文

这篇教程不假设你已经会 Flask、虚拟环境或 Nacos。跟着步骤操作，第一次运行不需要
Docker；确认 Python 程序正常后，再启动 Nacos，完成服务注册、配置读取、服务发现和
健康检查。

如果你已经熟悉 Flask，可以直接阅读[完整接入案例](complete-example.zh-CN.md)。

## 先认识 6 个概念

| 名称 | 可以先这样理解 |
| --- | --- |
| Flask app | 你的 Python Web 应用。 |
| Nacos client | Flask-Nacos 创建的、用于访问 Nacos 的客户端。 |
| 服务注册 | 把服务名、IP 和端口告诉 Nacos。 |
| 配置中心 | 从 Nacos 读取一段配置文本。 |
| 服务发现 | 根据服务名查询可以访问的实例。 |
| 健康检查 | 查看扩展是否启用、client 是否初始化；不是远端 Nacos 探测。 |

## 第一阶段：先让 Flask 程序运行

### 1. 检查 Python

Windows PowerShell：

```powershell
py --version
```

如果 `py` 不存在，再试：

```powershell
python --version
```

macOS / Linux：

```bash
python3 --version
```

看到 `Python 3.8` 到 `Python 3.13` 即可继续。如果命令不存在，请先从
[python.org](https://www.python.org/downloads/) 安装 Python；Windows 安装时勾选
“Add Python to PATH”。

### 2. 创建项目和虚拟环境

虚拟环境把当前项目使用的包放在独立目录中，不会影响系统里的其他 Python 项目。

Windows PowerShell：

```powershell
mkdir flask-nacos-demo
cd flask-nacos-demo
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install flask-nacos
```

如果你的电脑使用 `python` 而不是 `py`，把第三行的 `py` 换成 `python`。

macOS / Linux：

```bash
mkdir flask-nacos-demo
cd flask-nacos-demo
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install flask-nacos
```

这里直接使用虚拟环境中的 Python，不需要执行激活命令，也不会遇到 PowerShell 执行策略
阻止 `Activate.ps1` 的问题。

### 3. 创建 `app.py`

在 `flask-nacos-demo` 目录创建 `app.py`，复制下面的完整代码：

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
    NACOS_SERVER_ADDR=os.environ.get("NACOS_SERVER_ADDR", "127.0.0.1:8848"),
    NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
    NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
    NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
    NACOS_ACCESS_KEY=os.environ.get("NACOS_ACCESS_KEY"),
    NACOS_SECRET_KEY=os.environ.get("NACOS_SECRET_KEY"),
    NACOS_SERVICE_NAME=SERVICE_NAME,
    NACOS_SERVICE_IP=os.environ.get("NACOS_SERVICE_IP", "127.0.0.1"),
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
    NACOS_LOG_LEVEL=os.environ.get("NACOS_LOG_LEVEL", "INFO"),
    NACOS_FAIL_FAST=os.environ.get("NACOS_FAIL_FAST", "false"),
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

仓库源码用户也可以直接运行
[`examples/beginner_app.py`](../examples/beginner_app.py)，它与上面的代码行为一致。

### 4. 第一次运行：暂时不连接 Nacos

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe app.py
```

macOS / Linux：

```bash
.venv/bin/python app.py
```

看到 `Running on http://127.0.0.1:5000` 表示 Flask 已启动。打开：

- <http://127.0.0.1:5000/>
- <http://127.0.0.1:5000/nacos/status>
- <http://127.0.0.1:5000/health/nacos>

此时预期看到：

```json
{
  "nacos_enabled": false,
  "client_initialized": false,
  "registered": false
}
```

健康接口中的 `"status": "disabled"` 也是正确结果。这一步只证明：虚拟环境、Flask、
Flask-Nacos 和你的代码都可以正常工作。按 `Ctrl+C` 停止程序。

## 第二阶段：连接真实 Nacos

### 5. 启动本地 Nacos

先确认 Docker Desktop 已启动：

```powershell
docker --version
```

Windows PowerShell：

```powershell
docker run --name flask-nacos-beginner-nacos -e MODE=standalone -e NACOS_AUTH_ENABLE=false -p 8848:8848 -p 9848:9848 -d nacos/nacos-server:v2.3.2
```

macOS / Linux 使用相同命令：

```bash
docker run --name flask-nacos-beginner-nacos -e MODE=standalone -e NACOS_AUTH_ENABLE=false -p 8848:8848 -p 9848:9848 -d nacos/nacos-server:v2.3.2
```

第一次运行需要下载镜像，请耐心等待。使用下面命令确认容器状态：

```powershell
docker ps --filter name=flask-nacos-beginner-nacos
```

状态为 `Up` 后通常还要等待 30–60 秒，再打开 <http://127.0.0.1:8848/nacos>。如果暂时
打不开，可以运行 `docker logs flask-nacos-beginner-nacos` 查看启动进度。这个本地教学
容器关闭了认证，不能用于生产环境。

### 6. 开启 Nacos 并重新运行 Flask

Windows PowerShell：

```powershell
$env:NACOS_ENABLED = "true"
.\.venv\Scripts\python.exe app.py
```

macOS / Linux：

```bash
export NACOS_ENABLED="true"
.venv/bin/python app.py
```

再次打开 <http://127.0.0.1:5000/nacos/status>，预期关键字段为：

```json
{
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true,
  "service_name": "flask-nacos-beginner",
  "service_port": 5000
}
```

这表示 client 已创建，并且 `FlaskNacos(app)` 初始化时完成了自动注册。你也可以在 Nacos
控制台的服务列表中查找 `flask-nacos-beginner`。

打开 <http://127.0.0.1:5000/health/nacos>，此时预期为 `"status": "ok"`。这个接口只
反映扩展内部状态，并不主动请求远端 Nacos。

### 7. 发布并读取一条配置

保持 Flask 运行，另开一个 PowerShell 窗口：

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8848/nacos/v1/cs/configs" `
  -Body @{
    dataId = "flask-nacos-beginner.properties"
    group = "DEFAULT_GROUP"
    content = "greeting=hello-from-nacos"
  }
```

macOS / Linux：

```bash
curl -X POST "http://127.0.0.1:8848/nacos/v1/cs/configs" \
  --data-urlencode "dataId=flask-nacos-beginner.properties" \
  --data-urlencode "group=DEFAULT_GROUP" \
  --data-urlencode "content=greeting=hello-from-nacos"
```

返回 `true` 表示发布成功。打开 <http://127.0.0.1:5000/nacos/config>，预期看到：

```json
{
  "available": true,
  "data_id": "flask-nacos-beginner.properties",
  "content": "greeting=hello-from-nacos"
}
```

`get_config()` 返回的是原始字符串；Flask-Nacos 不会自动解析，也不会写入
`app.config`。

### 8. 发现刚才注册的服务

打开 <http://127.0.0.1:5000/nacos/instances>。等待一两秒后，预期 `count` 至少为 `1`，
并看到类似下面的实例：

```json
{
  "ip": "127.0.0.1",
  "port": 5000,
  "healthy": true
}
```

这里的服务名为 `flask-nacos-beginner`，group 为 `DEFAULT_GROUP`。返回空列表通常表示
服务名或 group 不一致、实例尚未注册完成，或者 Nacos 暂时不可用。

### 9. 停止并清理

在 Flask 窗口按 `Ctrl+C`。Python 正常退出时，Flask-Nacos 会自动注销由当前扩展注册的
实例。

Windows PowerShell、macOS 和 Linux 都可以使用：

```powershell
docker stop flask-nacos-beginner-nacos
docker rm flask-nacos-beginner-nacos
```

PowerShell 如需清除当前窗口的环境变量：

```powershell
Remove-Item Env:NACOS_ENABLED
```

Bash：

```bash
unset NACOS_ENABLED
```

## 连接已有且开启认证的 Nacos

下面两个看起来相似的地址，作用完全不同：

| 配置项 | 含义 | 谁连接它？ |
| --- | --- | --- |
| `NACOS_SERVER_ADDR` | Nacos API 地址，格式为 `host:port`。 | Flask 进程主动连接 Nacos。 |
| `NACOS_SERVICE_IP` | 注册时发布的 Flask 实例地址。 | 其他服务通过它和 `NACOS_SERVICE_PORT` 访问 Flask。 |

例如，Nacos 使用文档示例地址 `203.0.113.10:8848`，Flask 使用
`203.0.113.20:5000`，那么 server address 填 `.10:8848`，service IP 填 `.20`。
不要把 Nacos 所在机器的 IP 填到 `NACOS_SERVICE_IP`。

- 只有 Nacos、Flask 和消费者都在同一台机器时，才可以都使用 `127.0.0.1`。
- Docker 中 `NACOS_SERVER_ADDR` 可以是 `nacos:8848` 这样的容器主机名；
  `NACOS_SERVICE_IP` 仍必须是消费者能够访问的 Flask 地址。
- NAT、多网卡环境应显式选择需要发布的 Flask IP，不要依赖自动识别。

PowerShell 使用用户名/密码且不把密码写入源码：

```powershell
$credential = Get-Credential
$env:NACOS_ENABLED = "true"
$env:NACOS_SERVER_ADDR = "nacos.example.com:8848"
$env:NACOS_SERVICE_IP = "203.0.113.20"
$env:NACOS_NAMESPACE_ID = "your-namespace-id"
$env:NACOS_USERNAME = $credential.UserName
$env:NACOS_PASSWORD = $credential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe app.py
```

Bash 等价命令（密码输入时不会回显）：

```bash
export NACOS_ENABLED="true"
export NACOS_SERVER_ADDR="nacos.example.com:8848"
export NACOS_SERVICE_IP="203.0.113.20"
export NACOS_NAMESPACE_ID="your-namespace-id"
read -r -p "Nacos username: " NACOS_USERNAME
read -r -s -p "Nacos password: " NACOS_PASSWORD; echo
export NACOS_USERNAME NACOS_PASSWORD
.venv/bin/python app.py
```

`NACOS_NAMESPACE_ID` 必须填写 namespace ID，不是控制台显示名称。使用 AccessKey 认证时，
不要设置用户名/密码，改为通过同样的环境变量或密钥管理方式设置 `NACOS_ACCESS_KEY` 和
`NACOS_SECRET_KEY`。

分别测试两条网络路径。从 Flask 所在机器测试 Nacos：

```powershell
Test-NetConnection nacos.example.com -Port 8848
```

从消费者机器测试注册出去的 Flask 地址：

```powershell
Test-NetConnection 203.0.113.20 -Port 5000
```

macOS/Linux 可以使用 `nc -vz nacos.example.com 8848` 和
`nc -vz 203.0.113.20 5000`。请将所有文档示例地址替换为自己的测试环境。

如果 client 仍未初始化，可以临时设置 `NACOS_FAIL_FAST=true` 并重启 Flask，从异常中
读取准确原因；完成排查后，根据应用启动策略删除或恢复该设置。

## 常见问题速查

| 现象 | 处理方法 |
| --- | --- |
| 找不到 `py` / `python` | 安装 Python 并加入 PATH；macOS/Linux 使用 `python3`。 |
| 无法执行 `Activate.ps1` | 不需要激活；直接使用 `.venv\Scripts\python.exe`。 |
| `No module named flask_nacos` | 确认安装和运行使用的是同一个 `.venv` Python。 |
| 5000 端口被占用 | 关闭占用程序，或同时修改服务端口与 `app.run()` 端口。 |
| 8848 端口被占用 | 停止已有 Nacos，或复用已有 Nacos 并修改服务地址。 |
| 找不到 `docker` | 安装并启动 Docker Desktop；第一阶段仍然可以正常完成。 |
| `registered` 为 `false` | 确认环境变量为 `true`、容器状态为 `Up`，然后查看 Flask 日志。 |
| 配置接口返回 503 | 确认 Nacos 正在运行，并且 data ID/group 与教程完全一致。 |

更多情况见[错误排查](troubleshooting.zh-CN.md)。

## 下一步

- [完整接入案例](complete-example.zh-CN.md)：应用工厂、环境变量和全部接口。
- [配置项](configuration.zh-CN.md)：了解所有 `NACOS_*` 设置。
- [API 参考](api-reference.zh-CN.md)：查看每个公开方法的参数和返回值。
- [生产部署](production.zh-CN.md)：Gunicorn、容器、多 worker 与安全配置。
