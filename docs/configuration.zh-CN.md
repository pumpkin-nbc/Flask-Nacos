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

示例：

```python
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_NAMESPACE_ID="public",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
)
```

## 2. 服务注册

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_REGISTER_ENABLED` | bool | `True` | 否 | 是否启用服务注册。 |
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

## 3. 服务发现

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_DISCOVERY_STRATEGY` | str | `"first"` | 否 | `get_one_healthy_instance` 的默认策略（`first`/`random`/`weight`）。 |
| `NACOS_DISCOVERY_CLUSTER` | str | `None` | 否 | 默认 cluster 过滤。 |
| `NACOS_DISCOVERY_METADATA` | dict | `{}` | 否 | 默认 metadata 过滤。 |
| `NACOS_INSTANCE_NORMALIZE` | bool | `True` | 否 | `list_instances` 是否返回标准化实例 dict。 |

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
| `NACOS_RETRY_TIMES` | int | `3` | 否 | 每个操作的最大尝试次数。 |
| `NACOS_RETRY_INTERVAL` | float | `1.0` | 否 | 每次尝试之间的等待秒数。 |
| `NACOS_REQUEST_TIMEOUT` | float | `5.0` | 否 | 请求超时（预留；通过 `get_status()` 暴露，但当前内置 SDK 暂不应用）。 |

示例：

```python
app.config.update(
    NACOS_RETRY_ENABLED=True,
    NACOS_RETRY_TIMES=3,
    NACOS_RETRY_INTERVAL=1.0,
)
```

## 6. 运行状态

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_STATUS_ENABLED` | bool | `True` | 否 | 是否启用 `get_status()` 运行状态查询。 |

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

| 配置项 | 类型 | 默认值 | 是否必填 | 说明 |
| --- | --- | --- | --- | --- |
| `NACOS_LOG_LEVEL` | str | `"INFO"` | 否 | `flask_nacos` logger 的日志级别。敏感信息不会被记录。 |

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
