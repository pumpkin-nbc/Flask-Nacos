# Changelog

English | [简体中文](changelog.zh-CN.md)

The full, authoritative changelog lives at [`CHANGELOG.md`](../CHANGELOG.md) in
the repository root. This page links to it for convenience.

- [View the full changelog](../CHANGELOG.md)

The latest release is `1.1.1`. `register_instance(app=None)` returns
immediately and drives a target-state lifecycle through one per-app/PID Worker
and Naming single-flight. Client creation is lazy, while initialization-time
registration remains enabled by default. Verified transient Client-construction
and Naming failures can continue low-frequency lifecycle recovery after the
existing finite budget, without adding remote monitoring. It validates Python
3.8-3.14 and current Flask `>=1.0` combinations.
