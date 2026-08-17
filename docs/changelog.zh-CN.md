# 更新日志

[English](changelog.md) | 简体中文

完整、权威的中文更新日志位于仓库根目录的
[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)。本页仅为方便跳转。

- [查看完整中文更新日志](../CHANGELOG.zh-CN.md)

最新版本为 `1.1.0`。无参数 `register_instance()` 命令改为非阻塞，初始化注册保持默认开启
但改为后台执行，并增加 per-app、per-process single-flight 生命周期状态。同时验证
Python 3.8-3.14 与当前 Flask `>=1.0` 的有效组合。完整细节请见根目录的更新日志。
