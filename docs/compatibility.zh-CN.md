# 兼容性

[English](compatibility.md) | 简体中文

本页说明 flask-nacos 支持的运行时版本及其兼容性保证。

`1.0.0` 是首个稳定版：公开 API 在 1.0 系列中保持稳定（见
[1.0.0 验收清单](1.0-checklist.zh-CN.md)）。

另请参阅：[快速开始](quickstart.zh-CN.md) - [配置项](configuration.zh-CN.md) -
[生产部署](production.zh-CN.md)。

## 支持的 Python 版本

flask-nacos 支持 **Python 3.8 - 3.12**。库代码的类型提示保持 Python 3.8 兼容：使用
`typing.Optional` / `typing.List` / `typing.Dict`，而不是 PEP 604 联合类型
（`str | None`）或 PEP 585 内置泛型（`list[str]`），并且不使用 `match`/`case`。
`scripts/check_compatibility.py` 静态检查会强制这一点，并在 CI 中运行。

## 支持的 Flask 版本

flask-nacos 支持 **Flask `>=1.0, <4.0`**（Flask 1.x、2.x、3.x）。

- Flask 1.x / 2.x / 3.x：扩展在普通模式 `FlaskNacos(app)` 与工厂模式
  `init_app(app)` 下均可正常初始化。
- 扩展只使用在 1.x-3.x 间稳定的 Flask API（`app.extensions`、
  `app.add_url_rule`、`app.url_map.iter_rules`、`app.view_functions`、
  `flask.jsonify`），并避免使用在 Flask 3.x 中被移除的 API。
- 可选的健康检查路由是幂等注册的，因此重复调用 `init_app(app)` 或路由已存在时不会
  报错。
- Flask 1.x 依赖较旧的 Werkzeug，与较新的 Python 版本不兼容，因此 CI 只在
  Python 3.8 上验证 Flask 1.x。

## 建议的 Nacos 版本

- Nacos 服务端：**2.x**。
- Nacos SDK：`nacos-sdk-python>=2.0.0,<3.0.0`（同步客户端）。

## Nacos SDK 返回结构兼容

不同版本的 SDK 返回的服务发现结果结构略有差异。`list_instances()` 使用内部的
`extract_instances()` 工具方法，兼容以下所有结构：

- 普通的实例 `list`
- `{"hosts": [...]}`
- `{"instances": [...]}`
- `{"data": {"hosts": [...]}}`
- `{"data": {"instances": [...]}}`
- `None` 或空列表（视为“没有实例”）

随后每个实例都会经过 `normalize_instance()`，它同时兼容 `dict` 与对象属性形式，以及
camelCase（`serviceName`、`clusterName`）与 snake_case（`service_name`、
`cluster_name`）字段名，并为缺失字段填充合理的默认值。

SDK 返回结构的轻微差异不会导致服务发现整体失败。当结构完全无法识别时，行为遵循
`NACOS_FAIL_FAST`：`NACOS_FAIL_FAST=False`（默认）时返回空列表并记录日志；
`NACOS_FAIL_FAST=True` 时抛出异常。

## Gunicorn / uWSGI 多 worker 注意事项

每个 worker 都是独立进程，各自注册自己的实例；注册状态按进程区分。完整部署建议见
[生产部署](production.zh-CN.md)。

## 不支持的能力

本版本有意不包含以下能力：

- `get_config()` 只返回 Nacos 配置的原始内容；不做 YAML、JSON、dict 解析，也不会写入
  Flask `app.config`。
- 本版本没有 `get_config_as_dict()` 辅助方法。
- 本版本没有 `load_config_to_flask()` 辅助方法。
- 不提供动态配置监听、热更新或后台配置线程。
- 不引入 PyYAML 依赖。
