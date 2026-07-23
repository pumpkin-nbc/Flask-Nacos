# 配置项参考

[English](configuration.md) | 简体中文

所有配置项均从 Flask `app.config` 读取。未设置的键回退到 `flask_nacos/config.py`
中定义的默认值。布尔与数值型键支持从字符串强制转换，因此环境变量风格的值也能正常
工作。

另请参阅：[快速开始](quickstart.zh-CN.md) - [API 参考](api-reference.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 生产与安全须知

- 生产环境请显式设置 `NACOS_SERVICE_NAME`、`NACOS_SERVICE_IP`、
  `NACOS_SERVICE_PORT`，不要依赖自动识别。在容器、多网卡主机或 NAT 环境下，
  自动识别到的 IP 可能不可达。
- 切勿将 `NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、`NACOS_SECRET_KEY` 等敏感值提交到
  代码仓库。请通过环境变量或密钥管理服务注入。这些值不会被写入日志。

## 1. Nacos 连接

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_ENABLED` | bool | `True` | 否 | 总开关；为 `False` 时不创建 client，所有操作均为 no-op。 |
| `NACOS_SERVER_ADDR` | str | `"127.0.0.1:8848"` | 是 | Nacos 服务地址（`host:port`）。 |
| `NACOS_NAMESPACE_ID` | str | `""` | 否 | 命名空间 id。 |
| `NACOS_USERNAME` | str | `None` | 否 | 认证用户名。 |
| `NACOS_PASSWORD` | str | `None` | 否 | 认证密码（不要写入源码库）。 |
| `NACOS_ACCESS_KEY` | str | `None` | 否 | 认证 AccessKey（敏感）。 |
| `NACOS_SECRET_KEY` | str | `None` | 否 | 认证 SecretKey（敏感）。 |
| `NACOS_GROUP_NAME` | str | `"DEFAULT_GROUP"` | 否 | 默认 group，作为回退值。 |

`NACOS_SERVER_ADDR` 与 `NACOS_SERVICE_IP` 不能互换：

- `NACOS_SERVER_ADDR` 是 Flask 进程主动连接的 Nacos API 地址。
- `NACOS_SERVICE_IP` 是注册给消费者访问的 Flask 地址，需要与
  `NACOS_SERVICE_PORT` 组合使用。

以文档拓扑为例：Nacos 是 `203.0.113.10:8848`，Flask 是
`203.0.113.20:5000`，两个配置应分别使用这两个值。从 Flask 主机测试第一条链路，从
消费者主机测试第二条链路。PowerShell/Bash 诊断命令及 Docker/NAT 说明见
[快速开始](quickstart.zh-CN.md#连接已有且开启认证的-nacos)。

示例：

```python
import os

app.config.update(
    NACOS_SERVER_ADDR=os.environ["NACOS_SERVER_ADDR"],
    NACOS_NAMESPACE_ID=os.environ.get("NACOS_NAMESPACE_ID", ""),
    NACOS_USERNAME=os.environ.get("NACOS_USERNAME"),
    NACOS_PASSWORD=os.environ.get("NACOS_PASSWORD"),
    NACOS_ACCESS_KEY=os.environ.get("NACOS_ACCESS_KEY"),
    NACOS_SECRET_KEY=os.environ.get("NACOS_SECRET_KEY"),
)
```

请填写 namespace ID，而不是控制台显示名称。根据服务端认证方式选择用户名/密码或
AK/SK，任何一种都不要硬编码。每组凭据必须完整，两种认证方式互斥；认证配置非法时，
client 初始化会遵循 `NACOS_FAIL_FAST`。

## 2. 服务注册

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_REGISTER_ENABLED` | bool | `True` | 否 | 是否启用初始化阶段的自动注册；不影响手动注册。 |
| `NACOS_AUTO_REGISTER` | bool | `True` | 否 | 自动注册总开关。 |
| `NACOS_AUTO_DEREGISTER` | bool | `True` | 否 | 退出时自动注销。 |
| `NACOS_SERVICE_NAME` | str | `None` | 是（注册时） | 服务名。 |
| `NACOS_SERVICE_IP` | str | `None` | 建议 | 服务 IP；未设置时自动识别。 |
| `NACOS_SERVICE_PORT` | int | `None` | 是（注册时） | 服务端口，`1-65535`。 |
| `NACOS_SERVICE_GROUP` | str | `"DEFAULT_GROUP"` | 否 | 注册所用 group。 |
| `NACOS_SERVICE_CLUSTER` | str | `"DEFAULT"` | 否 | 集群名称。 |
| `NACOS_SERVICE_WEIGHT` | float | `1.0` | 否 | 有限的负载均衡权重（`> 0`）。 |
| `NACOS_SERVICE_METADATA` | dict | `{}` | 否 | 实例元数据。 |
| `NACOS_SERVICE_EPHEMERAL` | bool | `True` | 否 | 是否注册为临时实例。 |
| `NACOS_SERVICE_HEARTBEAT_INTERVAL` | float | `5.0` | 否 | 临时实例的 SDK 心跳间隔，单位为秒；必须为大于 `0` 的有限数字。 |
| `NACOS_SERVICE_HEALTHY` | bool | `True` | 否 | 初始健康标识。 |
| `NACOS_SERVICE_ENABLED` | bool | `True` | 否 | 实例是否启用。 |

示例：

```python
app.config.update(
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
    NACOS_SERVICE_METADATA={"version": "v1"},
)
```

生产建议：显式设置 `NACOS_SERVICE_NAME`、`NACOS_SERVICE_IP`、
`NACOS_SERVICE_PORT`。

`NACOS_SERVICE_HEARTBEAT_INTERVAL` 仅在临时实例注册时传给 SDK 2.x；持久实例
（`NACOS_SERVICE_EPHEMERAL=False`）会忽略它。初始健康标识不能让临时实例持续存活。

## 3. 服务发现

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_DISCOVERY_STRATEGY` | str | `"first"` | 否 | `get_one_healthy_instance` 的默认策略（`first`/`random`/`weight`）。 |
| `NACOS_DISCOVERY_CLUSTER` | str | `None` | 否 | 默认 cluster 过滤。 |
| `NACOS_DISCOVERY_METADATA` | dict | `{}` | 否 | 默认 metadata 过滤。 |
| `NACOS_INSTANCE_NORMALIZE` | bool | `True` | 否 | 是否返回标准化实例 dict；IP/端口畸形的实例会被跳过。 |

示例：

```python
app.config.update(
    NACOS_DISCOVERY_STRATEGY="weight",
    NACOS_DISCOVERY_CLUSTER="DEFAULT",
)
```

## 4. 健康检查

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_HEALTH_CHECK_ENABLED` | bool | `False` | 否 | 是否注册 Flask 健康检查路由。 |
| `NACOS_HEALTH_CHECK_PATH` | str | `"/health/nacos"` | 否 | 健康检查路由路径。 |

示例：

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

## 5. 重试

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_RETRY_ENABLED` | bool | `True` | 否 | 是否为 Nacos 操作启用重试。 |
| `NACOS_RETRY_TIMES` | int | `3` | 否 | 最大尝试次数，必须为不小于 `1` 的整数。 |
| `NACOS_RETRY_INTERVAL` | float | `1.0` | 否 | 尝试间隔秒数，必须为不小于 `0` 的有限数字。 |
| `NACOS_REQUEST_TIMEOUT` | float | `5.0` | 否 | 配置中心读取超时，必须为大于 `0` 的有限数字。 |

示例：

```python
app.config.update(
    NACOS_RETRY_ENABLED=True,
    NACOS_RETRY_TIMES=3,
    NACOS_RETRY_INTERVAL=1.0,
)
```

支持合法数字字符串；布尔值、小数尝试次数、NaN、Infinity 和越界值会立即失败且不重试。
关闭重试时忽略重试参数；关闭配置中心时忽略请求超时。

## 6. 运行状态

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_STATUS_ENABLED` | bool | `True` | 否 | 已弃用的无操作兼容项；计划在 2.0 删除。 |

## 7. 生命周期

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_AUTO_REGISTER_ON_INIT` | bool | `True` | 否 | `init_app(app)` 是否执行自动注册。 |
| `NACOS_REGISTER_ONCE_PER_PROCESS` | bool | `True` | 否 | 同一进程只注册一次；fork 出的新 worker（新 pid）可重新注册。 |
| `NACOS_DEREGISTER_ON_EXIT` | bool | `True` | 否 | 是否注册 `atexit` 处理器在进程退出时注销。 |

示例（Gunicorn 下显式注册）：

```python
app.config["NACOS_AUTO_REGISTER_ON_INIT"] = False
```

## 8. 日志

这些 `NACOS_LOG_*` 配置项仅控制 `flask_nacos` logger 生成的脱敏安全日志。底层
`nacos-sdk-python` logger（`nacos`、`nacos.client`、`nacos-sdk-python`）的原生日志可能
包含 token、请求参数或配置正文，因此始终静默。

默认关闭 Flask-Nacos 日志，不创建任何日志文件、不修改 root logger，也不会创建 SDK 的
`~/logs/nacos` 目录。设置 `NACOS_LOG_ENABLED=True` 后，控制台和轮转文件输出默认同时开启；
创建 `NACOS_LOG_PATH` 后写入 `NACOS_LOG_FILENAME`，默认结果为 `./logs/flask-nacos.log`。

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_LOG_ENABLED` | bool | `False` | 否 | Flask-Nacos 安全日志总开关；无论取值如何，SDK 原生日志始终静默。 |
| `NACOS_LOG_LEVEL` | str | `"INFO"` | 否 | Flask-Nacos 安全日志级别，取值 `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`。非法值遵循 `NACOS_FAIL_FAST`。 |
| `NACOS_LOG_CONSOLE_ENABLED` | bool | `True` | 否 | 日志启用时，向控制台输出正常日志和异常日志。 |
| `NACOS_LOG_FILE_ENABLED` | bool | `True` | 否 | 日志启用时，写入轮转日志文件。 |
| `NACOS_LOG_PATH` | str | `"./logs"` | 否 | Flask-Nacos 安全日志目录；仅在日志和文件输出均启用时创建。 |
| `NACOS_LOG_FILENAME` | str | `"flask-nacos.log"` | 否 | `NACOS_LOG_PATH` 内的文件名；不能包含路径或目录穿越。 |
| `NACOS_LOG_FORMAT` | str | `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` | 否 | 应用于 flask-nacos handler 的格式字符串。 |
| `NACOS_LOG_PROPAGATE` | bool | `True` | 否 | 是否向父级 logger 传播。即使为 `True` 也不会修改 root logger。 |
| `NACOS_LOG_MAX_BYTES` | int \| None | `10485760` | 否 | 正整数设置 `RotatingFileHandler` 的轮转大小；`None` 使用普通 `FileHandler`。 |
| `NACOS_LOG_BACKUP_COUNT` | int | `5` | 否 | `RotatingFileHandler` 的备份数量。 |

重复调用 `init_app(app)` 不会重复添加 handler。

示例：

```python
# 文件日志（轮转）写入指定目录。
app.config.update(
    NACOS_LOG_ENABLED=True,
    NACOS_LOG_LEVEL="INFO",
    NACOS_LOG_FILE_ENABLED=True,
    NACOS_LOG_PATH="/var/log/flask-nacos",
    NACOS_LOG_FILENAME="service.log",
    NACOS_LOG_MAX_BYTES=10485760,
    NACOS_LOG_BACKUP_COUNT=5,
)

# 容器友好：仅控制台，无文件。
app.config.update(
    NACOS_LOG_ENABLED=True,
    NACOS_LOG_CONSOLE_ENABLED=True,
    NACOS_LOG_FILE_ENABLED=False,
)

# 同时静默 Flask-Nacos 安全日志（SDK 原生日志始终静默）。
app.config.update(NACOS_LOG_ENABLED=False)
```

生产建议：容器中优先使用平台统一日志。若启用日志但不希望创建文件，请设置
`NACOS_LOG_FILE_ENABLED=False`；否则默认文件为 `./logs/flask-nacos.log`。不要依赖
nacos-sdk-python 的默认日志路径。

## 同步 SDK 2.x 的 HTTPS 限制

同步 `nacos-sdk-python` 2.x 没有提供可靠的 HTTPS 证书校验控制。不能仅凭
`NACOS_SERVER_ADDR` 使用 `https://` 就认为传输已经安全。生产环境请仅通过受信网络连接，
或使用能够验证 Nacos 服务端证书的 TLS 代理 / sidecar。

## 9. 行为控制

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_FAIL_FAST` | bool | `False` | 否 | 为 `True` 时 Nacos 错误抛出异常；为 `False` 时记录日志并返回安全默认值。 |

`NACOS_FAIL_FAST` 对各方法的影响详见 [API 参考](api-reference.zh-CN.md)。

## 配置中心

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_CONFIG_ENABLED` | bool | `True` | 否 | 是否启用配置中心能力。 |
| `NACOS_CONFIG_DATA_ID` | str | `None` | 否 | 默认配置 data id。 |
| `NACOS_CONFIG_GROUP` | str | `"DEFAULT_GROUP"` | 否 | 默认配置 group。 |

`get_config()` 只返回配置的原始内容字符串，不做 YAML、JSON、dict 解析，也不会写入
`app.config`。
省略 `data_id` 时使用 `NACOS_CONFIG_DATA_ID`；关闭 `NACOS_CONFIG_ENABLED` 时跳过
SDK 调用并返回 `None`。
