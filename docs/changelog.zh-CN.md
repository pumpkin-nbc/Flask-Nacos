# 更新日志

[English](changelog.md) | 简体中文

完整、权威的中文更新日志位于仓库根目录的
[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)。本页仅为方便跳转。

- [查看完整中文更新日志](../CHANGELOG.zh-CN.md)

最新版本为 `1.0.2`。它会阻止 SDK 默认日志文件和 `~/logs/nacos` 目录，保持 SDK 原生日志
静默，并让 `NACOS_LOG_*` 只管理脱敏后的 Flask-Nacos 日志。同时加固了事务式初始化、
生命周期身份、发现参数校验与安全示例。完整细节请见根目录的更新日志。
