# Changelog

English | [简体中文](changelog.zh-CN.md)

The full, authoritative changelog lives at [`CHANGELOG.md`](../CHANGELOG.md) in
the repository root. This page links to it for convenience.

- [View the full changelog](../CHANGELOG.md)

The latest release is `1.0.2`. It prevents the SDK default log file and
`~/logs/nacos` directory, keeps native SDK logging silent, and makes
`NACOS_LOG_*` govern sanitized Flask-Nacos records only. It also hardens
transactional initialization, lifecycle identity, discovery validation, and
safe examples. See the root changelog for complete details.
