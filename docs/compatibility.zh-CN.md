# 兼容性

[English](compatibility.md) | 简体中文

本页说明 flask-nacos 支持的运行时版本及其兼容性保证。

`1.1.1` 是当前受支持的发布接口，其 API 快照由发布检查强制执行。

另请参阅：[快速开始](quickstart.zh-CN.md) - [配置项](configuration.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 支持的 Python 版本

flask-nacos 要求 **Python `>=3.8`**。CI 当前逐一验证 Python 3.8 到 3.14。包元数据
不会人为阻止后续 Python 版本安装，但新版本加入 CI 后才进入正式验证范围。

库代码的类型提示保持 Python 3.8 兼容：使用 `typing.Optional` / `typing.List` /
`typing.Dict`，而不是 PEP 604 联合类型（`str | None`）或 PEP 585 内置泛型
（`list[str]`），并且不使用 `match`/`case`。`scripts/check_compatibility.py` 静态检查会
强制这一点，并在 CI 中运行。

## 支持的 Flask 版本

flask-nacos 要求 **Flask `>=1.0`**，不人为设置 Flask 上限。CI 当前验证 Flask 1.0.x、
1.1.x、2.x、3.0.x、3.1.x 中受 Flask 及其依赖支持的有效组合。

- Flask 1.0.x 到 3.1.x：扩展在普通模式 `FlaskNacos(app)` 与工厂模式
  `init_app(app)` 下均可正常初始化。
- 扩展只使用长期稳定的 Flask API（`app.extensions`、
  `app.add_url_rule`、`app.url_map.iter_rules`、`app.view_functions`、
  `flask.jsonify`），示例使用 `app.route()`，不依赖较新的路由快捷方法。
- 可选的健康检查路由是幂等注册的，因此重复调用 `init_app(app)` 或路由已存在时不会
  报错。
- CI 在 Python 3.8 上分别验证 Flask 1.0.4、1.1.4 及其兼容的 Pallets 依赖栈。
  Flask 3.1 已停止支持 Python 3.8，因此 Python 3.8 使用 Flask 3.0.x；Python 3.9-3.14
  验证可安装的最新 Flask。
- 兼容性指上游支持的运行时组合，不代表每个旧 Flask 都必须与每个较新的 Python 组合。

## 建议的 Nacos 版本

- Nacos 服务端：**2.x**。
- Nacos SDK：`nacos-sdk-python>=2.0.0,<3.0.0`（同步客户端）。

## Naming 失败兼容性

注册生命周期瞬时故障自恢复主要依赖稳定的结构化证据：标准超时/连接异常、选定的网络与 DNS errno、
结构化 HTTP 状态和 SDK错误码。通用 SDK异常保持 UNKNOWN，只使用现有有限重试预算。

经典 SDK 在经过验证的节点不可用路径中会抛出不带结构化 cause 的裸
`nacos.exception.NacosRequestException`。因此 Flask-Nacos 仅为 SDK `2.0.0` 和 `2.0.11`
的 Naming register 与补偿 deregister 保留窄范围私有兼容规则，并要求实际安装的精确类型和
精确失败阶段。SDK `2.0.11` 另外为认证 Client 构造期间、register方向的同一精确异常保留
一项已验证规则；SDK `2.0.0` Client构造、同步/退出注销、同名替代类型、其他方向和未经验证的
SDK版本均不命中。其他 2.x 异常体系继续依据自身结构化证据处理，不假设统一异常层次；
结构化 401/403 证据始终属于确定性错误。

## Heartbeat 可观测兼容性

同步 SDK 2.x 的 `send_heartbeat` 布局只由一个私有 best-effort 身份提取 helper 使用。
关键字参数优先，再回退到已验证位置。完整安全的 service/group/cluster/IP/port 身份拥有独立
警告节流和一次恢复日志；字段缺失、重复、未知或为复杂对象时退化为无状态 `<unknown>`
日志。Flask-Nacos 不会格式化/哈希用户对象，也不会构造可能碰撞的 key；wrapper 始终保持
SDK 返回值或原异常不变。

这仍是 instrumentation兼容层，不是远端监控。每个 Client只有一层 Flask-Nacos heartbeat
wrapper，由日志和可选 Runtime observer共用；按身份节流的日志状态仅属于该 Client，并随其
丢弃。`get_status()` 只暴露当前 app/PID临时注册周期最近一次脱敏观测，health不包含它。
两条路径都不能触发 Lifecycle Recovery，注册后的唯一心跳 owner仍是 SDK。

## Timeout 兼容性

`NACOS_REQUEST_TIMEOUT` 继续只表示配置中心读取 timeout。Naming 使用实际 SDK Client 的
`default_timeout`，shutdown 快照该值用于有界活动 RPC 等待，避免静默改写共享 SDK Client
行为。

## Nacos SDK 返回结构兼容

不同版本的 SDK 返回的服务发现结果结构略有差异。`list_instances()` 使用内部的
`extract_instances()` 工具方法，兼容以下所有结构：

- 普通的实例 `list`
- `{"hosts": [...]}`
- `{"instances": [...]}`
- `{"data": {"hosts": [...]}}`
- `{"data": {"instances": [...]}}`
- `None` 或空列表（视为“没有实例”）

随后每个实例都会经过 `normalize_instance()`，它同时兼容 `dict` 与对象属性形式，以及
camelCase（`serviceName`、`clusterName`）与 snake_case（`service_name`、
`cluster_name`）字段名，并为缺失字段填充合理的默认值。

SDK 返回结构的轻微差异不会导致服务发现整体失败。当结构完全无法识别时，行为遵循
`NACOS_FAIL_FAST`：`NACOS_FAIL_FAST=False`（默认）时返回空列表并记录日志；
`NACOS_FAIL_FAST=True` 时抛出异常。

## Gunicorn / uWSGI 多 worker 注意事项

每个 worker 都是独立进程，注册状态按进程区分。但公布相同
service/group/cluster/IP/port 的 worker 在 Nacos 中仍映射到同一个实例。共享端点应关闭
每个 worker 的退出注销，或使用单一外部生命周期协调者。完整建议见
[生产部署](production.zh-CN.md)。

## SDK 2.x 的 HTTPS 限制

同步 SDK 2.x 没有提供可靠的服务端证书校验控制。HTTPS 部署请使用受信网络，或通过能够
校验证书的 TLS 代理 / sidecar 连接。

## 不支持的能力

本版本有意不包含以下能力：

- `get_config()` 只返回 Nacos 配置的原始内容；不做 YAML、JSON、dict 解析，也不会写入
  Flask `app.config`。
- 本版本没有 `get_config_as_dict()` 辅助方法。
- 本版本没有 `load_config_to_flask()` 辅助方法。
- 不提供动态配置监听、热更新或后台配置线程。
- 不引入 PyYAML 依赖。
