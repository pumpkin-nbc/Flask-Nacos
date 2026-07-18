# 服务发现

[English](service-discovery.md) | 简体中文

查询实例并选择单个健康实例。

另请参阅：[配置项](configuration.zh-CN.md) - [API 参考](api-reference.zh-CN.md)。

## 查询实例列表

```python
# 默认只返回健康实例
instances = nacos.list_instances("user-service")
```

## 只查健康实例 vs 查全部

```python
# 返回全部实例，包括不健康的
instances = nacos.list_instances("user-service", healthy_only=False)
```

## 按 cluster 过滤

```python
instances = nacos.list_instances("user-service", cluster="CANARY")
```

省略时 `cluster` 回退到 `NACOS_DISCOVERY_CLUSTER`。

## 按 metadata 过滤

```python
instances = nacos.list_instances("user-service", metadata={"version": "v1"})
```

只返回 metadata 包含全部给定键值对的实例。省略或传入 `None` 时 `metadata` 回退到
`NACOS_DISCOVERY_METADATA`；显式传入 `{}` 可禁用配置中的 metadata 过滤。

## 实例标准化

当 `NACOS_INSTANCE_NORMALIZE=True`（默认）时，`list_instances()` 返回标准 dict
列表：

```python
{
    "ip": "127.0.0.1",
    "port": 5000,
    "service_name": "user-service",
    "cluster_name": "DEFAULT",
    "weight": 1.0,
    "healthy": True,
    "enabled": True,
    "ephemeral": True,
    "metadata": {},
}
```

你也可以标准化单个原始实例：

```python
normalized = nacos.normalize_instance(raw_sdk_instance)
```

## 获取一个健康实例

```python
instance = nacos.get_one_healthy_instance("user-service")
```

省略时 `strategy` 回退到 `NACOS_DISCOVERY_STRATEGY`（默认 `first`）。

## 策略：first

```python
nacos.get_one_healthy_instance("user-service", strategy="first")
```

返回第一个健康实例。

## 策略：random

```python
nacos.get_one_healthy_instance("user-service", strategy="random")
```

从健康实例中均匀随机返回一个。

## 策略：weight

```python
instance = nacos.get_one_healthy_instance(
    "user-service",
    strategy="weight",
)
```

按实例 `weight` 加权随机选择（缺失权重默认 `1.0`；权重 `<= 0` 的实例被忽略；若所有
权重都 `<= 0`，退化为 `first` 策略）。

没有健康实例时返回 `None`。不支持的策略遵循 `NACOS_FAIL_FAST`。

> 本版本仅提供简单的客户端选择策略，不提供完整的服务治理能力。
