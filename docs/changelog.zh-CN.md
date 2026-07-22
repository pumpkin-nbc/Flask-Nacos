# 更新日志

[English](changelog.md) | 简体中文

完整、权威的中文更新日志位于仓库根目录的
[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)。本页仅为方便跳转。

- [查看完整中文更新日志](../CHANGELOG.zh-CN.md)

最新版本为 `1.0.2`。修复了意外生成日志文件的问题（包括底层 `nacos-sdk-python` 的默认
`~/logs/nacos/nacos-client-python.log`），并新增统一的 `NACOS_LOG_*` 日志控制，可同时管理
`flask-nacos` 与 `nacos-sdk-python` 的日志。完整细节请见根目录的更新日志。
