# 生产部署

[English](production.md) | 简体中文

## 普通 WSGI 启动

使用默认的 `NACOS_AUTO_REGISTER=True` 时，普通非预加载应用工厂会在
`init_app(app)` 执行时调度注册。Client 创建与 Naming I/O 由短生命周期 daemon Worker完成。

请显式配置消费者可访问的 `NACOS_SERVICE_IP` 与 `NACOS_SERVICE_PORT`；Flask 能在本机
localhost 访问，不代表其他机器可以访问注册到 Nacos 的地址。

## Gunicorn `--preload`

预加载模式会在 worker fork 前由 master导入并初始化 Flask 应用。在此时启动 SDK Runtime
或注册既有 fork 风险，也可能让 master注册。推荐配置：

```python
# application configuration
NACOS_AUTO_REGISTER = False
```

然后在 Gunicorn 的 worker hook 中，于 fork 完成后调用现有生命周期命令：

```python
def post_fork(server, worker):
    from myservice import app, nacos

    nacos.register_instance(app)
```

Flask-Nacos 不猜测服务器类型或 worker数量，也不增加 Gunicorn 专用公开 API。PID Runtime
重建能阻止 worker复用父进程 Client、锁、Event 或注册事实，但无法撤销 preload master
已经启动的工作。

## 多 worker 与共享端点

多个 worker使用相同服务身份与 IP:port（即相同 service/group/cluster/IP/port）时，在
Nacos 中是同一个实例；虽然每个进程拥有独立本地 Runtime 和 Client，但一个 worker退出时
不应删除其他 worker仍在提供服务的共享实例：

```python
NACOS_AUTO_DEREGISTER = False
```

也可以由单一外部协调者负责注册与注销。每个 worker拥有不同 IP 或端口时，默认的
`NACOS_AUTO_DEREGISTER=True` 才可能合适。

`NACOS_REGISTER_ENABLED=False` 会阻止新注册，但不会阻止清理当前 Runtime 已经注册的实例。

## 退出行为

退出回调会把当前 PID Runtime 标记为 shutting down 并唤醒重试等待。此后普通生命周期路径
不能再启动 Naming RPC。

- `NACOS_AUTO_DEREGISTER=False` 时立即返回，不等待，也不修改用户注册目标。
- 设为 `True` 时，只可能等待已经在执行的那一笔 Naming RPC，使用其剩余超时加少量调度
  余量，并设置五秒等待上限；随后最多执行一次基于准确缓存身份的退出注销。

退出注销不重试、不调度后续注册，也不会猜测缺失身份。

## 容器部署

优雅停止时间应覆盖 SDK 请求超时。显式设置注册 IP/端口，并优先使用控制台日志：

```python
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = True
NACOS_LOG_FILE_ENABLED = False
```

## 日志与密钥

SDK 原生日志被隔离，Flask-Nacos 不创建 `~/logs/nacos`。扩展安全日志默认关闭。启用文件
日志时，`NACOS_LOG_PATH` 默认 `./logs`，`NACOS_LOG_FILENAME` 默认
`flask-nacos.log`。

Nacos 用户名/密码或 AK/SK 应放入环境变量或密钥管理器。不要通过无鉴权接口返回完整应用
配置或内部状态。

## HTTPS 限制

当前支持的同步 Nacos SDK 2.x 在 HTTPS 服务端证书校验方面存在限制。应将其视为部署风险：
使用可信私有网络、具备适当控制的终止代理，或其他经过验证的传输边界，直到上游 SDK能力
满足安全策略。

## 健康与观测

`/health/nacos` 与 `get_status()` 只反映本地生命周期，不查询 Nacos，也不读取 SDK 心跳
成功状态。就绪策略要求当前 Nacos 可达时，请增加独立远端探针。
