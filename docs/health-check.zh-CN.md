# 健康检查

[English](health-check.md) | 简体中文

一个可选的 Flask 路由，用于反映扩展的内部状态。

另请参阅：[配置项](configuration.zh-CN.md) - [生产部署](production.zh-CN.md)。

## 启用路由

```python
app.config.update(
    NACOS_HEALTH_CHECK_ENABLED=True,
    NACOS_HEALTH_CHECK_PATH="/health/nacos",
)
```

当 `NACOS_HEALTH_CHECK_ENABLED=True` 时，路由会在 `init_app(app)` 期间注册。注册是
幂等的：路由或路径已存在时不会导致 Flask 报错。

## 路径配置

`NACOS_HEALTH_CHECK_PATH` 控制路由路径（默认 `/health/nacos`）。

## 返回内容

```json
{
  "status": "ok",
  "nacos_enabled": true,
  "client_initialized": true,
  "registered": true
}
```

当 Nacos 被禁用时 `status` 为 `"disabled"`；当 client 初始化失败时为 `"error"`。
已知时会包含服务标识字段（`service_name`、`service_ip`、`service_port`）。

## 适用范围

- 该路由只反映扩展的内部状态。
- 它不会请求 Nacos 服务端，因此接口很快，不受 Nacos 延迟影响。
- 它适合用于观察本地服务状态，但不是完整的 Nacos 连通性探测，因此返回 `ok` 本身
  并不保证 Nacos 服务端可达。
