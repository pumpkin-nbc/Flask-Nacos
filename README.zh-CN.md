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
- Nacos 操作统一重试、可选健康检查路由，以及 `get_status()` 运行状态查询（0.3.0）。
- 按进程的注册生命周期、安全注销、实例标准化，以及 `first`/`random`/`weight` 服务发现
  策略（0.4.0）。
- 完整类型提示与 `py.typed`（PEP 561），并提供 ruff/mypy/pytest/coverage 配置与 CI
  （0.5.0）。
- 发布工具链：版本一致性、包内容、敏感信息检查脚本，一键 `release_check.sh`、
  扩展的 CI 检查，以及手动触发的 TestPyPI/PyPI 发布工作流（0.6.0）。
- 完整的 [`docs/`](docs/) 文档集、增强的示例、本地 Nacos Docker Compose 文件，
  以及文档一致性检查（0.7.0）。
- 广泛的兼容性：Python 3.8-3.12 与 Flask `>=1.0,<4.0`（1.x/2.x/3.x），兼容不同
  Nacos SDK 返回结构，提供 Python 3.8 兼容性检查脚本以及 Python x Flask CI 矩阵
  （0.8.0）。
- Release Candidate 准备：冻结公开 API 并提供 API 快照检查、向后兼容性测试、示例
  校验脚本、安装包 smoke test，以及 1.0.0 验收清单（0.9.0）。
- 首个稳定版：公开 API 在 1.0 系列中被声明为稳定，并由 API 快照检查与向后兼容性测试
  保障（1.0.0）。

## 稳定版

`1.0.0` 是 Flask-Nacos 的首个稳定版，面向 PyPI 发布。公开 API 在 1.0 系列中保持稳定：
不会在没有废弃流程的情况下修改方法名称、已有参数含义与返回值约定；新增参数一律带默认值，
不破坏已有代码。

- `get_config()` 只返回 Nacos 配置的原始内容，不做 YAML、JSON、dict 解析。
- 当前版本不提供 `get_config_as_dict()`。
- 当前版本不提供 `load_config_to_flask()`。
- 不会自动将 Nacos 配置写入 Flask `app.config`。
- 完整的发布前验证见 [docs/1.0-checklist.zh-CN.md](docs/1.0-checklist.zh-CN.md)。

## 兼容性

- Python：3.8 - 3.12。
- Flask：`>=1.0, <4.0`（Flask 1.x、2.x、3.x）。
- Nacos：服务端 2.x，使用同步的 `nacos-sdk-python` 客户端。
- 服务发现兼容不同的 SDK 返回结构（普通列表、`hosts`/`instances`，或带 `data`
  包装的嵌套结构），并同时兼容 camelCase 与 snake_case 实例字段。

详见[兼容性](docs/compatibility.zh-CN.md)。

## 安装

```bash
pip install flask-nacos
```

本地开发（测试、代码检查、类型检查、构建）：

```bash
pip install -e ".[dev]"
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

## 文档

完整文档位于 [`docs/`](docs/)（每篇均有中英文版本）：

- [快速开始](docs/quickstart.zh-CN.md) —— 安装与第一个应用。
- [配置项](docs/configuration.zh-CN.md) —— 全部配置项分组说明。
- [API 参考](docs/api-reference.zh-CN.md) —— 公开方法与异常行为。
- [服务注册](docs/service-registration.zh-CN.md) —— 注册/注销。
- [服务发现](docs/service-discovery.zh-CN.md) —— 实例查询与策略。
- [健康检查](docs/health-check.zh-CN.md) —— 可选健康检查路由。
- [生产部署](docs/production.zh-CN.md) —— Gunicorn/uWSGI/Docker 部署。
- [错误排查](docs/troubleshooting.zh-CN.md) —— 常见问题与解决。
- [兼容性](docs/compatibility.zh-CN.md) —— 支持的 Python/Flask/Nacos 版本。
- [1.0.0 验收清单](docs/1.0-checklist.zh-CN.md) —— Release Candidate 验收清单。
- [发布指南](docs/release.zh-CN.md) —— 发布到 TestPyPI/PyPI。
- [更新日志](docs/changelog.zh-CN.md) —— 指向完整更新日志。

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
- `get_one_healthy_instance()` 支持可插拔的选择策略（`first`、`random`、`weight`）以及
  可选的 cluster / metadata 过滤，详见下方"生产部署与服务发现增强（0.4.0）"。

## 配置中心

```python
content = nacos.get_config("application.yaml")
```

`data_id` 为必填项。当省略 `group` 时，将回退到 `NACOS_CONFIG_GROUP`（再回退到
`NACOS_GROUP_NAME`）。直接返回 Nacos 配置的原始字符串内容，不做任何 YAML、JSON、
dict 解析。

## 生产可用性增强（0.3.0）

0.3.0 版本面向生产环境增强：重试、请求超时配置、可选健康检查路由、运行状态查询，
以及更精细的自动注册控制。

### 重试

`register_instance()`、`deregister_instance()`、`list_instances()`、
`get_config()` 均接入统一的重试机制。

- `NACOS_RETRY_ENABLED`（默认 `True`）：是否启用重试。为 `False` 时每个操作只执行一次。
- `NACOS_RETRY_TIMES`（默认 `3`）：最大尝试次数（不是额外重试次数）。`3` 表示最多尝试
  3 次。
- `NACOS_RETRY_INTERVAL`（默认 `1.0`）：每次尝试之间的等待秒数。

每次失败都会记录 `warning` 日志。最终失败后由 `NACOS_FAIL_FAST` 决定抛出异常还是返回
安全默认值。

### 请求超时

- `NACOS_REQUEST_TIMEOUT`（默认 `5.0`）。

> 预留配置：当前内置的同步 `nacos-sdk-python`（2.x）客户端未提供可靠的单次请求超时，
> 因此该值会被读取并通过 `get_status()` / 配置暴露，但暂不会应用到 SDK 调用。保留该
> 配置项以便应用现在即可配置，未来版本无需改配置即可生效。

### 健康检查路由

当 `NACOS_HEALTH_CHECK_ENABLED` 为 `True` 时，会在 `NACOS_HEALTH_CHECK_PATH`
（默认 `/health/nacos`）注册一个 Flask 路由。它只反映扩展内部状态，不会请求 Nacos
服务端，因此接口不会变慢。

```json
{
  "status": "ok",
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true,
  "service_name": "fund-service",
  "service_ip": "127.0.0.1",
  "service_port": 5000
}
```

当 Nacos 未启用时：

```json
{
  "status": "disabled",
  "nacos_enabled": false,
  "client_initialized": false,
  "registered": false
}
```

当 client 初始化失败时：

```json
{
  "status": "error",
  "nacos_enabled": true,
  "client_initialized": false,
  "registered": false
}
```

该路由的注册是幂等的：重复调用 `init_app(app)` 或路由已存在时都不会导致 Flask 报错。

### 运行状态查询

```python
status = nacos.get_status()
```

只返回扩展内部状态与非敏感配置，不会请求 Nacos，也不会包含 `NACOS_PASSWORD`、
`NACOS_ACCESS_KEY`、`NACOS_SECRET_KEY`：

```python
{
    "nacos_enabled": True,
    "client_initialized": True,
    "registered": True,
    "service_name": "fund-service",
    "service_ip": "127.0.0.1",
    "service_port": 5000,
    "server_addr": "127.0.0.1:8848",
    "namespace_id": "",
}
```

### 自动注册控制

两个开关共同控制初始化阶段的注册：

- `NACOS_AUTO_REGISTER`（默认 `True`）：自动注册总开关。
- `NACOS_AUTO_REGISTER_ON_INIT`（默认 `True`）：`init_app(app)` 是否执行自动注册。

只有两者都为 `True`（且 `NACOS_REGISTER_ENABLED` 为 `True`）时，才会在
`init_app(app)` 期间自动注册。你始终可以手动注册：

```python
nacos.register_instance()
```

### Gunicorn / 多 worker 部署

在 Gunicorn / uWSGI 下，每个 worker 进程都会执行 `init_app` 并各自注册实例。为获得更
可控的行为，建议将 `NACOS_AUTO_REGISTER_ON_INIT` 设为 `False`，改为在明确的启动流程
（例如 post-fork 钩子或管理命令）中显式调用注册，而不是在导入 / 初始化阶段隐式注册。

生产环境请务必显式配置 `NACOS_SERVICE_NAME`、`NACOS_SERVICE_IP`、
`NACOS_SERVICE_PORT`，不要依赖自动识别。

## 生产部署与服务发现增强（0.4.0）

0.4.0 版本聚焦多 worker 部署安全与更丰富的服务发现：按进程的注册生命周期、安全注销、
实例标准化、服务发现过滤，以及可插拔的选择策略。

### 多 worker 注册（Gunicorn / uWSGI）

在 Gunicorn / uWSGI 下，主进程会 fork 出多个 worker，每个 worker 都会执行 `init_app`。
flask-nacos 会记录执行注册的进程 ID：

- `NACOS_REGISTER_ONCE_PER_PROCESS`（默认 `True`）：同一进程内，`register_instance()`
  成功后重复调用会被跳过。当 fork 出新 worker（进程 ID 变化）时，新 worker 允许注册
  自己的实例。
- 退出时，`deregister_instance()` 只注销当前进程注册的实例。如果记录的注册进程 ID 与
  当前进程不一致（例如主进程与 worker），会记录日志并跳过注销，避免误删其他进程的实例。

Gunicorn 示例（每个 worker 各自注册，退出时各自注销）：

```python
# wsgi.py
from myapp import create_app

app = create_app()  # 此处执行 init_app；每个 fork 出的 worker 各自注册
```

```bash
gunicorn -w 4 wsgi:app
```

uWSGI 行为相同，每个 worker 进程各自注册和注销自己的实例。如果希望显式控制注册，可将
`NACOS_AUTO_REGISTER_ON_INIT` 设为 `False`，并在 post-fork 钩子中调用
`nacos.register_instance()`。

### 退出时注销

- `NACOS_DEREGISTER_ON_EXIT`（默认 `True`）：是否注册 `atexit` 处理器在进程退出时注销。
- 仅当 `NACOS_AUTO_DEREGISTER` 与 `NACOS_DEREGISTER_ON_EXIT` 都为 `True` 时才注册
  `atexit` 处理器，且每个扩展实例最多注册一次（重复调用 `init_app(app)` 不会重复注册）。

### 实例标准化

- `NACOS_INSTANCE_NORMALIZE`（默认 `True`）：启用时 `list_instances()` 返回标准 dict
  列表；关闭时返回 SDK 原始实例。

```python
instance = nacos.normalize_instance(raw_sdk_instance)
```

标准 dict 结构：

```python
{
    "ip": "127.0.0.1",
    "port": 5000,
    "service_name": "user-service",
    "cluster_name": "DEFAULT",
    "weight": 1.0,
    "healthy": True,
    "enabled": True,
    "ephemeral": True,
    "metadata": {},
}
```

`normalize_instance()` 兼容 dict 与对象属性形式的实例，缺失字段使用合理默认值，且不会
因单个实例异常而抛错（记录日志并返回 `None`）。服务发现时，单个标准化失败的实例会被
跳过，而不会导致整个发现失败。

### 服务发现过滤

`list_instances()` 支持可选的 `cluster` 与 `metadata` 过滤：

```python
nacos.list_instances("user-service", cluster="CANARY")
nacos.list_instances("user-service", metadata={"version": "v1"})
```

- `cluster` 未提供时回退到 `NACOS_DISCOVERY_CLUSTER`。
- `metadata` 未提供时回退到 `NACOS_DISCOVERY_METADATA`。
- 设置 `cluster` 时只返回该 cluster 的实例。
- 设置 `metadata` 时只返回 metadata 包含全部指定键值对的实例。
- 过滤后无实例时返回空列表。

### 选择策略

`get_one_healthy_instance()` 支持可选的 `strategy`（未提供时回退到
`NACOS_DISCOVERY_STRATEGY`，默认 `first`），并支持相同的 `cluster` / `metadata` 过滤：

```python
# first（默认）：返回第一个健康实例
nacos.get_one_healthy_instance("user-service", strategy="first")

# random：随机返回一个健康实例
nacos.get_one_healthy_instance("user-service", strategy="random")

# weight：按实例权重进行加权随机选择
nacos.get_one_healthy_instance("user-service", strategy="weight")
```

当前支持的策略：`first`、`random`、`weight`。

- `first`：返回第一个健康实例。
- `random`：从健康实例中均匀随机返回一个。
- `weight`：按实例 `weight` 加权随机选择（缺失权重默认 `1.0`；权重 `<= 0` 的实例被忽略；
  若所有权重都 `<= 0`，退化为 `first` 策略）。
- 没有健康实例时返回 `None`。
- 不支持的策略遵循 `NACOS_FAIL_FAST` 规则（`False` 时返回 `None`，`True` 时抛异常）。

### 运行状态（新增字段）

`get_status()` 新增进程与服务发现相关字段（仍不含敏感信息，也不会请求 Nacos）：

```python
{
    # ... 已有字段 ...
    "current_pid": 12345,
    "registered_pid": 12345,
    "register_once_per_process": True,
    "deregister_on_exit": True,
    "discovery_strategy": "first",
    "instance_normalize": True,
    "health_check_enabled": True,
    "health_check_path": "/health/nacos",
}
```

### 配置中心（保持不变）

`get_config()` 仍然只返回 Nacos 配置的原始内容，不做任何 YAML、JSON、dict 解析。

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
| `NACOS_RETRY_ENABLED` | `True` | 是否为 Nacos 操作启用重试。 |
| `NACOS_RETRY_TIMES` | `3` | 每个操作的最大尝试次数。 |
| `NACOS_RETRY_INTERVAL` | `1.0` | 每次重试之间的等待秒数。 |
| `NACOS_REQUEST_TIMEOUT` | `5.0` | 请求超时（预留；参见生产可用性增强）。 |
| `NACOS_HEALTH_CHECK_ENABLED` | `False` | 是否注册 Flask 健康检查路由。 |
| `NACOS_HEALTH_CHECK_PATH` | `"/health/nacos"` | 健康检查路由路径。 |
| `NACOS_STATUS_ENABLED` | `True` | 是否启用运行状态查询能力。 |
| `NACOS_AUTO_REGISTER_ON_INIT` | `True` | 是否在 `init_app` 阶段自动注册（配合 `NACOS_AUTO_REGISTER`）。 |
| `NACOS_REGISTER_ONCE_PER_PROCESS` | `True` | 同一进程内只注册一次；fork 出的新 worker（新 pid）可重新注册。 |
| `NACOS_DEREGISTER_ON_EXIT` | `True` | 是否注册 `atexit` 处理器在进程退出时注销。 |
| `NACOS_DISCOVERY_STRATEGY` | `"first"` | `get_one_healthy_instance` 的默认策略（`first`/`random`/`weight`）。 |
| `NACOS_DISCOVERY_CLUSTER` | `None` | 服务发现默认 cluster 过滤。 |
| `NACOS_DISCOVERY_METADATA` | `{}` | 服务发现默认 metadata 过滤。 |
| `NACOS_INSTANCE_NORMALIZE` | `True` | `list_instances` 是否返回标准化实例 dict。 |
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
- CI 中会运行敏感信息扫描（`scripts/check_sensitive_info.py`），防止误提交密钥、
  内部 IP 或 `.env` 文件。

## 示例

可直接运行的示例位于 [`examples/`](examples/) 目录：

- [`examples/basic_app.py`](examples/basic_app.py) —— Flask 普通模式，使用
  `FlaskNacos(app)`。
- [`examples/factory_app.py`](examples/factory_app.py) —— Flask 工厂模式，使用
  `nacos.init_app(app)`。
- [`examples/service_registration.py`](examples/service_registration.py) ——
  手动与自动注册、注销。
- [`examples/service_discovery.py`](examples/service_discovery.py) —— 列举实例、
  cluster / metadata 过滤，以及 `get_one_healthy_instance()`。
- [`examples/health_check_app.py`](examples/health_check_app.py) —— 通过
  `NACOS_HEALTH_CHECK_ENABLED` / `NACOS_HEALTH_CHECK_PATH` 启用健康检查路由。
- [`examples/production_config.py`](examples/production_config.py) —— 面向多
  worker 部署、基于环境变量的配置。
- [`examples/docker-compose-nacos.yml`](examples/docker-compose-nacos.yml) ——
  本地手动测试用的 Nacos（仅限本地使用）。

示例使用 `127.0.0.1:8848` 与本地演示账号 `nacos/nacos`，请替换为你自己的配置
（建议通过环境变量传入）。

启动本地 Nacos 进行手动测试：

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

## 本地开发与测试

将 dev 依赖安装到虚拟环境后运行相关工具。测试套件中所有 Nacos 交互均使用 mock，
无需真实 Nacos 服务。

```bash
# Linux / macOS
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy flask_nacos
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

```powershell
# Windows (PowerShell)
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy flask_nacos
.venv\Scripts\python -m build
.venv\Scripts\python -m twine check dist/*
```

覆盖率会自动统计（`--cov=flask_nacos`），且未设置硬性阈值，不会阻塞开发。

## 类型提示

`flask-nacos` 内置类型提示并附带 `py.typed` 标记（PEP 561）。安装后，mypy、Pyright
等类型检查工具会自动识别本包的类型信息，无需额外的 stub 包。

## PyPI 发布准备

在发布版本前，请在仓库根目录运行一键预发布检查：

```bash
bash scripts/release_check.sh
```

该脚本依次执行 `ruff`、`mypy`、`pytest`、版本一致性检查、敏感信息扫描、干净的
`python -m build`、`twine check` 以及包内容检查，且不会上传任何内容。各脚本分别为：

- [`scripts/check_version.py`](scripts/check_version.py) —— 校验 `pyproject.toml`、
  `__version__`、`CHANGELOG.md` 三处版本号一致。
- [`scripts/check_sensitive_info.py`](scripts/check_sensitive_info.py) —— 扫描硬编码
  密钥、内部 IP、内部域名与 `.env` 文件。
- [`scripts/check_package.py`](scripts/check_package.py) —— 检查构建出的 wheel，确认
  包含 `py.typed` 与核心模块，且不含测试 / 缓存。

手动触发的 `Release` 工作流（[`.github/workflows/release.yml`](.github/workflows/release.yml)）
会重跑上述检查，并上传到 TestPyPI（默认）或 PyPI（需显式选择）。完整发布流程、
TestPyPI/PyPI 步骤以及 GitHub Secrets 配置（`TEST_PYPI_API_TOKEN`、`PYPI_API_TOKEN`）
详见 [`docs/release.md`](docs/release.md)。

推送时绝不会自动发布到 PyPI；CI 仅执行代码检查、类型检查、测试、构建以及发布检查脚本。

## 版本兼容说明

- Flask：`>=1.0, <4.0`
- Python：`>=3.8`
- Nacos：2.x
- Nacos SDK：`nacos-sdk-python>=2.0.0,<3.0.0`（同步客户端）

## 开源许可

基于 GNU General Public License v3.0 或更新版本发布，详见 [LICENSE](LICENSE)。
