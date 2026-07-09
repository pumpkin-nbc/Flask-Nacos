# Flask-Nacos

简体中文 | [English](README.md)

`flask-nacos` 是一个 Flask 扩展库，用于将 Flask 应用接入 [Nacos](https://nacos.io/)，
提供服务注册、服务注销、服务发现以及配置中心访问能力。其使用方式尽量贴近常见的 Flask
扩展（如 `Flask-SQLAlchemy`、`Flask-Redis`）。

## 功能特性

- 同时支持 `FlaskNacos(app)` 直接初始化与工厂模式 `init_app(app)`。
- 从 `app.config` 读取配置初始化 Nacos client，支持 namespace 与用户名/密码认证。
- 支持自动注册与手动注册服务。
- 支持自动注销（基于 `atexit`）与手动注销服务。
- 服务发现：获取实例列表、获取一个健康实例。
- 配置中心读取能力（`get_config`）。
- 可配置的 fail-fast 行为，并提供专用异常类型体系。
- 基于标准 `logging`，且日志中不会输出敏感信息（密码、AccessKey、SecretKey）。

## 安装

```bash
pip install flask-nacos
```

可选的 YAML 支持（为后续配置解析能力预留）：

```bash
pip install "flask-nacos[yaml]"
```

## 快速开始

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
)

nacos = FlaskNacos(app)
```

初始化完成后，扩展实例可通过 `app.extensions["nacos"]` 获取。

## Flask 普通模式

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.from_object("config.Config")

nacos = FlaskNacos(app)
```

## Flask 工厂模式

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

## 服务注册

当 `NACOS_REGISTER_ENABLED` 与 `NACOS_AUTO_REGISTER` 同时为 `True` 时，会在
`init_app(app)` 期间自动注册服务。你也可以手动注册：

```python
nacos.register_instance()
```

### 注册参数校验规则

注册实例前会校验以下参数，非法值的处理遵循 `NACOS_FAIL_FAST` 规则
（参见[异常处理](#异常处理)）：

- `NACOS_SERVICE_NAME` —— 必填，不能为空。
- `NACOS_SERVICE_PORT` —— 必填，必须是 `1-65535` 范围内的整数。
- `NACOS_SERVICE_WEIGHT` —— 必须是大于 `0` 的数字。
- `NACOS_SERVICE_METADATA` —— 必须是 `dict`。
- `NACOS_SERVICE_EPHEMERAL` —— 必须是 `bool`。

注册具备幂等性：对同一个扩展实例多次调用 `register_instance()` 只会注册一次，
后续调用为无操作（no-op）。

### 服务 IP 自动识别

若未提供 `NACOS_SERVICE_IP`，扩展会通过 `get_local_ip()` 工具方法尝试自动识别本机
出口 IP。若识别失败，行为遵循 `NACOS_FAIL_FAST` 规则。

> 生产环境建议：请显式配置 `NACOS_SERVICE_IP`，不要完全依赖自动识别。在容器、多网卡
> 主机或 NAT 环境下，自动识别到的地址可能并不是希望被其他服务访问的地址。

## 服务注销

当 `NACOS_AUTO_DEREGISTER` 为 `True` 时，会在进程退出时通过 `atexit` 自动注销实例。
你也可以手动注销：

```python
nacos.deregister_instance()
```

注销具备幂等性：实例被注销后，再次调用 `deregister_instance()` 为无操作，且不会报错。

## 服务发现

```python
# 获取实例列表（默认只返回健康实例）
instances = nacos.list_instances("user-service")

# 获取指定 group 的全部实例
instances = nacos.list_instances("user-service", group="DEFAULT_GROUP", healthy_only=False)

# 获取一个健康实例
instance = nacos.get_one_healthy_instance("user-service")
```

- `service_name` 为必填项；为空时行为遵循 `NACOS_FAIL_FAST` 规则。
- 省略 `group` 时使用默认 group（`NACOS_GROUP_NAME`）。
- `healthy_only=True`（默认）只返回健康实例；`healthy_only=False` 返回全部实例。
- 查询结果为空时返回空列表，而不是抛出异常。
- `get_one_healthy_instance()` 当前返回第一个健康实例。随机、轮询、权重负载均衡等
  策略将在后续版本支持。

## 配置中心

```python
content = nacos.get_config("application.yaml")
```

`data_id` 为必填项。当省略 `group` 时，将回退到 `NACOS_CONFIG_GROUP`（再回退到
`NACOS_GROUP_NAME`）。直接返回 Nacos 配置的原始字符串内容，不做任何 YAML、JSON、
dict 解析。

## 配置项说明

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `NACOS_ENABLED` | `True` | 总开关；为 `False` 时不创建 client。 |
| `NACOS_SERVER_ADDR` | `"127.0.0.1:8848"` | Nacos 服务地址（必填）。 |
| `NACOS_NAMESPACE_ID` | `""` | 命名空间 id。 |
| `NACOS_USERNAME` | `None` | 认证用户名。 |
| `NACOS_PASSWORD` | `None` | 认证密码。 |
| `NACOS_ACCESS_KEY` | `None` | 认证 AccessKey。 |
| `NACOS_SECRET_KEY` | `None` | 认证 SecretKey。 |
| `NACOS_GROUP_NAME` | `"DEFAULT_GROUP"` | 默认 group。 |
| `NACOS_REGISTER_ENABLED` | `True` | 是否启用服务注册。 |
| `NACOS_AUTO_REGISTER` | `True` | 是否在 `init_app` 时自动注册。 |
| `NACOS_AUTO_DEREGISTER` | `True` | 是否在退出时自动注销。 |
| `NACOS_SERVICE_NAME` | `None` | 服务名（注册时必填）。 |
| `NACOS_SERVICE_IP` | `None` | 服务 IP；未设置时自动检测。 |
| `NACOS_SERVICE_PORT` | `None` | 服务端口（注册时必填）。 |
| `NACOS_SERVICE_GROUP` | `"DEFAULT_GROUP"` | 注册所用 group。 |
| `NACOS_SERVICE_CLUSTER` | `"DEFAULT"` | 集群名称。 |
| `NACOS_SERVICE_WEIGHT` | `1.0` | 负载均衡权重。 |
| `NACOS_SERVICE_METADATA` | `{}` | 实例元数据字典。 |
| `NACOS_SERVICE_EPHEMERAL` | `True` | 是否注册为临时实例。 |
| `NACOS_SERVICE_HEALTHY` | `True` | 初始健康标识。 |
| `NACOS_SERVICE_ENABLED` | `True` | 实例是否启用。 |
| `NACOS_CONFIG_ENABLED` | `True` | 是否启用配置中心能力。 |
| `NACOS_CONFIG_DATA_ID` | `None` | 默认配置 data id。 |
| `NACOS_CONFIG_GROUP` | `"DEFAULT_GROUP"` | 默认配置 group。 |
| `NACOS_FAIL_FAST` | `False` | 为 `True` 时 Nacos 异常会抛出。 |
| `NACOS_LOG_LEVEL` | `"INFO"` | `flask_nacos` 的日志级别。 |

## 异常处理

失败时的行为由 `NACOS_FAIL_FAST` 控制，涵盖 Nacos 客户端初始化、服务注册、服务注销、
服务发现、注册参数校验以及本机 IP 自动识别：

- `NACOS_FAIL_FAST = False`（默认）：失败时仅记录日志，不会阻止 Flask 应用启动。
  各方法返回安全默认值：
  - `register_instance()` -> `False`
  - `deregister_instance()` -> `False`
  - `list_instances()` -> `[]`
  - `get_one_healthy_instance()` -> `None`
  - `get_config()` -> `None`
- `NACOS_FAIL_FAST = True`：失败时抛出异常。

异常类型体系：

```python
from flask_nacos import (
    FlaskNacosError,
    NacosConfigError,
    NacosClientError,
    NacosValidationError,
    NacosRegistrationError,
    NacosDeregistrationError,
    NacosDiscoveryError,
)
```

- `FlaskNacosError` —— 基类。
- `NacosConfigError` —— 配置无效或配置读取失败。
- `NacosClientError` —— Nacos 客户端创建 / 使用失败。
- `NacosValidationError` —— 注册参数校验失败（继承自 `NacosConfigError`）。
- `NacosRegistrationError` —— 服务注册失败。
- `NacosDeregistrationError` —— 服务注销失败。
- `NacosDiscoveryError` —— 服务发现失败。

## 生产部署注意事项

- 在多 worker 服务器（Gunicorn / uWSGI）下，每个 worker 会各自注册实例。基于
  `atexit` 的注销为“尽力而为”，更完善的多 worker 处理将在后续版本中提供。
- 切勿提交真实账号密码、公司内部 Nacos 地址或内部 IP。建议通过环境变量传入
  `NACOS_USERNAME` / `NACOS_PASSWORD`。
- 敏感信息（`NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、`NACOS_SECRET_KEY`）不会写入日志。

## 版本兼容说明

- Flask：`>=1.0, <4.0`
- Python：`>=3.8`
- Nacos：2.x
- Nacos SDK：`nacos-sdk-python>=2.0.0,<3.0.0`（同步客户端）

## 开源许可

基于 GNU General Public License v3.0 或更新版本发布，详见 [LICENSE](LICENSE)。
