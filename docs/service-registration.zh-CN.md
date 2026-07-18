# 服务注册

[English](service-registration.md) | 简体中文

flask-nacos 如何注册与注销服务实例。

另请参阅：[配置项](configuration.zh-CN.md) - [API 参考](api-reference.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 自动注册

当 `NACOS_REGISTER_ENABLED`、`NACOS_AUTO_REGISTER` 与
`NACOS_AUTO_REGISTER_ON_INIT` 都为 `True` 时，会在 `init_app(app)` 期间注册服务。

## 手动注册

`NACOS_REGISTER_ENABLED` 只控制初始化阶段的自动注册，不会禁用显式手动调用。

```python
nacos.register_instance()
```

## 注册参数

注册前会校验以下参数；非法值遵循 `NACOS_FAIL_FAST` 规则：

- `NACOS_SERVICE_NAME` —— 必填，不能为空。
- `NACOS_SERVICE_PORT` —— 必填，`1-65535` 范围内的整数。
- `NACOS_SERVICE_WEIGHT` —— 大于 `0` 的有限数字。
- `NACOS_SERVICE_METADATA` —— 必须是 `dict`。
- `NACOS_SERVICE_EPHEMERAL` —— 必须是 `bool`。
- `NACOS_SERVICE_HEARTBEAT_INTERVAL` —— 大于 `0` 的有限数字，单位为秒。

## 临时实例心跳

临时实例依靠 SDK 心跳保持健康。注册临时实例时，Flask-Nacos 会把
`NACOS_SERVICE_HEARTBEAT_INTERVAL` 传给 SDK 2.x，默认值为 `5.0` 秒。初始的
`healthy=True` 只描述注册时的状态，不能替代持续心跳。

持久实例不会收到心跳间隔参数。如果临时实例先出现健康实例数为 0、随后又消失，请检查
心跳日志、`NACOS_SERVICE_EPHEMERAL`、namespace/group 是否一致，以及 Flask 进程是否
仍在运行。`/health/nacos` 仅反映本地 client 初始化状态，不能证明 Nacos 在持续收到心跳。

## IP 自动识别

若未设置 `NACOS_SERVICE_IP`，扩展会尝试识别本机出口 IP。识别失败时，行为遵循
`NACOS_FAIL_FAST`。

生产建议：显式配置 `NACOS_SERVICE_IP`。在容器、多网卡主机或 NAT 环境下，自动识别到
的地址可能无法被其他服务访问。同时请显式设置 `NACOS_SERVICE_NAME` 与
`NACOS_SERVICE_PORT`。

## 幂等注册

注册是幂等的。当 `NACOS_REGISTER_ONCE_PER_PROCESS=True` 时，同一进程内一旦
`register_instance()` 成功，后续调用即为 no-op。当 fork 出新 worker（进程 ID 变化）
时，新 worker 可注册自己的实例。

## 多进程注册（Gunicorn / uWSGI）

在 Gunicorn / uWSGI 下，主进程会 fork 多个 worker，每个 worker 都会执行 `init_app`
并注册自己的实例。flask-nacos 会记录执行注册的进程 ID，因此某个 worker 只会注销它
自己注册的实例。部署建议见[生产部署](production.zh-CN.md)。

如果希望显式控制，可设置 `NACOS_AUTO_REGISTER_ON_INIT=False`，并在 post-fork 钩子中
调用 `nacos.register_instance()`。

## 注销

```python
nacos.deregister_instance()
```

注销是幂等的，注销后再次调用不会报错。

## 自动注销

当 `NACOS_AUTO_DEREGISTER` 与 `NACOS_DEREGISTER_ON_EXIT` 都为 `True` 时，会通过
`atexit` 处理器在进程退出时注销由当前扩展成功注册的实例；从未注册或注册失败时不执行
注销。每个扩展实例最多注册一次该处理器。
