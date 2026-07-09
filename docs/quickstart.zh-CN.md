# 快速开始

[English](quickstart.md) | 简体中文

本指南带你从安装到运行一个接入 Nacos 的 Flask 应用。

另请参阅：[配置项](configuration.zh-CN.md) - [API 参考](api-reference.zh-CN.md) -
[服务注册](service-registration.zh-CN.md) -
[服务发现](service-discovery.zh-CN.md) - [健康检查](health-check.zh-CN.md) -
[生产部署](production.zh-CN.md) - [错误排查](troubleshooting.zh-CN.md)。

## 安装

```bash
pip install flask-nacos
```

本地开发（测试、代码检查、类型检查、构建）：

```bash
pip install -e ".[dev]"
```

## 本地测试用 Nacos

你可以用仓库自带的 Compose 文件启动一个本地 Nacos（仅用于本地测试，切勿用于生产）：

```bash
docker compose -f examples/docker-compose-nacos.yml up -d
```

它监听 `127.0.0.1:8848`，默认演示账号为 `nacos/nacos`。

## 最小示例

```python
from flask import Flask
from flask_nacos import FlaskNacos

app = Flask(__name__)
app.config.update(
    NACOS_SERVER_ADDR="127.0.0.1:8848",
    NACOS_USERNAME="nacos",
    NACOS_PASSWORD="nacos",
    NACOS_SERVICE_NAME="my-service",
    NACOS_SERVICE_IP="127.0.0.1",
    NACOS_SERVICE_PORT=5000,
)

nacos = FlaskNacos(app)
```

初始化完成后，扩展实例可通过 `app.extensions["nacos"]` 获取。

## 工厂模式

```python
from flask import Flask
from flask_nacos import FlaskNacos

nacos = FlaskNacos()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    nacos.init_app(app)
    return app
```

## 服务注册

当 `NACOS_REGISTER_ENABLED` 与 `NACOS_AUTO_REGISTER` 都为 `True` 时，会在
`init_app(app)` 期间自动注册。你也可以手动注册：

```python
nacos.register_instance()
```

详见[服务注册](service-registration.zh-CN.md)。

## 服务发现

```python
instances = nacos.list_instances("user-service")
instance = nacos.get_one_healthy_instance("user-service", strategy="random")
```

过滤与策略详见[服务发现](service-discovery.zh-CN.md)。

## 健康检查

```python
app.config["NACOS_HEALTH_CHECK_ENABLED"] = True
app.config["NACOS_HEALTH_CHECK_PATH"] = "/health/nacos"
```

返回格式详见[健康检查](health-check.zh-CN.md)。

## 读取配置

```python
content = nacos.get_config("application.yaml")
```

`get_config()` 直接返回 Nacos 配置的原始内容字符串，不做任何 YAML、JSON、dict
解析，也不会写入 Flask `app.config`。
