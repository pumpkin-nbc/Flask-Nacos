# 错误排查

[English](troubleshooting.md) | 简体中文

常见问题及解决方法。每条包含现象、可能原因、排查方法与解决建议。

另请参阅：[配置项](configuration.zh-CN.md) - [API 参考](api-reference.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 1. 应用启动后没有注册到 Nacos

- 现象：Flask 应用已运行，但实例没有出现在 Nacos 中。
- 可能原因：注册被禁用，或自动注册被关闭。
- 排查方法：检查 `NACOS_ENABLED`、`NACOS_REGISTER_ENABLED`、
  `NACOS_AUTO_REGISTER`、`NACOS_AUTO_REGISTER_ON_INIT`；查看日志和 `get_status()`。
- 解决建议：开启相关开关，或显式调用 `nacos.register_instance()`。

## 2. 注册失败：`NACOS_SERVICE_NAME` 为空

- 现象：出现校验错误或注册失败。
- 可能原因：`NACOS_SERVICE_NAME` 缺失或为空。
- 排查方法：打印 `app.config["NACOS_SERVICE_NAME"]`。
- 解决建议：设置非空的 `NACOS_SERVICE_NAME`。

## 3. 注册失败：`NACOS_SERVICE_PORT` 未配置

- 现象：注册因必填字段错误而失败。
- 可能原因：`NACOS_SERVICE_PORT` 未设置，且无法被推断。
- 排查方法：确认该值已设置且为 `1-65535` 范围内的整数。
- 解决建议：显式设置 `NACOS_SERVICE_PORT`。

## 4. 自动识别的 IP 不符合预期

- 现象：注册的 IP 无法被其他服务访问。
- 可能原因：自动识别选到了非预期网卡（容器、多网卡、NAT）。
- 排查方法：查看 Nacos / `get_status()` 中注册的 IP。
- 解决建议：显式设置 `NACOS_SERVICE_IP`。

## 5. Nacos client 初始化失败

- 现象：`get_status()` 中 `client_initialized` 为 `False`。
- 可能原因：`NACOS_SERVER_ADDR` 错误、网络问题或认证失败。
- 排查方法：核对服务地址与连通性；查看日志。
- 解决建议：修正地址/凭据。可临时设置 `NACOS_FAIL_FAST=True` 让错误在启动时暴露。

## 6. 用户名 / 密码错误

- 现象：SDK 返回认证相关错误。
- 可能原因：`NACOS_USERNAME` / `NACOS_PASSWORD` 不正确。
- 排查方法：在 Nacos 控制台核对凭据。
- 解决建议：修正凭据（通过环境变量注入）。

## 7. namespace 配置错误

- 现象：实例/配置明明存在却查不到。
- 可能原因：`NACOS_NAMESPACE_ID` 指向了不同的命名空间。
- 排查方法：在 Nacos 控制台确认命名空间 id。
- 解决建议：设置正确的 `NACOS_NAMESPACE_ID`。

## 8. 服务发现返回空列表

- 现象：`list_instances()` 返回 `[]`。
- 可能原因：没有匹配实例、group/cluster/metadata 过滤不当，或 `healthy_only=True`
  把全部排除了。
- 排查方法：放宽过滤条件、尝试 `healthy_only=False`、确认 group。
- 解决建议：修正 `service_name`/`group`/`cluster`/`metadata`；无匹配时返回空是
  正常的。

## 9. `get_one_healthy_instance()` 返回 None

- 现象：返回 `None`。
- 可能原因：没有匹配的健康实例，或所有权重都非正。
- 排查方法：调用 `list_instances(healthy_only=True)` 查看候选。
- 解决建议：确保存在健康实例；检查 `strategy` 取值。

## 临时实例变为不健康并自动消失

- 现象：服务出现在 Nacos 中，但健康实例数为 0，稍后实例被删除。
- 可能原因：临时实例没有持续发送心跳、Flask 进程已停止，或查询使用了不同的
  namespace/group。
- 排查方法：保持 Flask 进程运行，检查 SDK 心跳日志，确认
  `NACOS_SERVICE_EPHEMERAL=True`、namespace 与 group。`/health/nacos` 只反映本地
  client 初始化状态，不是远端心跳探测。
- 解决建议：使用 Flask-Nacos 默认的 `NACOS_SERVICE_HEARTBEAT_INTERVAL=5.0`，或设置
  另一个大于 0 的有限间隔。不要用初始 `healthy=True` 代替持续心跳。

## 10. 健康检查接口未注册

- 现象：健康检查路径返回 404。
- 可能原因：`NACOS_HEALTH_CHECK_ENABLED` 为 `False`，或路径已被占用。
- 排查方法：检查配置及现有路由/日志。
- 解决建议：启用路由，并/或选择一个未占用的 `NACOS_HEALTH_CHECK_PATH`。

## 11. 理解多 worker 下的“重复注册”

- 现象：Gunicorn/uWSGI 下一个服务出现多个实例。
- 可能原因：这是预期行为——每个 worker 是独立进程，各自注册自己的实例。
- 排查方法：将实例数量与 worker 数量对应。
- 解决建议：无需修复，详见[生产部署](production.zh-CN.md)。如需不同拓扑可使用显式
  注册。

## 12. `NACOS_FAIL_FAST=True` 导致启动失败

- 现象：Nacos 不可达时应用启动崩溃。
- 可能原因：`NACOS_FAIL_FAST=True` 会把 Nacos 错误变成异常。
- 排查方法：查看抛出的异常。
- 解决建议：修复底层 Nacos 问题，或使用 `NACOS_FAIL_FAST=False`（默认），让失败被
  记录并继续启动。

## 13. `get_config()` 返回的是字符串而不是 dict

- 现象：期望得到解析后的对象，却得到字符串。
- 可能原因：`get_config()` 有意返回配置的原始内容。
- 排查方法：检查返回值类型。
- 解决建议：在你的应用代码中按需解析内容。flask-nacos 不做 YAML、JSON、dict 解析，
  也不会写入 `app.config`。

## 14. 从错误信息中读取失败原因

- 现象：某个 Nacos 操作抛出异常，需要确认具体原因。
- 可能原因：注册、服务发现、配置读取的错误都会在消息中包装底层 SDK 失败。
- 排查方法：阅读异常消息。注册/注销错误会给出服务名、IP、端口、group；服务发现错误会
  说明是服务名为空、SDK 查询失败，还是实例结构无法识别；配置读取错误会说明是 client
  不可用还是 SDK 调用失败。
- 解决建议：针对报告的具体原因处理。错误信息中不包含密码、access key 或 secret key。
