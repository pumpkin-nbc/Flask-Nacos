# 错误排查

[English](troubleshooting.md) | 简体中文

常见问题及解决方法。每条包含现象、可能原因、排查方法与解决建议。

另请参阅：[配置项](configuration.zh-CN.md) - [API 参考](api-reference.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 1. 应用启动后没有注册到 Nacos

- 现象：Flask 应用已运行，但实例没有出现在 Nacos 中。
- 可能原因：Nacos 或自动注册被显式关闭、确定性注册预检失败，或后台注册操作失败。
- 排查方法：检查 `NACOS_ENABLED` 与 `NACOS_AUTO_REGISTER`；查看日志和
  `get_status()`。
- 解决建议：恢复预期的开关（`NACOS_AUTO_REGISTER` 默认值为 `True`），或修复状态中报告的原因后
  显式调用 `nacos.register_instance(app)`。
- 若 `operation_running=True`，生命周期仍在收敛。已确认的瞬时网络故障会让 Worker保持低频
  自恢复，不需要 HTTP 或业务触发。若其变为 `False`，同时 `target_registered=True` 且
  `registered=False`，则最近失败属于确定性/UNKNOWN（或已关闭重试）；请检查 `last_error`
  与安全日志，修复后再次调用 `register_instance(app)`。

## 注册网络错误不会从 `register_instance()` 抛出

- 可能原因：1.1 的注册始终是后台生命周期命令。
- 解决建议：通过 `get_status()` 与日志查看 Nacos 超时、有限重试与瞬时故障生命周期自恢复。
  `NACOS_FAIL_FAST=True` 只同步抛出缓存的确定性注册错误。Thread 创建/启动、Client、
  SDK、超时与连接错误都安全写入状态，不会从 `register_instance()` 抛出。

## 为什么有限重试后 `operation_running=True` 仍持续存在？

- 可能原因：最近注册失败存在可靠瞬时传输故障证据。普通有限预算耗尽后，Register Worker
  继续持有 owner，并使用有界退避与抖动进行低频恢复。
- 排查方法：安全 WARNING 会标明错误类型和 recovery阶段；`get_status()` 仍是无副作用的
  本地视图。
- 解决建议：通常无需额外触发，只需恢复 Nacos/网络。注销或 shutdown 会立即唤醒等待。
  如果进程必须在当前一次失败后停止，可设置 `NACOS_RETRY_ENABLED=False`。认证、参数和
  UNKNOWN SDK失败不会持续进入生命周期自恢复。

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

## 5. Nacos Client 创建失败

- 现象：`client_created` 一直为 `False`、注册以安全 `last_error` 结束，或显式
  `get_client()` 抛出 `FlaskNacosError`。
- 可能原因：`NACOS_SERVER_ADDR` 错误、网络问题或认证失败。
- 排查方法：核对服务地址与连通性；查看日志。
- 解决建议：修正地址/凭据。认证结构属于确定性配置，可用 `NACOS_FAIL_FAST=True` 在启动
  阶段暴露；运行期连接错误仍是后台生命周期错误。

## 6. 用户名 / 密码错误

- 现象：SDK 返回认证相关错误。
- 可能原因：`NACOS_USERNAME` / `NACOS_PASSWORD` 不正确。
- 排查方法：在 Nacos 控制台核对凭据。
- 解决建议：修正凭据（通过环境变量注入）。

## client 初始化前认证配置被拒绝

- 可能原因：`NACOS_USERNAME`/`NACOS_PASSWORD` 或
  `NACOS_ACCESS_KEY`/`NACOS_SECRET_KEY` 缺少一项、同时配置两种认证，或凭据不是字符串。
- 解决建议：只配置一组完整凭据；可临时启用 `NACOS_FAIL_FAST=True` 查看安全的配置错误。

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
- 返回实例的 IP 为空或端口非法时，该实例会被记录并跳过；请在 Nacos 中核对提供方注册的
  `NACOS_SERVICE_IP` 与端口。

## 重试或请求超时配置立即失败

- 可能原因：尝试次数小于 `1` 或不是整数、间隔为负数，或数值为布尔值、NaN、Infinity
  或非数字。
- 解决建议：使用 `NACOS_RETRY_TIMES >= 1`、`NACOS_RETRY_INTERVAL >= 0` 和
  `NACOS_REQUEST_TIMEOUT > 0`。确定性校验失败不会重试。

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
  生命周期状态，不是远端心跳探测。
- 解决建议：使用 Flask-Nacos 默认的 `NACOS_SERVICE_HEARTBEAT_INTERVAL=5.0`，或设置
  另一个大于 0 的有限间隔。不要用初始 `healthy=True` 代替持续心跳。

## 10. 健康检查接口未注册

- 现象：健康检查路径返回 404。
- 可能原因：`NACOS_HEALTH_CHECK_ENABLED` 为 `False`，或路径已被占用。
- 排查方法：检查配置及现有路由/日志。
- 解决建议：启用路由，并/或选择一个未占用的 `NACOS_HEALTH_CHECK_PATH`。

## 11. 多 worker 注册不等于每个 worker 一个 Nacos 实例

- 现象：多个 worker 都执行了注册，但 Nacos 只显示一个实例；或某个 worker 退出后，其他
  worker 仍运行，注册地址却被删除。
- 可能原因：Nacos 使用 service/group/cluster/IP/port 标识实例。多个 worker 公布相同 IP
  和端口时共享同一个实例，尽管 Flask-Nacos 会分别维护它们的本地状态。
- 排查方法：比较完整的注册地址，不要仅比较 worker 数量。
- 解决建议：共享端点设置 `NACOS_AUTO_DEREGISTER=False`，或由单一外部协调者负责注册
  与注销。详见[生产部署](production.zh-CN.md)。

## 12. `NACOS_FAIL_FAST=True` 导致启动失败

- 现象：应用在 `FlaskNacos(app)` / `init_app(app)` 期间崩溃，或采用延迟加载的 WSGI
  服务器直到第一次请求才显示异常。
- 可能原因：`NACOS_FAIL_FAST=True` 会把确定性配置错误变成异常。启用自动注册时，会在
  创建 Client 前校验缺失或非法的注册配置。
- 排查方法：查看异常并确认应用工厂何时执行。启用自动注册时，`NACOS_SERVICE_NAME` 必须
  是非空且不能只包含空白字符的字符串。
- 解决建议：修正非法配置，或使用 `NACOS_FAIL_FAST=False`（默认），让安全错误保持可见
  并继续启动。Gunicorn `--preload` 应设置 `NACOS_AUTO_REGISTER=False`，并在 fork
  后的 worker hook 中注册。

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

## 15. 为什么会出现 `~/logs/nacos/nacos-client-python.log`？

- 现象：即使应用没有配置，也在 `~/logs/nacos/nacos-client-python.log` 生成了日志文件。
- 可能原因：底层 `nacos-sdk-python` 在创建 client 时，若其 logger 没有 handler 就会自行
  添加文件 handler。
- 排查方法：确认该文件是在创建 Nacos client 之后才出现。
- 解决建议：使用 flask-nacos 1.1.0。它会静默 SDK 原生 logger，并将 SDK 初始化指向
  已存在的其他目录，因此不会创建默认文件或 `~/logs/nacos` 目录。不要开启 SDK 原生日志，
  因为其中可能包含敏感请求或配置数据。

## 16. 如何关闭 Flask-Nacos 日志

- 现象：希望扩展完全不产生日志。
- 可能原因：Flask-Nacos 安全日志默认开启（`INFO`，并向你的 handler 传播）；SDK 原生日志
  已始终静默。
- 排查方法：检查 `NACOS_LOG_ENABLED`。
- 解决建议：设置 `NACOS_LOG_ENABLED=False`。不再添加或传播 Flask-Nacos console/file
  handler；SDK 原生日志仍保持静默。

## 17. 如何指定日志目录

- 现象：希望 Flask-Nacos 安全日志写入指定目录。
- 可能原因：未显式请求时不会创建文件。
- 排查方法：确认目标目录可写。
- 解决建议：设置 `NACOS_LOG_ENABLED=True`、`NACOS_LOG_PATH="/var/log/flask-nacos"`，
  并可用 `NACOS_LOG_FILENAME="service.log"` 自定义文件名。如需轮转，同时设置
  `NACOS_LOG_MAX_BYTES` 与
  `NACOS_LOG_BACKUP_COUNT`。SDK 原生日志不会写入该文件。
- 如果旧配置已经在该目录位置创建了普通文件（例如名为 `logs` 的文件），请先重命名或
  删除该旧文件。

## 18. Flask-Nacos 日志关闭后仍出现 `nacos-client-python.log`

- 现象：Flask-Nacos 日志关闭，但默认 SDK 文件仍然出现。
- 可能原因：使用了旧版 flask-nacos，或其他组件在 flask-nacos 配置日志之前就创建了 client。
- 排查方法：确保 `FlaskNacos(app)` / `init_app(app)` 在任何直接构造 `nacos.NacosClient`
  的代码之前执行。
- 解决建议：使用 1.1.0。Flask-Nacos 会在创建 client 前静默 SDK logger，并使 SDK
  初始化不使用用户主目录。直接创建的 SDK client 不受 Flask-Nacos 控制。

## 19. flask-nacos 日志重复输出

- 现象：每条日志出现两次或多次。
- 可能原因：flask-nacos handler 与传播到父级的 handler 同时输出，或多套日志配置各自添加了
  handler。
- 排查方法：检查是否配置了 root logger，以及 `NACOS_LOG_CONSOLE_ENABLED`/`NACOS_LOG_FILE_ENABLED` 是否
  与你自己的 handler 重叠。
- 解决建议：要么使用 flask-nacos 的 handler（设置 `NACOS_LOG_CONSOLE_ENABLED`/`NACOS_LOG_FILE_ENABLED`）
  并设置 `NACOS_LOG_PROPAGATE=False`；要么依赖自己的日志系统，设置
  `NACOS_LOG_PROPAGATE=True` 且不使用 flask-nacos handler。

## 20. 复用 Flask `app.logger`

- 现象：希望 flask-nacos 日志走 `app.logger`。
- 可能原因：默认情况下 flask-nacos 使用自己的命名 logger。
- 排查方法：确认 `app.logger` 已有你想要的 handler。
- 解决建议：按需配置 `NACOS_LOG_CONSOLE_ENABLED`、`NACOS_LOG_FILE_ENABLED`
  和 `NACOS_LOG_PROPAGATE`。Flask-Nacos 不复用或修改 `app.logger` handler；
  SDK 原生日志仍保持静默。

## 21. HTTPS 能否校验 Nacos 服务端证书？

- 现象：需要 Flask 进程与 Nacos 之间使用经过校验的 TLS。
- 可能原因：同步 `nacos-sdk-python` 2.x 没有提供可靠的 HTTPS 证书校验控制。
- 解决建议：使用受信网络，或通过能够验证 Nacos 服务端证书的 TLS 代理 / sidecar；不要
  仅依赖 `https://` 地址。

## 22. 重复 `init_app` 后日志重复

- 现象：多次调用 `init_app(app)` 导致 handler / 日志行成倍增加。
- 可能原因：简单的 handler 设置会在每次调用时重复添加。
- 排查方法：统计 `logging.getLogger("flask_nacos")` 上的 handler 数量。
- 解决建议：1.1.0 无需处理。flask-nacos 会对 handler 去重，重复 `init_app(app)` 不会
  添加第二个 console 或 file handler。
