# 更新日志

[English](CHANGELOG.md) | 简体中文

本文件记录 Flask-Nacos 项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
项目遵循[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。

## 1.0.2

### 修复

- 修复 Flask 加载 `flask-nacos` 时意外生成日志文件的问题。
- 修复底层 `nacos-sdk-python` 意外生成 `~/logs/nacos/nacos-client-python.log` 的问题。
- 修复库级别日志配置带来的日志副作用。
- 修复 Flask 应用初始化过程中的 SDK 级别日志副作用。
- 修复重复调用 `init_app(app)` 时重复添加日志 handler 的问题。
- 修复 SDK 原生日志可能通过应用、root、控制台或文件 handler 泄露 token、请求参数或配置
  正文的问题。
- 修复 fail-fast 初始化失败后残留部分应用或扩展状态的问题。
- 修复已初始化但 client 不可用时，非 fail-fast 操作仍抛出异常的问题。
- 修复注销时重新解析服务身份、可能没有使用实际注册身份的问题。

### 新增

- 新增可配置的日志控制能力。
- 新增 `NACOS_LOG_ENABLED`。
- 新增 `NACOS_LOG_CONSOLE_ENABLED` 与 `NACOS_LOG_FILE_ENABLED`。
- 新增 `NACOS_LOG_PATH` 与 `NACOS_LOG_FILENAME`。
- 新增 `NACOS_LOG_FORMAT`。
- 新增 `NACOS_LOG_PROPAGATE`。
- 新增 `NACOS_LOG_MAX_BYTES`。
- 新增 `NACOS_LOG_BACKUP_COUNT`。
- 新增日志、事务式初始化、注册身份与服务发现校验回归测试。

### 变更

- `NACOS_LOG_*` 现在只控制脱敏后的 Flask-Nacos 日志；SDK 原生 logger 始终静默。
- `NACOS_LOG_ENABLED` 默认值为 `False`；启用后控制台与轮转文件输出均默认开启，
  `NACOS_LOG_PATH` 默认使用 `./logs`，`NACOS_LOG_FILENAME` 默认使用 `flask-nacos.log`。
- 轮转日志默认每个文件 10 MiB，并保留五个备份。
- 控制台日志按等级着色：`DEBUG` 蓝色、`INFO` 绿色、`WARNING` 黄色、
  `ERROR` 红色、`CRITICAL` 加粗红色；文件日志保持纯文本，不包含 ANSI 转义符。
- 在发布前移除未发布的 `NACOS_LOG_TO_CONSOLE`、`NACOS_LOG_DIR`、
  `NACOS_LOG_FILE` 与 `NACOS_LOG_USE_FLASK_LOGGER` 配置。
- 日志关闭时绝不创建用户配置的日志目录；生成的文件只包含 Flask-Nacos 安全日志。
- `flask-nacos` 不再配置 root logger。
- `flask-nacos` 使用命名 logger：`flask_nacos`。
- 注册成功后缓存并在重试、注销时复用精确服务身份；持久实例忽略心跳配置。
- 服务发现会在 SDK 调用前校验 service/group/cluster/filter，并把 cluster 过滤同时传给 SDK
  2.x 和本地防御过滤。
- 状态示例只公开安全字段白名单，注册示例不再暴露无鉴权的 HTTP 生命周期端点。
- 生产文档补充多 worker 共享实例身份、SDK 2.x HTTPS 证书校验限制与安全日志默认行为。

### 说明

- `get_config()` 仍然只返回原始配置内容。
- 不支持 YAML、JSON、dict 配置解析。
- 不支持将 Nacos 配置加载进 Flask `app.config`。

## 1.0.1

### 修复

- 在 `init_app()` 中预检已启用的自动注册配置，使 fail-fast 校验错误在创建 client 或写入
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
- 通过现有 fail-fast 行为拒绝不完整或混用的认证凭据，以及非法重试和请求超时数字。
- 跳过端点异常的发现实例，正确解析字符串布尔值，并处理非法权重。
- 向 Nacos SDK 2.x 传递心跳间隔，使临时服务实例保持健康；持久实例注册行为不变。
- 将初学者示例的注册端口和监听端口统一为 `3000`，并删除硬编码连接与认证信息。
- 让每个 Flask app 独立维护运行状态、健康信息、注册标志、进程 ID、锁和退出回调。
- 重复调用 `init_app()` 时复用现有 client 和生命周期状态，并明确拒绝扩展槽冲突。
- 使用每应用 `RLock` 串行化并发注册/注销状态转换，并在进程 ID 改变后替换继承的锁。
- 确定性的 `NacosValidationError` 不再执行重试。
- `NACOS_CONFIG_ENABLED=False` 时跳过配置中心 SDK 调用。

### 弃用

- `NACOS_STATUS_ENABLED` 在 1.x 中保留为无操作兼容项，计划在 2.0 删除；
  `get_status()` 始终可用。

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
- 新增 `NACOS_AUTO_REGISTER_ON_INIT`，提供更精细的自动注册控制。

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
- 明确注册、注销和服务发现的 fail-fast 行为。
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
- 支持 `NACOS_FAIL_FAST` 行为控制和自定义异常体系。
- 集成标准 `logging`，且日志绝不输出敏感信息。
- 提供完全模拟 Nacos SDK 的 pytest 测试套件。
- 使用 Hatchling 构建 PyPI 安装包。
