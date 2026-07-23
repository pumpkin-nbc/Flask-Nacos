# 生产部署

[English](production.md) | 简体中文

在生产环境中运行 flask-nacos 的建议。

另请参阅：[配置项](configuration.zh-CN.md) -
[服务注册](service-registration.zh-CN.md) - [错误排查](troubleshooting.zh-CN.md)。

## Gunicorn

```bash
gunicorn "app:create_app()" -w 4 -b 0.0.0.0:5000
```

每个 worker 都是独立进程并各自执行 `init_app`，因此本地注册状态按进程区分。但公布相同
service/group/cluster/IP/port 的 worker 在 Nacos 中仍对应同一个共享实例。

## uWSGI

uWSGI 的行为与 Gunicorn 类似：每个 worker 都会初始化扩展，但公布相同 IP 和端口的 worker
指向同一个 Nacos 实例。共享端点应关闭 worker 退出注销，或交给单一外部协调者管理生命周期。

## 多 worker 注册

在多 worker 服务器下，主进程 fork 出多个 worker，flask-nacos 会按进程记录注册状态：

- `NACOS_REGISTER_ONCE_PER_PROCESS=True`：同一进程内，`register_instance()` 首次
  成功后重复调用会被跳过；fork 出的新 worker（新 pid）可注册自己的实例。
- 退出时，某个进程只会尝试注销它注册时使用的实例标识。

进程状态相互独立不代表 Nacos 实例相互独立。多个 worker 共享同一个注册地址时，某个 worker
退出可能在其他 worker 仍提供服务时删除共享实例。请设置 `NACOS_DEREGISTER_ON_EXIT=False`，
或由单一外部协调者负责注册与注销。

## Docker

- 将 `NACOS_SERVER_ADDR` 设为容器网络中可达的 Nacos 地址。
- 显式设置 `NACOS_SERVICE_IP` 与 `NACOS_SERVICE_PORT`，以便其他服务能访问到该实例；
  在容器内不要依赖自动识别。
- 通过环境变量注入凭据，不要打进镜像。

本地测试用的 Nacos 见
[`examples/docker-compose-nacos.yml`](../examples/docker-compose-nacos.yml)
（仅限本地使用）。

## 显式配置服务 IP 与端口

生产环境请始终显式配置 `NACOS_SERVICE_NAME`、`NACOS_SERVICE_IP`、
`NACOS_SERVICE_PORT`。

## 自动注销注意事项

基于 `atexit` 的注销是“尽力而为”：在硬杀（`SIGKILL`）或崩溃时可能不会执行。Nacos
最终会剔除不健康的临时实例，但为实现优雅下线，请确保进程能够干净退出。

## `NACOS_AUTO_REGISTER_ON_INIT`

当你希望精确控制注册时机（例如在 post-fork 钩子或管理命令中）而不是在 `init_app`
阶段隐式注册时，将其设为 `False`。

## `NACOS_DEREGISTER_ON_EXIT`

控制是否安装 `atexit` 注销处理器（仅当 `NACOS_AUTO_DEREGISTER` 也为 `True` 时）。

## 生产环境日志

`NACOS_LOG_*` 只控制 Flask-Nacos 生成的脱敏安全日志。SDK 原生日志（来自
`nacos-sdk-python`）可能包含敏感请求或响应数据，因此始终静默。建议：

1. 如需文件日志，设置 `NACOS_LOG_ENABLED=True` 并配置 `NACOS_LOG_PATH` 与
   `NACOS_LOG_FILENAME`（如需轮转再配置相关参数）。
2. 容器环境优先输出到 stdout：设置 `NACOS_LOG_ENABLED=True`、
   `NACOS_LOG_CONSOLE_ENABLED=True` 和 `NACOS_LOG_FILE_ENABLED=False`。
3. 若项目已有统一日志系统，设置 `NACOS_LOG_PROPAGATE=True` 和 `NACOS_LOG_FILE_ENABLED=False`，
   让现有 handler 负责格式化与路由。
4. 若连 Flask-Nacos 安全日志也不希望产生，设置 `NACOS_LOG_ENABLED=False`。
5. 生产环境不要依赖 nacos-sdk-python 的默认日志路径。
6. 日志默认关闭，因此不创建用户配置的目录或 `~/logs/nacos`；启用后默认写入
   `./logs/flask-nacos.log`。

## 日志安全

敏感信息（`NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、`NACOS_SECRET_KEY`）不会写入日志。
也请保持你自己的应用日志中不含凭据。

## HTTPS 证书校验

同步 `nacos-sdk-python` 2.x 没有提供可靠的 HTTPS 证书校验控制。请使用受信网络，或通过
能够验证 Nacos 服务端证书的 TLS 代理 / sidecar 终止 TLS。不要认为地址使用 `https://`
就已经验证了服务端身份。

## 敏感信息不要进入代码仓库

切勿提交真实凭据、内部 Nacos 地址或内部 IP。建议通过环境变量或密钥管理服务注入
配置。
