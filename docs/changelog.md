# Changelog

English | [简体中文](changelog.zh-CN.md)

The full, authoritative changelog lives at [`CHANGELOG.md`](../CHANGELOG.md) in
the repository root. This page links to it for convenience.

- [View the full changelog](../CHANGELOG.md)

The latest release is `1.1.0`. It makes the no-argument
`register_instance()` command non-blocking, keeps init-time registration enabled
by default as background work, and adds per-app/per-process single-flight lifecycle status.
It also validates Python 3.8-3.14 and current Flask `>=1.0` combinations.
