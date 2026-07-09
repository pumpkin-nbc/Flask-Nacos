# Service Discovery

English | [简体中文](service-discovery.zh-CN.md)

Query instances and select a single healthy instance.

See also: [Configuration](configuration.md) - [API Reference](api-reference.md).

## List instances

```python
# Healthy instances only (default)
instances = nacos.list_instances("user-service")
```

## Healthy only vs all

```python
# All instances, including unhealthy ones
instances = nacos.list_instances("user-service", healthy_only=False)
```

## Filter by cluster

```python
instances = nacos.list_instances("user-service", cluster="CANARY")
```

`cluster` falls back to `NACOS_DISCOVERY_CLUSTER` when omitted.

## Filter by metadata

```python
instances = nacos.list_instances("user-service", metadata={"version": "v1"})
```

Only instances whose metadata contains all the given key/value pairs are
returned. `metadata` falls back to `NACOS_DISCOVERY_METADATA` when omitted.

## Instance normalization

When `NACOS_INSTANCE_NORMALIZE=True` (default), `list_instances()` returns a list
of standard dicts:

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

You can also normalize a single raw instance:

```python
normalized = nacos.normalize_instance(raw_sdk_instance)
```

## Get one healthy instance

```python
instance = nacos.get_one_healthy_instance("user-service")
```

`strategy` falls back to `NACOS_DISCOVERY_STRATEGY` (default `first`).

## Strategy: first

```python
nacos.get_one_healthy_instance("user-service", strategy="first")
```

Returns the first healthy instance.

## Strategy: random

```python
nacos.get_one_healthy_instance("user-service", strategy="random")
```

Returns a uniformly random healthy instance.

## Strategy: weight

```python
instance = nacos.get_one_healthy_instance(
    "user-service",
    strategy="weight",
)
```

Weighted-random selection using each instance's `weight` (missing weight
defaults to `1.0`; instances with weight `<= 0` are ignored; if all weights are
`<= 0` the strategy degrades to `first`).

When there are no healthy instances, `None` is returned. An unsupported strategy
follows `NACOS_FAIL_FAST`.

> This version provides simple client-side selection strategies only; it does
> not provide full service-governance capabilities.
