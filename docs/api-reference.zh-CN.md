# API 参考

[English](api-reference.md) | 简体中文

Flask-Nacos 1.1.1 将生命周期命令保持精炼并严格绑定 Flask 上下文。显式传入
`app` 时操作指定应用；未传入时必须存在当前 app/request context，不再回退到最近初始化的
应用。

## API 快照（1.1 系列）

```python
from flask_nacos import FlaskNacos

nacos = FlaskNacos()
nacos.init_app(app)

nacos.register_instance(app)       # 立即返回 None
removed = nacos.deregister_instance(app)
status = nacos.get_status(app)
client = nacos.get_client(app)
```

生命周期签名固定为：

```text
register_instance(app=None) -> None
deregister_instance(app=None) -> bool
get_status(app=None) -> Dict[str, Any]
get_client(app=None) -> Any
```

## `FlaskNacos(app=None)` 与 `init_app(app)`

`FlaskNacos(app)` 立即初始化一个应用；`FlaskNacos()` 配合 `init_app(app)` 适用于应用工厂。
初始化会校验当前已启用职责所需的确定性配置并安装本地钩子，但不会创建 Nacos Client。
仅在自动注册开启时于初始化阶段执行注册专用校验；否则延迟到首次显式注册命令。

启用自动注册时，`init_app()` 调用与业务代码相同的公开 `register_instance(app)` 命令，
网络请求由一个 daemon收敛 Worker执行；收敛后退出，不会成为第二套心跳监控。

## 应用选择

生命周期和状态 API 都接受可选 Flask 应用；不传时请使用应用或请求上下文：

```python
with app.app_context():
    nacos.register_instance()
    status = nacos.get_status()
```

无上下文、应用未初始化，或应用属于另一个 `FlaskNacos` 对象时抛出
`FlaskNacosError`。

`.app`、`.config` 和 `.client` 属性遵循相同的当前上下文规则，从而保证多应用隔离。

## `register_instance(app=None)`

将本地目标设为已注册，最多调度一个生命周期 Worker，并在 Client 创建或网络 I/O 之前
返回 `None`。

- 注册进行中或已经完成时重复调用是幂等的。
- UNKNOWN/确定性失败且当前空闲时，再次调用会启动新的有限尝试；已确认瞬时故障会保留现有
  Worker进行低频生命周期自恢复。
- `NACOS_ENABLED=False` 时该命令完全禁用且无副作用。
- 缓存的纯本地确定性注册错误会同步抛出且不提交新的生命周期目标；Thread、Client、SDK、
  超时与连接失败只安全写入本地状态，不由该命令抛出。

临时实例注册成功后，心跳由 SDK接管，Flask-Nacos Worker随即退出，并不是永久心跳线程。

每次失败都会立即分类：确定性失败停止，UNKNOWN在现有有限预算后停止，只有已确认瞬时传输
故障会继续进行可中断、有界退避的自恢复。`NACOS_RETRY_ENABLED=False` 时只执行当前一次
尝试。自恢复不增加远端轮询，也不改变该方法固定返回 `None` 的契约。

## `deregister_instance(app=None)`

将目标设为未注册。返回语义：

- 已注销、活动 Worker接受了新目标、SDK注销成功，或更新的注册命令使本次注销不再需要时
  返回 `True`。
- 仍然需要注销但无法完成时返回 `False`。

空闲且已注册时同步注销；Register Worker活动时由该 Worker收敛到最新目标。

所有注销都使用最近一次成功注册缓存的准确身份，不重新猜测 IP 或实例身份。

## `get_client(app=None)` 与 `.client`

`get_client()` 显式请求所选 app 与当前 PID 可用的 Client。只有扩展禁用时返回 `None`；
本地配置非法时抛出 `NacosConfigError`/`NacosValidationError`，Client构造失败时抛出
`NacosClientError`，并通过异常链保留原始 cause。

读取 `.client` 永远不会创建 Client，只返回当前上下文应用已经缓存的 Client 或 `None`；
无上下文时抛出 `FlaskNacosError`。

Client 创建本身不修改注册目标、注册事实、生命周期 generation 或生命周期错误。

## `get_status(app=None)`

固定返回以下 16 个本地字段：

```python
{
    "enabled": True,
    "pid": 12345,
    "client_created": True,
    "service_name": "demo-service",
    "group_name": "DEFAULT_GROUP",
    "cluster_name": "DEFAULT",
    "service_ip": "203.0.113.20",
    "service_port": 3000,
    "target_registered": True,
    "registered": True,
    "operation_running": False,
    "last_error": None,
    "heartbeat_state": "healthy",
    "last_heartbeat_success_at": 1770000000.25,
    "last_heartbeat_failure_at": None,
    "heartbeat_error_type": None,
}
```

`registered` 是最近一次 Naming 注册/注销成功确认的本地事实，不是实时服务端查询。
`operation_running` 同时覆盖后台注册生命周期与同步注销生命周期。`last_error` 只包含安全的
异常类型或内部错误码。

`heartbeat_state` 表示当前本地临时注册周期最近一次被接受的 SDK 心跳观测：

- `unknown`：临时注册成功，但尚未观察到本周期心跳。
- `healthy`：最近一次有效心跳成功。
- `failing`：最近一次有效心跳失败。
- `not_applicable`：扩展禁用、尚未注册或当前为持久实例。

两个心跳时间字段为 Unix epoch秒或 `None`；`heartbeat_error_type` 只包含安全异常类型，
恢复成功后清除。观测按 app/PID、准确注册身份、注册周期和 monotonic完成顺序隔离；它不会
改变 Lifecycle 状态，也不能证明远端当前健康。

注册前身份来自配置快照，不探测 IP；已注册时优先返回实际缓存的注册身份。

该方法不会创建 Client、调用 SDK、探测 Nacos、探测 IP、启动线程或消费 fork 后待恢复注册。

## 服务发现与配置中心

- `list_instances(service_name, group=None, healthy_only=True, cluster=None, metadata=None)`
  返回标准化实例列表。
- `get_one_healthy_instance(service_name, group=None, strategy=None, cluster=None, metadata=None)`
  选择一个标准化健康实例。
- `get_config(data_id=None, group=None)` 返回原始文本；省略 `data_id` 时使用
  `NACOS_CONFIG_DATA_ID`。
- `normalize_instance(instance)` 返回标准化字典或 `None`。

这些操作使用当前 Flask 上下文，并在需要时惰性创建 app/PID Client。合法空结果仍为
`[]`/`None`；校验、Client、Discovery或Config真实失败会在既有有限重试预算后抛出最具体的
现有领域异常。Flask-Nacos 不解析 YAML 或 JSON 配置内容。

## 异常类型

- `FlaskNacosError`：应用选择或初始化 owner 非法。
- `NacosConfigError`：确定性扩展配置非法。
- `NacosClientError`：SDK Client无法构造或使用。
- `NacosValidationError`：注册或发现输入非法。
- `NacosRegistrationError` / `NacosDeregistrationError`：Naming SDK 未明确成功。
- `NacosDiscoveryError`：发现 SDK 操作失败。
- `NacosLoggingError`：日志配置非法。

运行期生命周期错误通过安全状态与日志观测，不从 `register_instance()` 抛出。
