# 发布指南

[English](release.md) | 简体中文

本文档使用 GitHub Actions 和 PyPI Trusted Publishing 发布 **flask-nacos**。
本地命令只负责准备和检查产物，不会上传任何文件。

## 1. 发布约束

- 只从默认分支 `master` 发布，并确保其完整 CI 矩阵通过。
- `[project].version`、`flask_nacos.__version__`、最新 Changelog 标题及
  `vX.Y.Z` tag 必须完全一致。
- PyPI 版本不可覆盖。错误版本应执行 yank、提升版本号并重新发布。
- 两个真实 Nacos 集成测试任意一个失败时停止发布。

## 2. GitHub 与包索引的一次性配置

创建两个 GitHub Environment：

- `testpypi`：供手动预演任务使用。
- `pypi`：配置必要审核人，并只允许匹配 `v*` 的受保护 tag 部署。

分别在 PyPI 与 TestPyPI 创建 Pending Trusted Publisher：

| 字段 | 值 |
| --- | --- |
| PyPI 项目 | `flask-nacos` |
| GitHub Owner | `pumpkin-nbc` |
| Repository | `Flask-Nacos` |
| Workflow | `release.yml` |
| Environment | `pypi` 或 `testpypi` |

Pending Publisher 不会预留包名，完成配置后应尽快发布。工作流使用短期 OIDC
凭据，不需要 `PYPI_API_TOKEN` 或 `TEST_PYPI_API_TOKEN`。OIDC 验证成功后，删除
旧 GitHub Secrets，并在两个索引中撤销相应长期 token。

同时启用 GitHub Private Vulnerability Reporting，使 [`SECURITY.md`](../SECURITY.md)
中说明的私密报告渠道可用。

## 3. 在非生产 Nacos 上验证

使用具备配置读写权限的专用测试账号。所有值通过环境变量注入，禁止提交凭据。

```powershell
$env:FLASK_NACOS_RUN_AUTH_INTEGRATION = "1"
$env:FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION = "1"
$env:FLASK_NACOS_TEST_SERVER_ADDR = "nacos-test.example:8848"
$env:FLASK_NACOS_TEST_USERNAME = "<test-user>"
$env:FLASK_NACOS_TEST_PASSWORD = "<test-password>"
$env:FLASK_NACOS_TEST_NAMESPACE_ID = "<optional-namespace-id>"
.venv\Scripts\python -m pytest tests/test_authenticated_integration.py tests/test_heartbeat_integration.py -v
```

```bash
export FLASK_NACOS_RUN_AUTH_INTEGRATION="1"
export FLASK_NACOS_RUN_HEARTBEAT_INTEGRATION="1"
export FLASK_NACOS_TEST_SERVER_ADDR="nacos-test.example:8848"
export FLASK_NACOS_TEST_USERNAME="<test-user>"
read -s FLASK_NACOS_TEST_PASSWORD && export FLASK_NACOS_TEST_PASSWORD
export FLASK_NACOS_TEST_NAMESPACE_ID="<optional-namespace-id>"
.venv/bin/python -m pytest tests/test_authenticated_integration.py tests/test_heartbeat_integration.py -v
```

认证测试会发布、读取并删除唯一临时配置；心跳测试会注册唯一临时服务，默认等待
35 秒，确认实例仍保持健康，并在 `finally` 中注销。

## 4. 本地干净验收

在仓库根目录运行：

```bash
bash scripts/release_check.sh
```

脚本会运行 Ruff、mypy、pytest、版本、敏感信息、文档、兼容性、API 和示例检查；
清理旧产物；构建 wheel 与 sdist；执行 `twine check --strict`；校验元数据、包内容和
源码新鲜度；最后在两个独立临时环境中分别安装两种产物。

确认 `git status` 中没有非预期的发布输入。Hatch 显式包含列表之外的本地笔记不会
进入源码包，但仍应人工确认。

## 5. 合并发布提交

创建从 `develop` 到 `master` 的 Pull Request，不要直接从 `develop` 发布。审核并合并
后，确认最终 `master` 提交的全部 Python/Flask 矩阵及质量任务通过。

## 6. TestPyPI 预演

在 `master` 的 Actions 页面手动运行 **Release** 工作流。手动触发只会发布到
TestPyPI；工作流会拒绝其他分支，从干净 checkout 重建，检查 `1.0.1` 尚不存在，并
通过 `testpypi` Environment 和 OIDC 上传。

在全新的 Python 3.8、3.13 环境中验证：

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos==1.0.1
python -c "from flask_nacos import FlaskNacos; import flask_nacos; print(flask_nacos.__version__)"
```

同时检查 TestPyPI 项目页中的 README 链接、项目 URL、Apache-2.0 表达式、
`LICENSE`、`NOTICE` 以及中英文入口。

## 7. 正式 PyPI 发布

在已验证的 `master` 提交上创建并推送受保护 tag：

```bash
git switch master
git pull --ff-only origin master
git tag -a v1.0.1 -m "Flask-Nacos v1.0.1"
git push origin v1.0.1
```

tag 工作流会确认提交属于 `master`，并且 tag 与所有版本声明完全一致。重新构建和
验收后，工作流停在受保护的 `pypi` Environment。审批前再次核对提交与产物。发布
Action 默认生成 PEP 740 provenance。

## 8. 发布后验证

在干净环境中从 PyPI 安装：

```bash
python -m pip install flask-nacos==1.0.1
python -c "from flask_nacos import FlaskNacos; import flask_nacos; print(flask_nacos.__version__)"
```

确认 PyPI 文件、哈希、provenance、许可证表达式、许可文件、项目 URL、README 链接和
版本号。随后从 `v1.0.1` 创建名为 `Flask-Nacos v1.0.1` 的 GitHub Release，说明使用
对应 Changelog 章节。

## 9. 失败处理

- 上传前失败：修复原因，并从干净 checkout 重建。
- TestPyPI 已存在同版本：提升测试版本；TestPyPI 文件同样不可覆盖。
- PyPI 已发布错误版本：执行 yank、修复、提升版本号后重新发布。
- PyPI 成功上传后绝不能移动对应 tag。
