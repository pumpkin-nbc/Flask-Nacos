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
gunicorn "examples.complete_factory_app:create_app()" -w 4 -b 0.0.0.0:5000
```

每个 worker 都会执行 `create_app()`。`NACOS_REGISTER_ONCE_PER_PROCESS=True` 保证单个
worker 内不会重复执行 SDK 注册，fork 后也会重建进程锁。共享同一 IP 和端口的 worker
在 Nacos 中对应同一个实例标识；如果单个 worker 独立重启时不能注销这个共享端点，
需要在部署层统一协调注册与注销。

生产环境中还应：

- 发布消费者能够访问的 IP 或 DNS 地址，不要使用 `127.0.0.1`；
- 使用密钥管理服务保存凭据，并开启 Nacos 认证；
- 根据应用启动策略选择 fail-fast 和重试配置；
- 需要判断远端可用性时，使用真正执行 Nacos 操作的 readiness/监控；
- 不要使用仓库自带的单机 Compose 配置。
