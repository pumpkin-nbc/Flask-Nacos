# Flask-Nacos

[English](README.md) | 简体中文

Flask-Nacos 为 Flask 提供 Nacos 服务注册、服务发现与配置中心接入。1.1.0 使用目标状态
生命周期、按 app/PID 惰性创建 Client，并严格隔离多个 Flask 应用。

## 新手从这里开始

- [初学者快速开始](docs/quickstart.zh-CN.md)
- [完整应用工厂案例](docs/complete-example.zh-CN.md)
- [配置项参考](docs/configuration.zh-CN.md)
- [API 参考](docs/api-reference.zh-CN.md)
- [服务注册生命周期](docs/service-registration.zh-CN.md)
- [服务发现](docs/service-discovery.zh-CN.md)
- [健康检查](docs/health-check.zh-CN.md)
- [生产部署](docs/production.zh-CN.md)
- [错误排查](docs/troubleshooting.zh-CN.md)
- [兼容性矩阵](docs/compatibility.zh-CN.md)
- [更新日志](CHANGELOG.zh-CN.md)

## 功能特性

- 支持普通 Flask 模式与应用工厂。
- 使用准确缓存身份完成 Naming 注册与注销。
- 临时实例心跳交由 Nacos SDK 2.x 维护。
- 标准化发现结果、cluster/metadata 过滤与 first/random/weight 选择。
- 配置中心原始文本读取与请求超时。
- 最后命令优先的目标状态注册生命周期。
- 每个 app/PID Runtime 同时最多一个 Lifecycle Worker 与一笔 Naming RPC。
- Client 惰性创建；初始化、状态与健康检查无 SDK 副作用。
- fork 后 PID Runtime整体重建，并严格隔离多应用上下文。
- 脱敏彩色控制台日志与可选轮转文件日志。
- Python 3.8 语法、类型标记和双语文档。

## 兼容性

- Python `>=3.8`，CI 验证 Python 3.8–3.14。
- Flask `>=1.0`，CI 验证 Flask 1.0.x–3.1.x 的有效组合。
- `nacos-sdk-python>=2.0.0,<3.0.0`。

Python 3.8 单独验证 Flask 1.0.4、1.1.4、2.x 与 3.0.x。Flask 3.1 要求更高版本
Python，因此不声明上游不支持的组合。

## 安装

```bash
python -m pip install flask-nacos
```

从正式 PyPI 安装 `flask-nacos` 会自动安装兼容的 `nacos-sdk-python`。从 TestPyPI 验证时，
由于 TestPyPI 不是完整镜像，需要让依赖回退到正式 PyPI：

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos==1.1.0
```

## 快速开始

```python
from flask import Flask

from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME="orders-api",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_HEALTH_CHECK_ENABLED=True,
)

nacos = FlaskNacos(app)
```

默认自动注册流程：

```text
init_app(app)
  -> 校验确定性配置
  -> 提交不含 Client 的 PID Runtime
  -> 调用 register_instance(app)
  -> daemon Worker创建 Client并执行 Naming I/O，初始化线程直接返回
```

`NACOS_AUTO_REGISTER`（默认 `True`）是唯一的自动注册开关。`NACOS_ENABLED` 与
`NACOS_AUTO_REGISTER` 同时开启时执行自动注册；关闭自动注册不影响显式调用
`register_instance(app)`。

## 应用工厂

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

必须先加载配置再调用 `init_app(app)`。未显式传 app 的调用必须处于对应 Flask app/request
context；Flask-Nacos 不再回退到第一个或最近初始化的应用。

## 注册生命周期

公开生命周期 API 保持精炼：

```python
nacos.register_instance(app)        # 立即返回 None
removed = nacos.deregister_instance(app)
status = nacos.get_status(app)
client = nacos.get_client(app)
```

`register_instance(app=None) -> None` 将最终目标设为已注册，并最多发布一个 daemon收敛
Worker。Client 构造、网络重试、Naming RPC 与 SDK 心跳启动都不会延迟调用方。

`deregister_instance(app=None) -> bool` 将最终目标设为未注册。幂等/接受/成功清理，或新的
注册命令使 RPC 不再需要时返回 `True`；清理仍有必要但失败时返回 `False`。

Worker持续读取最新目标，因此 register → deregister → register 最终服从最后一次 register；
旧命令不会永久覆盖它。注册、普通注销、补偿注销与退出注销共享同一 Naming single-flight
锁。

注册成功会缓存 SDK 实际使用的 service/group/cluster/IP/port，所有注销都使用该准确身份，
绝不猜测替代 IP。临时实例注册成功后心跳归 SDK所有，Flask-Nacos Worker随即退出。

完整说明见[生命周期流程图与新旧调度对照](docs/service-registration.zh-CN.md)。

## 确定性校验与重试

启用自动注册时，`init_app(app)` 会在创建扩展状态前校验 `NACOS_SERVICE_NAME`、端口、权重、
metadata、ephemeral/心跳、认证与重试配置。

关闭自动注册时，初始化会跳过仅服务于注册的校验。首次显式调用
`register_instance(app)` 时才执行并缓存纯本地确定性校验；该过程不创建 Client，也不执行
网络 I/O。

- `NACOS_FAIL_FAST=True`：确定性自动注册错误在提交 `app.extensions["nacos"]` 前抛出。
- `NACOS_FAIL_FAST=False`：保留可用扩展状态与安全错误，不启动无效 Worker。

`NACOS_FAIL_FAST` 不会把生命周期运行时失败变成同步注册异常。Thread 创建/启动、Client
创建、超时、连接与 SDK失败只以安全类型/错误码写入 `last_error`。

注册生命周期失败会立即、保守地分类：

- 配置、认证、权限、参数或内部不变量等确定性失败会立即结束 Worker；
- 无法可靠判断的失败只使用现有有限重试预算；
- 有结构化证据确认的瞬时传输故障先使用相同有限预算，耗尽后进入低频、可中断、带有界
  退避与抖动的生命周期自恢复，直到目标变化、进程退出、后续失败不再属于瞬时故障，或注册成功。

`NACOS_RETRY_ENABLED=False` 会同时关闭有限重试和生命周期自恢复。自恢复仅处理已确认的
瞬时故障，也不轮询远端状态；`registered == target_registered` 后 Worker立即退出，心跳与
连接维护仍完全由 Nacos SDK负责。

`NACOS_RETRY_TIMES` 必须是 `>=1` 的整数；`NACOS_RETRY_INTERVAL` 必须是 `>=0` 的有限
数字；配置中心开启时 `NACOS_REQUEST_TIMEOUT` 必须是 `>0` 的有限数字。支持数字字符串，
拒绝布尔值、NaN、Infinity、小数尝试次数和越界值。

## 本地状态

`get_status(app=None)` 固定返回 12 个本地字段：

```python
{
    "enabled": True,
    "pid": 12345,
    "client_created": True,
    "service_name": "orders-api",
    "group_name": "DEFAULT_GROUP",
    "cluster_name": "DEFAULT",
    "service_ip": "203.0.113.20",
    "service_port": 5000,
    "target_registered": True,
    "registered": True,
    "operation_running": False,
    "last_error": None,
}
```

`registered` 是最近一次 Naming RPC 成功确认的本地事实，不是实时 Nacos 查询。状态读取不
创建 Client、不访问 Nacos、不探测 IP、不启动线程，也不恢复 fork 后注册。

`get_client(app)` 显式创建或返回 app/PID Client，失败时抛出安全 `FlaskNacosError`。
`.client` 属性只读缓存，并要求当前 Flask context。

## 健康检查

```python
NACOS_HEALTH_CHECK_ENABLED = True
NACOS_HEALTH_CHECK_PATH = "/health/nacos"
```

固定返回 `status`、`enabled`、`client_created`、`target_registered`、`registered`、
`operation_running` 与 `last_error`。`status=ok` 只表示本地生命周期已收敛或正在无错误地
收敛，不是远端 Nacos 或心跳探测，也不会创建 Client。

## 服务发现

```python
with app.app_context():
    instances = nacos.list_instances("inventory-api")
    instance = nacos.get_one_healthy_instance(
        "inventory-api",
        strategy="weight",
        cluster="CANARY",
        metadata={"version": "v2"},
    )
```

畸形实例会被记录并跳过。IP 必须是非空字符串，端口必须是 1–65535 的整数；字符串布尔值
会正确解析，非法或非有限权重安全回退。

## 配置中心

```python
with app.app_context():
    content = nacos.get_config("application.yaml", group="DEFAULT_GROUP")
```

`get_config()` 返回原始文本。Flask-Nacos 不解析 YAML/JSON，也不会把远端内容写入
`app.config`。

`NACOS_USERNAME`/`NACOS_PASSWORD` 必须完整成对，
`NACOS_ACCESS_KEY`/`NACOS_SECRET_KEY` 必须完整成对，两套认证互斥。切勿提交真实凭据。

## 日志

`NACOS_LOG_ENABLED=False` 为默认值。SDK 原生日志被隔离，因此 Flask-Nacos 不创建
`~/logs/nacos` 或 SDK 日志文件。安全扩展日志配置：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `NACOS_LOG_ENABLED` | `False` | 日志总开关。 |
| `NACOS_LOG_CONSOLE_ENABLED` | `True` | 启用后输出彩色控制台日志。 |
| `NACOS_LOG_FILE_ENABLED` | `True` | 启用后输出轮转文件。 |
| `NACOS_LOG_PATH` | `./logs` | 日志目录。 |
| `NACOS_LOG_FILENAME` | `flask-nacos.log` | 日志文件名。 |

控制台 DEBUG 蓝色、INFO 绿色、WARNING 黄色、ERROR 红色、CRITICAL 加粗红色；文件不含
ANSI 颜色。日志总开关关闭时，即使配置路径也不会创建目录。

## Fork、Gunicorn 与退出

Runtime资源绑定 Flask app 与 PID。fork 后父 Runtime整体作废；普通业务请求或显式 SDK
操作可以恢复自动注册，但状态、健康和 `.client` 读取不会。

Gunicorn `--preload` 推荐设置 `NACOS_AUTO_REGISTER=False`，并在 post-fork/
worker-init hook中调用 `nacos.register_instance(app)`，避免 preload master启动 SDK Runtime。

多个 worker使用相同服务身份与 IP:port（相同 service/group/cluster/IP/port）时，是同一个
Nacos 实例。共享端点应设置 `NACOS_AUTO_DEREGISTER=False`，防止一个 worker退出时删除
仍由其他 worker提供服务的实例。

`NACOS_AUTO_DEREGISTER=True` 是唯一退出注销开关。退出不会修改用户目标，不启动正常重试，
只会有限等待已经活跃的一笔 Naming RPC，随后最多执行一次尽力清理。

## 安全说明

同步 Nacos SDK 2.x 在 HTTPS 服务端证书校验方面存在限制。安全策略要求验证 TLS 时，请使用
可信网络或能够校验证书的代理/sidecar。

私密漏洞报告流程见 [SECURITY.md](SECURITY.md)。

## 示例与开发

- [初学者示例](examples/beginner_app.py)
- [完整工厂示例](examples/complete_factory_app.py)
- [服务注册示例](examples/service_registration.py)
- [服务发现示例](examples/service_discovery.py)

本地质量检查：

```bash
pytest
ruff check .
mypy flask_nacos
python scripts/check_api_snapshot.py
python scripts/check_docs.py
python scripts/check_examples.py
```

## 开源许可

Apache-2.0，详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
