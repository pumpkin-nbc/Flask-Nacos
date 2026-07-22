# Changelog

English | [简体中文](changelog.zh-CN.md)

The full, authoritative changelog lives at [`CHANGELOG.md`](../CHANGELOG.md) in
the repository root. This page links to it for convenience.

- [View the full changelog](../CHANGELOG.md)

The latest release is `1.0.2`. It fixes unexpected log file creation (including
the underlying `nacos-sdk-python` default `~/logs/nacos/nacos-client-python.log`)
and adds unified `NACOS_LOG_*` logging controls that govern both `flask-nacos`
and `nacos-sdk-python` logging. See the root changelog for complete details.
