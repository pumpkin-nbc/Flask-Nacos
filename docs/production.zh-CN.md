# 生产部署

[English](production.md) | 简体中文

## 普通 WSGI 启动

使用默认的 `NACOS_AUTO_REGISTER=True` 时，普通非预加载应用工厂会在
`init_app(app)` 执行时调度注册。Client 创建与 Naming I/O 由一个 daemon收敛 Worker完成。

启动时遇到已确认的瞬时网络故障，Worker会先使用配置的有限重试预算，随后保持为低频、
可中断的生命周期自恢复 owner；注册收敛、目标改变、shutdown开始或后续失败不再属于瞬时
故障时结束。这包括认证 SDK `2.0.11` Client构造期间经过验证的瞬时故障；自恢复不依赖
HTTP 请求、readiness或其他业务触发。结构化 HTTP 401/403 等认证拒绝不会进入长期 Recovery。

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
NACOS_DEREGISTER_ON_EXIT = False
```

也可以由单一外部协调者负责注册与注销。每个 worker拥有不同 IP 或端口时，默认的
`NACOS_DEREGISTER_ON_EXIT=True` 才可能合适。

## 退出行为

`NACOS_DEREGISTER_ON_EXIT=True` 时，已安装的退出回调会把当前 PID Runtime 标记为
shutting down 并唤醒重试等待。此后普通生命周期路径不能再启动 Naming RPC。

- `NACOS_DEREGISTER_ON_EXIT=False` 时不安装远端注销回调，因此进程退出时不等待 Naming，
  也不执行远端清理。
- 设为 `True` 时，只可能等待已经在执行的那一笔 Naming RPC，使用其剩余超时加少量调度
  余量，并设置五秒等待上限；随后最多执行一次基于准确缓存身份的退出注销。

该配置不会禁止显式 `deregister_instance()`。退出清理只在解释器正常关闭时尽力执行；
`SIGKILL`、容器强制终止或宿主机故障都无法保证回调运行。

活动 RPC 的 timeout 快照来自实际 SDK Client 的 `default_timeout`，而不是只用于配置中心的
`NACOS_REQUEST_TIMEOUT`。SDK 值缺失、读取抛错、为布尔/非数字/非有限数或不大于零时，
使用三秒回退值。

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

不要让多个 Gunicorn 或 Celery进程共同写入同一个轮转日志文件。推荐输出到控制台并由进程
管理器收集，或由宿主应用配置进程安全的日志管道。Flask-Nacos 不删除、关闭或接管宿主应用
安装的 Handler；1.1.1 不增加多进程文件轮转机制。

应只选择一种不重复输出的拓扑：

```python
# console/file Handler 全部由宿主应用管理。
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = False
NACOS_LOG_FILE_ENABLED = False
NACOS_LOG_PROPAGATE = True
```

```python
# 只输出容器 stdout。
NACOS_LOG_ENABLED = True
NACOS_LOG_CONSOLE_ENABLED = True
NACOS_LOG_FILE_ENABLED = False
NACOS_LOG_PROPAGATE = False
```

Nacos 用户名/密码或 AK/SK 应放入环境变量或密钥管理器。不要通过无鉴权接口返回完整应用
配置或内部状态。

## HTTPS 限制

当前支持的同步 Nacos SDK 2.x 在 HTTPS 服务端证书校验方面存在限制。应将其视为部署风险：
使用可信私有网络、具备适当控制的终止代理，或其他经过验证的传输边界，直到上游 SDK能力
满足安全策略。

## 健康与观测

`/health/nacos` 与 `get_status()` 只反映本地生命周期，不查询 Nacos，也不读取 SDK 心跳
成功状态。就绪策略要求当前 Nacos 可达时，请增加独立远端探针。

瞬时启动故障自恢复期间可能持续看到 `operation_running=True` 与 `registered=False`；它表示
本地仍在收敛，不是远端健康结果。读取 status 或 health 既不会加速，也不会触发重试。
