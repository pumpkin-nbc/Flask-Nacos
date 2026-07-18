# 更新日志

[English](changelog.md) | 简体中文

完整、权威的中文更新日志位于仓库根目录的
[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)。本页仅为方便跳转。

- [查看完整中文更新日志](../CHANGELOG.zh-CN.md)

最新版本为 `1.0.1`。启用自动注册时，会在 `init_app()` 中预检注册配置，使 fail-fast
配置错误在创建 client 或写入部分扩展状态之前抛出。该修复及稳定 1.0 API 的完整细节请见
根目录的更新日志。
