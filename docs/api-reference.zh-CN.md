# API 参考

[English](api-reference.md) | 简体中文

`FlaskNacos` 扩展的公开 API。除非具体方法另有约定，错误行为由 `NACOS_FAIL_FAST` 控制
（见[配置项](configuration.zh-CN.md)）：为 `False`（默认）时失败会被记录并返回安全
默认值；为 `True` 时抛出异常。后台注册失败发生在调用方返回之后，因此只保留在本地
状态中，不能抛回已经结束的调用栈。

另请参阅：[快速开始](quickstart.zh-CN.md) - [配置项](configuration.zh-CN.md)。

## API 快照（1.1 系列）

当前受支持的 1.1 接口会强制校验以下 API 快照：

```python
FlaskNacos(app=None)
init_app(app)
get_client()
register_instance()
deregister_instance()
list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)
get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)
get_config(data_id=None, group=None)
get_status()
normalize_instance(instance)
```

`get_config()` 只返回 Nacos 配置的原始内容。

- 不提供 `get_config_as_dict()`。
- 不提供 `load_config_to_flask()`。

该快照由 `scripts/check_api_snapshot.py` 强制校验。

## `FlaskNacos(app=None)`

构造扩展。提供 `app` 时会立即调用 `init_app(app)`（Flask 普通模式）；省略时可稍后
调用 `init_app(app)`（工厂模式）。

```python
from flask_nacos import FlaskNacos

nacos = FlaskNacos(app)          # 普通模式
nacos = FlaskNacos()             # 工厂模式；稍后调用 init_app
```

## `init_app(app)`

针对 Flask `app` 初始化扩展：加载配置、创建 Nacos client、注册健康检查路由
（若启用）、调度后台注册（默认开启）。会将包含 `config` 与 `client` 的状态映射保存到
`app.extensions["nacos"]`。

- 参数：`app` —— Flask 应用。
- 返回：`None`。
- 异常：确定性配置/client 与注册线程启动错误遵循 `NACOS_FAIL_FAST`；后台网络错误写入状态。

## `get_client()`

返回由 `init_app()` 创建的底层 Nacos SDK client。

- 返回：SDK client 对象；当 Nacos 被禁用，或 client 创建失败且 `NACOS_FAIL_FAST`
  为 `False` 时返回 `None`。
- 异常：client 创建失败时遵循 `NACOS_FAIL_FAST`。

## `register_instance()`

请求注册当前服务实例。

- 返回：立即返回 `None`，调用线程不执行 SDK 网络请求或重试。
- 每个 app、每个进程最多运行一个后台注册任务，并复用校验、重试、身份与心跳
  路径。
- 确定性配置错误、client 不可用和线程启动错误遵循 `NACOS_FAIL_FAST`。网络错误无法抛回
  旧调用栈，只会把安全错误类型写入本地状态。
- 注册完成后重复调用为幂等操作；注册中采用 single-flight。失败后可再次显式调用重试。

```python
nacos.register_instance()
status = nacos.get_status()
```

生命周期与部署细节见[服务注册](service-registration.zh-CN.md)。

## `deregister_instance()`

注销当前服务实例。

- 返回：`bool`。实例不存在时不调用 SDK 并返回 `True`；注册中返回 `True` 表示延迟注销已
  接受；已注册时同步注销并返回真实结果。
- 异常：`NACOS_FAIL_FAST` 为 `True` 时抛出 `NacosDeregistrationError`。

```python
nacos.deregister_instance()
```

## `list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)`

列出服务实例。

- 参数：
  - `service_name`（必填）—— 为空时遵循 `NACOS_FAIL_FAST`。
  - `group` —— 回退到 `NACOS_GROUP_NAME`。
  - `healthy_only` —— 默认 `True`。
  - `cluster` —— 回退到 `NACOS_DISCOVERY_CLUSTER`。
  - `metadata` —— 为 `None` 时回退到 `NACOS_DISCOVERY_METADATA`；`{}` 会显式禁用
    配置过滤；匹配包含全部给定键值对的实例。
- 返回：实例 `list`（当 `NACOS_INSTANCE_NORMALIZE` 为 `True` 时为标准化 dict）。
  结果为空时返回空列表。
- 异常：`NACOS_FAIL_FAST` 为 `True` 时抛出 `NacosDiscoveryError`。

```python
instances = nacos.list_instances("user-service", cluster="CANARY")
```

## `get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)`

选择单个健康实例。

- 参数：`strategy` 回退到 `NACOS_DISCOVERY_STRATEGY`（`first`、`random`、
  `weight`）；其余参数同 `list_instances`。
- 返回：单个实例；没有健康实例时返回 `None`。
- 异常：不支持的策略遵循 `NACOS_FAIL_FAST`；`NACOS_FAIL_FAST` 为 `True` 时发现错误
  抛出 `NacosDiscoveryError`。

```python
instance = nacos.get_one_healthy_instance("user-service", strategy="weight")
```

## `get_config(data_id=None, group=None)`

从 Nacos 读取配置内容。

- 参数：`data_id` 未传时回退到 `NACOS_CONFIG_DATA_ID`；`group` 回退到
  `NACOS_CONFIG_GROUP` 再回退到 `NACOS_GROUP_NAME`。
- 返回：配置的原始内容 `str`；`NACOS_FAIL_FAST` 为 `False` 时失败返回 `None`。
  `NACOS_CONFIG_ENABLED=False` 时不调用 SDK，直接返回 `None`。
- 异常：两个 data ID 都为空且 fail-fast 开启时抛出 `NacosValidationError`；其他配置
  失败抛出 `NacosConfigError`。
- 超时：`NACOS_REQUEST_TIMEOUT` 会传给 SDK 2.x 的读取调用。

`get_config()` 只返回 Nacos 配置的原始字符串，不做 YAML、JSON、dict 解析，也不会
写入 Flask `app.config`。

```python
content = nacos.get_config("application.yaml")
```

## `get_status()`

返回扩展的内部状态与非敏感配置。

- 返回：`dict`。不会请求 Nacos，也不会包含 `NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、
  `NACOS_SECRET_KEY`。
- 生命周期字段：`registration_in_progress`、`deregistration_requested` 与
  `last_registration_error_type`；错误字段只包含异常类名，不包含异常消息。

```python
status = nacos.get_status()
```

## `normalize_instance(instance)`

将原始 SDK 实例（dict 或对象属性形式）标准化为标准 dict。

- 返回：标准 dict；对无法标准化的单个实例返回 `None`（记录日志，单个坏实例不会
  抛错）。

```python
normalized = nacos.normalize_instance(raw_sdk_instance)
```

## 异常类型

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
- `NacosClientError` —— Nacos client 创建 / 使用失败。
- `NacosValidationError` —— 确定性输入或数值配置校验失败（`NacosConfigError` 的子类）。
- `NacosRegistrationError` / `NacosDeregistrationError` / `NacosDiscoveryError`
  —— 注册、注销与服务发现失败。
