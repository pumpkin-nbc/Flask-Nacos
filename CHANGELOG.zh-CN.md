# 更新日志

[English](CHANGELOG.md) | 简体中文

本文件记录 Flask-Nacos 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## 1.1.1

### 修复

- 修复启用认证时，Nacos 暂不可用导致 Client 构造失败后注册生命周期无法自行恢复的问题。
  SDK `2.0.11` 在精确 `CLIENT_CREATE/register` 阶段抛出的
  `NacosRequestException` 现在进入既有瞬时故障 Recovery。
- 保持结构化 401/403 认证失败为确定性错误；未经验证的 SDK版本、阶段、方向和异常类型仍为
  `UNKNOWN`，只使用有限重试预算。
- 修复同一 SDK Client 为多个实例发送心跳时日志状态串扰。警告节流与恢复现在按准确的
  service/group/cluster/IP/port 身份隔离；不安全或不完整身份退化为无状态 `<unknown>`
  日志，不构造可能碰撞的 key。
- 修复相同实例身份重复注册时的心跳观测串扰。私有 monotonic周期与完成顺序门禁会拒绝迟到
  或乱序回调；日志与 Runtime观测共用一个幂等安装的 Client wrapper。
- 修复 shutdown 活动 Naming RPC timeout 快照，改为读取实际 SDK Client 的
  `default_timeout`。`NACOS_REQUEST_TIMEOUT` 继续只属于配置中心，非法 SDK timeout 仍使用
  有界三秒回退值。

### 变更

- 删除无实际作用的 `NACOS_STATUS_ENABLED`，不保留别名或迁移分支；
  `get_status()` 仍始终可用且无副作用。
- 删除配置驱动的错误模式开关，不保留别名或迁移分支。启用自动注册时，纯本地确定性配置
  错误会使初始化事务失败；显式注册会在改变生命周期状态前拒绝该错误，运行期失败仍保留为
  Worker异步状态。
- 同步 Client、Discovery与Config操作不再把真实失败伪装为空结果，而是保留最具体的安全
  领域异常与 cause；合法空结果和能力禁用契约不变。
- 删除普通请求驱动的 fork后恢复。pending自动注册仅由显式注册或真实 Client、Discovery、
  Config SDK操作非阻塞消费，并继续共用现有 app/PID Client acquisition路径。
- 日志总开关或文件输出关闭时忽略对应未使用配置；已启用日志能力的非法配置或 Handler构造
  失败统一抛出 `NacosLoggingError`。
- 使用唯一的 `NACOS_DEREGISTER_ON_EXIT` 配置明确进程退出清理职责；关闭时不安装远端
  清理回调，也不会阻止显式 `deregister_instance()`。
- 降低 SDK heartbeat wrapper 日志噪声：普通成功为 `DEBUG`，首次/类型变化失败为
  `WARNING`，相同失败 60 秒内节流，失败后每个身份的首次成功记录一次恢复 `INFO`。
- 将无副作用的 `get_status()` 快照从 12 个字段扩展为 16 个，增加当前临时注册周期的本地
  心跳状态、最近成功/失败 Unix时间和安全错误类型。health仍保持七字段本地生命周期响应，
  不使用心跳观测判断状态。
- 增加 Python 3.8/Flask 1.1.4/gevent兼容测试，并将 SDK兼容矩阵固定为明确验证的
  `2.0.0` 与 `2.0.11`。
- 扩展高并发、fork、heartbeat 隔离、timeout 与显式启用的真实 Nacos 回归，包含仅用于
  测试的 TCP 恢复 gate。

### 兼容性

- 公共方法签名、七字段 health结构、目标状态生命周期、fork/shutdown行为及 SDK心跳归属
  保持不变；本地 `get_status()` 结构按文档增加四个 heartbeat字段。
- 生命周期自恢复仍不执行远端实例监控；本地状态收敛后 Worker退出，心跳与连接维护继续由
  Nacos SDK负责。

## 1.1.0

### 新增

- 通过 `register_instance(app=None) -> None` 新增目标状态生命周期收敛，生命周期 Worker
  按 app/PID 归属，Naming RPC全局 single-flight。
- 新增固定本地状态模型：`target_registered`、`registered`、`operation_running`、安全
  `last_error`，以及 Client 与实际注册身份快照。
- 新增 Naming 内部成功/失败/跳过三态、准确注册身份复用、可中断重试、fork Runtime
  重建与有界退出清理。
- 为有明确证据的瞬时传输故障新增注册生命周期自恢复：先保持现有有限尝试预算，耗尽后使用
  可中断、带抖动的有界退避；确定性失败立即停止，UNKNOWN失败在有限上限停止。
- CI 扩展到 Python 3.14，以及 Flask 1.0.x、1.1.x、2.x、3.0.x、3.1.x 的有效组合。
- wheel 与 sdist 固定生成 Core Metadata 2.4，在保留 PEP 639 许可证元数据的同时兼容
  当前打包工具的严格校验。

### 变更

- `register_instance()` 接受可选 Flask app并固定返回 `None`，Client 创建、SDK 注册、
  生命周期重试与心跳启动均由具名 daemon 线程执行。
- 删除重复的初始化专用自动注册开关；`NACOS_AUTO_REGISTER` 现在是唯一自动注册开关，
  初始化通过公开注册命令调度后台工作且不等待 Nacos。
- 删除重复的注册权限开关。`NACOS_ENABLED` 负责控制整体集成，`NACOS_AUTO_REGISTER`
  只控制自动注册；显式 `register_instance()` 继续表达注册命令。
- 关闭自动注册时按需执行注册专用校验；自动、显式与 fork 后 pending 恢复共享同一调用期
  编排流程，且不增加 Runtime 或公开状态字段。
- Client 按 Flask app/PID惰性创建；状态、健康与 `.client` 缓存读取无 SDK副作用。
- `deregister_instance(app=None)` 保证最后一次生命周期命令生效，并保持幂等与同步清理契约。
- `NACOS_DEREGISTER_ON_EXIT` 是唯一退出注销开关。
- 有限重试与自恢复继续统一由 Register Worker负责。Client 创建和 Naming失败共用保守分类，
  但 Client状态不会混入 Naming RPC Outcome元数据；收敛成功后心跳仍完全交由 Nacos SDK。
- 同步双语 Quickstart 与可运行的 beginner 示例，补齐完整工厂案例实际读取的全部环境变量，
  并移除简化示例中硬编码的演示凭据。

### 兼容性

- 生命周期运行时错误通过安全本地状态与日志观测；纯本地确定性注册错误会在提交生命周期
  状态前抛出。
- Python 运行要求继续为 `>=3.8`；Flask 依赖改为无额外上限的 `>=1.0`。
- 开发类型检查固定使用 mypy `<1.15`，这是仍能在 Python 3.8 运行并明确以其为检查
  目标的最后一个版本系列。

## 1.0.2

### 新增

- 新增脱敏日志配置：`NACOS_LOG_ENABLED`、`NACOS_LOG_CONSOLE_ENABLED`、
  `NACOS_LOG_FILE_ENABLED`、`NACOS_LOG_PATH`、`NACOS_LOG_FILENAME`、
  `NACOS_LOG_FORMAT`、`NACOS_LOG_PROPAGATE`、`NACOS_LOG_MAX_BYTES` 与
  `NACOS_LOG_BACKUP_COUNT`。
- 新增按等级着色的控制台日志：`DEBUG` 蓝色、`INFO` 绿色、`WARNING` 黄色、
  `ERROR` 红色、`CRITICAL` 加粗红色。
- 新增脱敏的临时实例心跳成功和失败日志。
- 新增日志、事务式初始化、注册身份和服务发现校验的回归测试。

### 变更

- `NACOS_LOG_*` 只控制脱敏后的 Flask-Nacos 日志；SDK 原生 logger 始终静默，且不再
  创建 `~/logs/nacos`。
- 日志默认关闭，关闭时不会创建已配置的目录；启用后控制台和轮转文件默认同时开启，
  默认写入 `./logs/flask-nacos.log`，单文件 10 MiB，并保留五个备份。
- 文件日志保持纯文本，不包含 ANSI 转义符；Flask-Nacos 使用命名 logger
  `flask_nacos`，且不会配置 root logger。
- 注册成功后缓存并在重试、注销时复用精确服务身份；持久实例忽略心跳配置。
- 服务发现会在 SDK 调用前校验 service、group、cluster 和 filter，把 cluster 过滤传给
  SDK 2.x，并在本地进行防御性过滤。
- 状态示例只公开安全字段；生产文档说明多 worker 共享实例身份、SDK 2.x HTTPS 证书
  校验限制和安全日志默认行为。

### 修复

- 修复库与 SDK 的日志副作用、重复 handler、意外日志文件，以及凭据、请求数据或配置
  正文可能通过应用、root、控制台或文件 handler 泄露的问题。
- 修复严格初始化失败后残留部分应用或扩展状态的问题。
- 修复 client 已初始化但不可用时，容错操作仍抛出异常的问题；这些操作现在返回
  文档约定的安全默认值。
- 修复注销时重新解析服务身份、没有使用实际注册身份的问题。

### 说明

- `get_config()` 仍只返回原始内容；Flask-Nacos 不解析 YAML、JSON 或字典，也不会把
  远端内容加载进 `app.config`。

## 1.0.1

### 修复

- 在 `init_app()` 中预检已启用的自动注册配置，使确定性校验错误在创建 client 或写入
  部分扩展状态之前抛出；关闭自动注册时，未配置服务名的应用仍可仅使用配置中心和服务发现。

## 1.0.0

### 新增

- 发布 Flask-Nacos 首个稳定版本。
- 新增 1.0 系列稳定 API 文档。
- 新增 PyPI 发布前最终验收清单。
- 新增稳定安装与 smoke test 验证步骤。
- CI 新增 Python 3.13 覆盖，并设置 85% 覆盖率下限。
- 新增多应用状态、并发生命周期调用、fork 后锁、配置默认值/超时和 SDK client 构造的
  回归测试。
- 新增可运行的应用工厂示例及内容一致的中英文端到端接入指南。
- 新增初学者示例，并将中英文 Quickstart 重写为渐进式 Python 入门教程，覆盖注册、健康
  检查、配置中心和服务发现。
- 为初学者示例新增基于环境变量的认证配置、用户名/密码与 AK/SK 独立测试，以及可选启用的
  真实 Nacos 认证测试。
- 新增 `NACOS_SERVICE_HEARTBEAT_INTERVAL`，默认值为经过校验的 `5.0` 秒，用于 SDK
  维护临时实例心跳。
- 新增安全策略与私密漏洞报告说明。
- 新增发布标签与包索引不可变版本的预检。

### 变更

- 首个公开版本采用 Apache License 2.0。
- 强化配置隔离、数字校验、服务发现过滤和自动注销行为。
- 新增包检查，确保源码和构建产物的许可证元数据一致。
- 将公共 API 标记为稳定。
- 改进 README 在 PyPI 上的展示。
- 改进 TestPyPI 与 PyPI 发布文档。
- 改进发布包最终验收脚本。
- 将 CI 拆分为一次质量/构建任务和轻量 Python/Flask 测试矩阵，避免重复执行高开销检查。
- `get_config()` 允许省略 `data_id`，此时回退到 `NACOS_CONFIG_DATA_ID`，并将
  `NACOS_REQUEST_TIMEOUT` 传给 SDK 2.x。
- SDK 导入和 client 构造失败统一使用 `NacosClientError`，并保留原异常作为 cause。
- 明确 `NACOS_SERVER_ADDR` 用于定位 Nacos，而 `NACOS_SERVICE_IP` 是向消费者公布的
  Flask 服务地址。
- 记录通过集中式 `app/extensions.py` 和 `extension_config(app)` 应用工厂模式接入
  Flask-Nacos 的方法。
- 将长期 PyPI Token 发布替换为受保护的 OIDC Trusted Publishing TestPyPI/PyPI 任务。
- 强化发布校验，拒绝陈旧产物和错误的 PyPI 链接，并分别安装测试 wheel 和 sdist。

### 修复

- 将 SDK 返回 `False` 的注册/注销结果视为可重试失败，且不破坏生命周期状态。
- 通过现有严格错误行为拒绝不完整或混用的认证凭据，以及非法重试和请求超时数字。
- 跳过端点异常的发现实例，正确解析字符串布尔值，并处理非法权重。
- 向 Nacos SDK 2.x 传递心跳间隔，使临时服务实例保持健康；持久实例注册行为不变。
- 将初学者示例的注册端口和监听端口统一为 `3000`，并删除硬编码连接与认证信息。
- 让每个 Flask app 独立维护运行状态、健康信息、注册标志、进程 ID、锁和退出回调。
- 重复调用 `init_app()` 时复用现有 client 和生命周期状态，并明确拒绝扩展槽冲突。
- 使用每应用 `RLock` 串行化并发注册/注销状态转换，并在进程 ID 改变后替换继承的锁。
- 确定性的 `NacosValidationError` 不再执行重试。
- `NACOS_CONFIG_ENABLED=False` 时跳过配置中心 SDK 调用。

### 稳定 API

以下 API 在 1.0 系列中视为稳定：

- `FlaskNacos`
- `init_app(app)`
- `get_client()`
- `register_instance()`
- `deregister_instance()`
- `list_instances()`
- `get_one_healthy_instance()`
- `get_config()`
- `get_status()`
- `normalize_instance()`

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。
- 这是面向 PyPI 发布的首个稳定版本。

## 0.9.0

### 新增

- 新增公共 API 快照检查。
- 新增向后兼容测试。
- 新增安装包 smoke test 脚本。
- 新增示例校验脚本。
- 新增 1.0.0 发布验收清单。
- 新增 Release Candidate 准备文档。
- CI 新增 API 稳定性和示例一致性检查。

### 变更

- 改进错误信息和日志一致性。
- 改进 TestPyPI 发布验证流程。
- 改进 API 冻结和 1.0.0 准备文档。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。
- `0.9.0` 是 `1.0.0` 之前的最终准备版本。

## 0.8.0

### 新增

- 新增 Python 3.8 语法兼容检查。
- 新增兼容性文档。
- 新增 Nacos SDK 响应提取兼容辅助函数。
- 新增多种 Nacos 实例响应结构测试。
- CI 新增兼容性校验。

### 变更

- 改进不同 Nacos SDK 响应结构下的服务发现兼容性。
- 改进 camelCase 和 snake_case 字段的实例标准化。
- 改进 README 兼容性说明。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。

## 0.7.0

### 新增

- 新增 Quickstart 文档。
- 新增完整配置参考。
- 新增 API 参考文档。
- 新增服务注册文档。
- 新增服务发现文档。
- 新增健康检查文档。
- 新增生产部署文档。
- 新增故障排查文档。
- 新增本地 Nacos Docker Compose 示例。
- 新增文档链接和不支持功能检查。

### 变更

- 改进 README 在 PyPI 上的展示结构。
- 改进常用 Flask-Nacos 场景示例。
- 改进 CI 文档一致性校验。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。

## 0.6.0

### 新增

- 新增 `scripts/check_version.py`，验证 `pyproject.toml`、`__version__` 和
  `CHANGELOG.md` 的版本一致性。
- 新增 `scripts/check_package.py`，检查构建产物，确认 wheel 包含 `py.typed` 和核心模块，
  且不包含测试或缓存文件。
- 新增 `scripts/check_sensitive_info.py`，扫描硬编码密钥、私有 IP、内部域名和遗留 `.env`。
- 新增一键发布前检查脚本 `scripts/release_check.sh`。
- 新增手动 TestPyPI/PyPI 发布工作流 `.github/workflows/release.yml`。
- 新增 `docs/release.md` 发布指南。

### 变更

- 扩展 CI，加入版本一致性、敏感信息和包内容检查。
- sdist 构建加入 `/scripts` 和 `/docs`。
- 更新中英文 README 的发布、开发和安全章节。

### 说明

- 没有库 API 变化，运行行为保持不变。
- `get_config()` 继续只返回原始配置内容。
- 不会因代码 push 自动发布 PyPI；发布上传必须显式选择目标索引。

## 0.5.0

### 新增

- 为公共 API 和核心内部方法新增类型提示。
- 新增用于 PEP 561 类型支持的 `py.typed`。
- 新增 Ruff 配置。
- 新增 mypy 配置。
- 新增 pytest 和覆盖率配置。
- 新增 GitHub Actions CI 工作流。
- 新增更多示例应用。
- 新增 PyPI 发布准备文档。

### 变更

- 改进 `pyproject.toml` 包元数据。
- 改进 README 的本地开发、测试和生产使用说明。
- 改进代码风格和导入组织。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。

## 0.4.0

### 新增

- 新增按进程的注册生命周期控制。
- 新增退出时注销控制。
- 新增服务实例标准化。
- 新增按 cluster 和 metadata 过滤服务发现。
- 新增 `first`、`random` 和 `weight` 服务发现策略。
- 新增进程和服务发现相关运行状态字段。

### 变更

- 改进多 worker 部署下的服务注册行为。
- 改进注销行为，避免注销其他进程的实例。
- 改进 Gunicorn/uWSGI 部署场景的 README 说明。
- 改进生命周期和服务发现策略的测试覆盖。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。

## 0.3.0

### 新增

- 新增 Nacos 操作重试支持。
- 新增重试配置项。
- 新增请求超时配置。
- 新增可选 Flask 健康检查路由。
- 新增 `get_status()` 用于查看扩展运行状态。

### 变更

- 改进生产部署文档。
- 改进重试、健康检查和自动注册相关日志。
- 改进重试和健康检查测试覆盖。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。
- 不支持将 Nacos 配置写入 Flask `app.config`。

## 0.2.0

### 新增

- 加强服务注册参数校验。
- 新增服务注册本地 IP 自动识别辅助函数。
- 新增服务注册幂等处理。
- 新增服务注销幂等处理。
- 改进服务发现行为。
- 明确注册、注销和服务发现的错误行为。
- 新增服务注册和发现测试。

### 变更

- 改进 Nacos client 初始化、服务注册、注销和发现日志。
- 改进 README 服务注册与发现说明。

### 说明

- `get_config()` 继续只返回原始配置内容。
- 本版本不支持 YAML、JSON 或 dict 配置解析。

## [0.1.0] - 2026-07-08

### 新增

- 首次发布 `flask-nacos`。
- `FlaskNacos` 扩展同时支持直接初始化 `FlaskNacos(app)` 和应用工厂
  `init_app(app)` 模式。
- 从 `app.config` 初始化 Nacos client，支持 namespace 和用户名/密码认证。
- 支持自动和手动服务注册 `register_instance`。
- 支持通过 `atexit` 自动注销和手动注销 `deregister_instance`。
- 支持服务发现：`list_instances` 和 `get_one_healthy_instance`。
- 支持配置中心读取：`get_config`。
- 支持可配置错误行为和自定义异常体系。
- 集成标准 `logging`，且日志绝不输出敏感信息。
- 提供完全模拟 Nacos SDK 的 pytest 测试套件。
- 使用 Hatchling 构建 PyPI 安装包。
