# 发布指南

[English](release.md) | 简体中文

本文档说明如何将 **flask-nacos** 发布到 TestPyPI 与 PyPI。整个流程刻意保持手动，
并通过自动检查进行把关，以确保永远不会发布损坏或含敏感信息的构建产物。

## 1. 发布前准备

开始发布前：

- 确认 `main`/`master` 分支的 CI 全部通过。
- 确认工作区干净（`git status`）。
- 审查自上个 tag 以来的变更，确认公共 API 没有变化，或所有变化都是有意为之且已记录。

## 2. 版本号更新规则

**每次发布都必须更新版本号。** PyPI 上的版本是不可变的 —— 同一个版本号永远无法重新上传。
请保持以下三处一致：

- `pyproject.toml` → `[project].version`
- `flask_nacos/__init__.py` → `__version__`
- `CHANGELOG.md` → 最新的 `## X.Y.Z` 标题

`scripts/check_version.py` 脚本会校验这一致性，并在 CI 中运行。

## 3. CHANGELOG 规则

- 在 `CHANGELOG.md` 顶部为本次发布新增一个 `## X.Y.Z` 章节。
- 视情况在 **Added**、**Changed**、**Fixed**、**Notes** 下归类各项条目。
- 最新的标题必须与 `pyproject.toml` 及 `__version__` 中的版本号一致。

## 4. 本地预发布检查

在仓库根目录运行一键脚本：

```bash
bash scripts/release_check.sh
```

它会依次执行：`ruff`、`mypy`、`pytest`、`check_version.py`、
`check_sensitive_info.py`、干净重建（`python -m build`）、`twine check dist/*`
以及 `check_package.py`。整个过程不会上传任何内容。

你也可以显式逐条执行：

```bash
python -m ruff check .
python -m mypy flask_nacos
python -m pytest
python scripts/check_version.py
python scripts/check_sensitive_info.py
rm -rf dist build ./*.egg-info
python -m build
python -m twine check dist/*
python scripts/check_package.py
```

## 5. 发布到 TestPyPI

TestPyPI 是用于验证上传与安装流程的沙箱环境：

```bash
python -m twine upload --repository testpypi dist/*
```

然后在一个全新的虚拟环境中，验证从 TestPyPI 安装：

```bash
pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ flask-nacos
python -c "import flask_nacos; print(flask_nacos.__version__)"
```

## 6. 发布到 PyPI

TestPyPI 验证无误后：

```bash
python -m twine upload dist/*
```

## 7. 通过 GitHub Actions 发布

`Release` 工作流（`.github/workflows/release.yml`）可以替你完成上传。在 **Actions**
标签页手动触发（`workflow_dispatch`），并选择目标索引：

- `testpypi`（默认）—— 安全的沙箱环境。
- `pypi` —— 正式发布；必须显式选择。

该工作流会在上传前重新运行全部预发布检查。

## 8. GitHub Secrets 配置

将 API token 配置为仓库 Secrets（Settings → Secrets and variables → Actions）：

- `TEST_PYPI_API_TOKEN` —— TestPyPI 的 API token。
- `PYPI_API_TOKEN` —— PyPI 的 API token。

token 通过 `TWINE_USERNAME=__token__` 与 `TWINE_PASSWORD=<secret>` 传给 `twine`。
切勿将 token 硬编码到文件或日志中。

## 9. 失败与回滚说明

- PyPI / TestPyPI 上的版本是**不可变的**，无法覆盖已发布的版本。
- 如果发布了有问题的产物，可在 PyPI 上对该版本执行 **yank**（这会让它对新的安装不可见，
  同时不破坏已锁定该版本的依赖），随后**提升版本号**并发布修复版本。
- 不存在“删除后用同一版本号重新上传”的路径 —— 始终以新的版本号向前推进。

## 10. 发布后验证

发布到 PyPI 后，在干净的环境中验证：

```bash
pip install flask-nacos
python -c "import flask_nacos; print(flask_nacos.__version__)"
```

确认输出的版本号与本次发布一致，如流程需要，再为该提交打 tag。
