# 更新日志

[English](changelog.md) | 简体中文

完整、权威的中文更新日志位于仓库根目录的
[`CHANGELOG.zh-CN.md`](../CHANGELOG.zh-CN.md)。本页仅为方便跳转。

- [查看完整中文更新日志](../CHANGELOG.zh-CN.md)

最新版本为 `1.1.1`。`register_instance(app=None)` 立即返回，并通过一个 app/PID Worker
与 Naming single-flight 驱动目标状态生命周期；Client 改为惰性创建，初始化自动注册仍默认
开启。已确认瞬时 Client 构造与 Naming故障可在现有有限预算耗尽后继续低频生命周期自恢复，
但不增加远端监控。
同时验证 Python 3.8-3.14 与当前 Flask `>=1.0` 的有效组合。完整细节请见根目录的更新日志。
