# 生产部署

[English](production.md) | 简体中文

在生产环境中运行 flask-nacos 的建议。

另请参阅：[配置项](configuration.zh-CN.md) -
[服务注册](service-registration.zh-CN.md) - [错误排查](troubleshooting.zh-CN.md)。

## Gunicorn

```bash
gunicorn "app:create_app()" -w 4 -b 0.0.0.0:5000
```

每个 worker 都是独立进程并各自执行 `init_app`，因此注册状态按进程区分。

## uWSGI

uWSGI 的行为与 Gunicorn 类似：每个 worker 进程各自注册和注销自己的实例。如果希望
显式控制，可设置 `NACOS_AUTO_REGISTER_ON_INIT=False`，并在 post-fork 钩子中注册。

## 多 worker 注册

在多 worker 服务器下，主进程 fork 出多个 worker，每个 worker 各自注册自己的实例。
flask-nacos 会记录执行注册的进程 ID：

- `NACOS_REGISTER_ONCE_PER_PROCESS=True`：同一进程内，`register_instance()` 首次
  成功后重复调用会被跳过；fork 出的新 worker（新 pid）可注册自己的实例。
- 退出时，某个进程只会注销它自己注册的实例。

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

## 日志安全

敏感信息（`NACOS_PASSWORD`、`NACOS_ACCESS_KEY`、`NACOS_SECRET_KEY`）不会写入日志。
也请保持你自己的应用日志中不含凭据。

## 敏感信息不要进入代码仓库

切勿提交真实凭据、内部 Nacos 地址或内部 IP。建议通过环境变量或密钥管理服务注入
配置。
