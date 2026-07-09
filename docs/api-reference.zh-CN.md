# API 参考

[English](api-reference.md) | 简体中文

`FlaskNacos` 扩展的公开 API。所有错误行为都由 `NACOS_FAIL_FAST` 控制（见
[配置项](configuration.zh-CN.md)）：为 `False`（默认）时失败会被记录并返回安全默认
值；为 `True` 时抛出异常。

另请参阅：[快速开始](quickstart.zh-CN.md) - [配置项](configuration.zh-CN.md)。

## `FlaskNacos(app=None)`

构造扩展。提供 `app` 时会立即调用 `init_app(app)`（Flask 普通模式）；省略时可稍后
调用 `init_app(app)`（工厂模式）。

```python
from flask_nacos import FlaskNacos

nacos = FlaskNacos(app)          # 普通模式
nacos = FlaskNacos()             # 工厂模式；稍后调用 init_app
```

## `init_app(app)`

针对 Flask `app` 初始化扩展：加载配置、惰性创建 Nacos client、注册健康检查路由
（若启用）、自动注册服务（若启用）。会将扩展实例保存到 `app.extensions["nacos"]`。

- 参数：`app` —— Flask 应用。
- 返回：`None`。
- 异常：client / 注册错误遵循 `NACOS_FAIL_FAST`。

## `get_client()`

返回底层 Nacos SDK client，首次使用时创建。

- 返回：SDK client 对象；当 Nacos 被禁用，或 client 创建失败且 `NACOS_FAIL_FAST`
  为 `False` 时返回 `None`。
- 异常：client 创建失败时遵循 `NACOS_FAIL_FAST`。

## `register_instance()`

注册当前服务实例。

- 返回：`bool` —— 成功为 `True`；`NACOS_FAIL_FAST` 为 `False` 时失败返回 `False`。
- 异常：`NACOS_FAIL_FAST` 为 `True` 时抛出 `NacosValidationError` /
  `NacosRegistrationError`。
- 说明：幂等；当 `NACOS_REGISTER_ONCE_PER_PROCESS=True` 时，同一进程内重复调用为
  no-op。

```python
nacos.register_instance()
```

## `deregister_instance()`

注销当前服务实例。

- 返回：`bool` —— 成功为 `True`，否则为 `False`（`NACOS_FAIL_FAST` 为 `False`
  时）。幂等，注销后再次调用不会报错。
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
  - `metadata` —— 回退到 `NACOS_DISCOVERY_METADATA`；匹配包含全部给定键值对的实例。
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

## `get_config(data_id, group=None)`

从 Nacos 读取配置内容。

- 参数：`data_id`（必填）；`group` 回退到 `NACOS_CONFIG_GROUP` 再回退到
  `NACOS_GROUP_NAME`。
- 返回：配置的原始内容 `str`；`NACOS_FAIL_FAST` 为 `False` 时失败返回 `None`。
- 异常：`NACOS_FAIL_FAST` 为 `True` 时抛出 `NacosConfigError`。

`get_config()` 只返回 Nacos 配置的原始字符串，不做 YAML、JSON、dict 解析，也不会
写入 Flask `app.config`。

```python
content = nacos.get_config("application.yaml")
```

## `get_status()`

返回扩展的内部状态与非敏感配置。

- 返回：`dict`。不会请求 Nacos，也不会包含 `NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、
  `NACOS_SECRET_KEY`。

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
- `NacosValidationError` —— 注册参数校验失败（`NacosConfigError` 的子类）。
- `NacosRegistrationError` / `NacosDeregistrationError` / `NacosDiscoveryError`
  —— 注册、注销与服务发现失败。
