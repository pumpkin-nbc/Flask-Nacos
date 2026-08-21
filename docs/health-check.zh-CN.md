# 健康检查

[English](health-check.md) | 简体中文

## 启用路由

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

路由在 `init_app(app)` 期间安装，固定返回七个字段：

```json
{
  "status": "ok",
  "enabled": true,
  "client_created": true,
  "target_registered": true,
  "registered": true,
  "operation_running": false,
  "last_error": null
}
```

状态规则：

```text
扩展禁用                                      -> disabled
registered 等于 target_registered             -> ok
operation 正在运行且没有生命周期错误           -> ok
其他尚未收敛状态                               -> error
```

`registered` 是最近一次成功 Naming 注册/注销 RPC确认的本地事实。`status=ok` 表示本地
生命周期已经收敛，或正在无记录错误地收敛；两者都不代表 Nacos 当前一定可达，也不保证远端
实例此刻仍存在。

SDK 心跳警告节流和恢复日志只是各 Client wrapper 内部的私有可观测状态，不进入本响应，
不会修改 `registered`，也不会唤醒或创建 Lifecycle Worker。需要实时 Nacos 就绪性时，应
使用独立远端探针。

健康路由不会创建 Client、执行 SDK/Nacos I/O、探测 IP、启动线程或恢复 fork 后待执行的
自动注册。因此完全惰性的启用状态（`client_created=false`，目标与事实均为 false）仍然健康。

`NACOS_ENABLED=False` 时固定为：

```json
{
  "status": "disabled",
  "enabled": false,
  "client_created": false,
  "target_registered": false,
  "registered": false,
  "operation_running": false,
  "last_error": null
}
```

需要确认远端 Nacos 可达时，请使用外部监控或单独的应用探针。
