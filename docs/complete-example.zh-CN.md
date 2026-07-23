# Flask 完整接入案例

[English](complete-example.md) | 简体中文

本指南使用应用工厂示例，从启动本地 Nacos 开始，完整验证服务注册、配置读取、服务发现、
健康检查和运行状态。完整源码位于
[`examples/complete_factory_app.py`](../examples/complete_factory_app.py)。

另请参阅：[快速开始](quickstart.zh-CN.md) - [配置项](configuration.zh-CN.md) -
[API 参考](api-reference.zh-CN.md) - [生产部署](production.zh-CN.md)。

## 1. 安装

安装已发布的软件包：

```bash
python -m pip install flask-nacos
```

从仓库源码运行时，改用可编辑安装：

```bash
python -m pip install -e .
```

示例只使用软件包安装的 Flask、Flask-Nacos 和同步 Nacos SDK 2.x，不需要 dotenv，
也不需要 YAML 解析器。

## 2. 启动本地 Nacos

仓库自带的 Compose 文件会启动一个仅用于本地测试的单机 Nacos 2.x：

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

等待容器就绪后打开 <http://127.0.0.1:8848/nacos>。该开发配置关闭了认证，切勿直接
用于生产环境。

## 3. 发布测试配置

示例默认读取 `DEFAULT_GROUP` 下的 `flask-nacos-demo.properties`。通过 Nacos OpenAPI
发布一份测试内容。

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

发布成功时返回 `true`。

## 4. 配置 Flask 服务

默认值可直接连接仓库自带的本地 Nacos。通过环境变量可以让同一份代码连接其他环境，
同时避免在源码中硬编码凭据。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `NACOS_SERVER_ADDR` | `127.0.0.1:8848` | Nacos 服务地址。 |
| `NACOS_NAMESPACE_ID` | 空 | 命名空间 ID。 |
| `NACOS_USERNAME` / `NACOS_PASSWORD` | 空 | 用户名/密码认证。 |
| `NACOS_ACCESS_KEY` / `NACOS_SECRET_KEY` | 空 | AccessKey 认证。 |
| `NACOS_SERVICE_NAME` | `flask-nacos-complete-demo` | 注册的服务名。 |
| `NACOS_SERVICE_IP` | `127.0.0.1` | 向消费者发布的地址。 |
| `NACOS_SERVICE_PORT` | `5000` | 发布端口及本地开发端口。 |
| `NACOS_SERVICE_GROUP` | `DEFAULT_GROUP` | 服务注册及默认发现 group。 |
| `NACOS_CONFIG_DATA_ID` | `flask-nacos-demo.properties` | 默认配置 data ID。 |
| `NACOS_CONFIG_GROUP` | `DEFAULT_GROUP` | 配置 group。 |
| `NACOS_REQUEST_TIMEOUT` | `5.0` | 配置读取超时秒数。 |
| `FLASK_HOST` | `127.0.0.1` | 本地开发监听地址。 |

`NACOS_SERVER_ADDR` 是当前 Flask 进程查找 Nacos 的地址，`NACOS_SERVICE_IP` 是注册给
消费者访问 Flask 的地址。例如 Nacos 位于 `203.0.113.10:8848`、Flask 位于
`203.0.113.20:5000` 时，应分别配置这两个值；Nacos 地址不是服务注册 IP。

Bash 配置示例：

```bash
export NACOS_SERVER_ADDR="127.0.0.1:8848"
export NACOS_SERVICE_NAME="flask-nacos-complete-demo"
export NACOS_SERVICE_IP="127.0.0.1"
export NACOS_SERVICE_PORT="5000"
export NACOS_CONFIG_DATA_ID="flask-nacos-demo.properties"
```

等价的 PowerShell 配置：

```powershell
$env:NACOS_SERVER_ADDR = "127.0.0.1:8848"
$env:NACOS_SERVICE_NAME = "flask-nacos-complete-demo"
$env:NACOS_SERVICE_IP = "127.0.0.1"
$env:NACOS_SERVICE_PORT = "5000"
$env:NACOS_CONFIG_DATA_ID = "flask-nacos-demo.properties"
```

如果 Nacos 开启认证，只通过环境变量或密钥管理服务注入凭据，切勿将真实凭据提交到
应用配置中。
请填写 namespace ID，而不是控制台显示名称。用户名/密码流程见
[快速开始](quickstart.zh-CN.md#连接已有且开启认证的-nacos)；使用 AK/SK 时改为设置
`NACOS_ACCESS_KEY` 与 `NACOS_SECRET_KEY`。

### 接入现有 Flask 扩展管理模块

如果应用已经在 `app/extensions.py` 中集中管理 Flask 扩展，可以把 Flask-Nacos 放入
同一个模块。导入模块时只创建扩展对象，等到 `extension_config(app)` 执行时再绑定应用：

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

初始化扩展前必须先加载所选的 Flask 配置，确保 Nacos client 和自动注册读取到最终的
服务名、IP、端口、namespace 与认证配置；完成扩展初始化后再注册 Blueprint 和 API：

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

业务模块像导入其他 Flask 扩展一样导入全局 `nacos` 对象。请求处理中调用时，扩展会
自动选择当前 Flask 应用：

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

状态路由使用字段白名单。不要在公开 API 中返回完整的 `get_status()` 映射，因为其中包含
Nacos 地址、namespace、服务 IP 和进程标识等部署信息。

Celery task、工作线程和独立脚本必须进入对应的 `app.app_context()`，除非现有集成已经
自动提供应用上下文。`app.extensions["nacos"]` 保存的是包含 `config` 和 `client` 的
内部状态映射，并不是 `FlaskNacos` 对象；业务代码应按上例从 `app.extensions` 模块导入
全局 `nacos`。

Nacos 配置应放在 Flask 配置类或环境变量中，不要写入 `app/extensions.py`。
`NACOS_SERVICE_IP` 仍然可选：启用自动注册且未设置该值时，Flask-Nacos 会尝试自动识别
本机 IP。如果应用只读取配置或发现其他服务，可以关闭自动注册并省略注册标识：

```python
NACOS_REGISTER_ENABLED = False
NACOS_AUTO_REGISTER = False
```

## 5. 运行应用

```bash
python examples/complete_factory_app.py
```

`create_app()` 执行时，Flask-Nacos 会创建 SDK client、注册服务并安装
`/health/nacos`。同一进程中的注册是幂等的。进程正常退出时，退出处理器只会注销由
当前应用成功注册的实例。

示例特意设置 `NACOS_FAIL_FAST=False`：Nacos 暂时不可用时不会阻止 Flask 启动；依赖
Nacos 的示例接口会返回安全响应，不会暴露凭据或 SDK traceback。

## 6. 验证全部接入点

应用首页与接口列表：

```bash
curl http://127.0.0.1:5000/
```

不请求 Nacos 的扩展内部状态：

```bash
curl http://127.0.0.1:5000/api/nacos/status
```

Flask-Nacos 安装的健康检查路由：

```bash
curl http://127.0.0.1:5000/health/nacos
```

该健康路由反映 client 初始化状态，并不是对远端 Nacos 服务的探测。

读取默认 data ID。接口调用 `nacos.get_config()` 时没有传 data ID，因此会使用
`NACOS_CONFIG_DATA_ID`：

```bash
curl http://127.0.0.1:5000/api/nacos/config
```

发现当前服务，或指定其他服务与 cluster：

```bash
curl http://127.0.0.1:5000/api/nacos/instances
curl "http://127.0.0.1:5000/api/nacos/instances?service=user-service&cluster=CANARY"
```

空实例列表是合法的发现结果。关闭 fail-fast 时，SDK 发现失败也会使用库的安全返回值
`[]`；如果运维上必须区分“服务为空”和“Nacos 故障”，应同时查看日志与外部监控。

按 `Ctrl+C` 停止开发服务器。解释器正常退出时会注销已注册实例。随后可以停止本地
Nacos：

```bash
docker compose -f examples/docker-compose-nacos.yml down
```

## 7. 生产环境与多 worker 部署

在支持 Gunicorn 的平台上运行应用工厂：

```bash
export NACOS_DEREGISTER_ON_EXIT="false"
gunicorn "examples.complete_factory_app:create_app()" -w 4 -b 0.0.0.0:5000
```

每个 worker 都会执行 `create_app()`。`NACOS_REGISTER_ONCE_PER_PROCESS=True` 保证单个
worker 内不会重复执行 SDK 注册，fork 后也会重建进程锁。共享同一 IP 和端口的 worker
在 Nacos 中对应同一个实例标识，而不是每个 worker 一个实例。请为该共享端点设置
`NACOS_DEREGISTER_ON_EXIT=False`，或由单一外部协调者负责注册与注销。

SDK 原生日志可能包含敏感请求或配置数据，因此始终静默。`NACOS_LOG_*` 只控制 Flask-Nacos
安全日志；默认既不创建 `~/logs/nacos`，也不创建日志文件。设置
`NACOS_LOG_ENABLED=True` 后默认写入 `./logs/flask_nacos.log`，可分别通过
`NACOS_LOG_DIR` 与 `NACOS_LOG_FILENAME` 覆盖目录和文件名。

同步 SDK 2.x client 没有提供可靠的 HTTPS 证书校验控制。生产 HTTPS 部署应使用受信网络，
或通过能够校验证书的 TLS 代理 / sidecar 连接。

生产环境中还应：

- 发布消费者能够访问的 IP 或 DNS 地址，不要使用 `127.0.0.1`；
- 使用密钥管理服务保存凭据，并开启 Nacos 认证；
- 根据应用启动策略选择 fail-fast 和重试配置；
- 需要判断远端可用性时，使用真正执行 Nacos 操作的 readiness/监控；
- 不要使用仓库自带的单机 Compose 配置。

## 8. 可选的真实认证测试

普通测试套件不会访问外部服务。如需验证专用、非生产的用户名/密码认证 Nacos，需要
显式开启集成测试。测试会在 `FLASK_NACOS_TEST` group 创建唯一临时配置，通过
Flask-Nacos 读取，并在清理阶段删除，因此测试账号需要配置读写权限。

PowerShell：

```powershell
$credential = Get-Credential
$env:FLASK_NACOS_RUN_AUTH_INTEGRATION = "1"
$env:FLASK_NACOS_TEST_SERVER_ADDR = "nacos.example.com:8848"
$env:FLASK_NACOS_TEST_NAMESPACE_ID = "your-namespace-id"
$env:FLASK_NACOS_TEST_USERNAME = $credential.UserName
$env:FLASK_NACOS_TEST_PASSWORD = $credential.GetNetworkCredential().Password
python -m pytest tests/test_authenticated_integration.py -q
```

Bash：

```bash
export FLASK_NACOS_RUN_AUTH_INTEGRATION="1"
export FLASK_NACOS_TEST_SERVER_ADDR="nacos.example.com:8848"
export FLASK_NACOS_TEST_NAMESPACE_ID="your-namespace-id"
read -r -p "Nacos username: " FLASK_NACOS_TEST_USERNAME
read -r -s -p "Nacos password: " FLASK_NACOS_TEST_PASSWORD; echo
export FLASK_NACOS_TEST_USERNAME FLASK_NACOS_TEST_PASSWORD
python -m pytest tests/test_authenticated_integration.py -q
```

没有开启标志或缺少必需环境变量时，该测试会显示为 skipped。
