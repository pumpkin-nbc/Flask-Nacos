#!/usr/bin/env python
"""Check the installed nacos-sdk-python 2.x surface used by Flask-Nacos."""

import argparse
import inspect
import re
import sys
from importlib import metadata
from typing import Dict, Iterable, Optional, Set, Tuple

SDK_DISTRIBUTION = "nacos-sdk-python"
MINIMUM_VERSION = (2, 0, 0)
MAXIMUM_MAJOR = 3

REQUIRED_PARAMETERS: Dict[str, Set[str]] = {
    "NacosClient": {
        "server_addresses",
        "namespace",
        "ak",
        "sk",
        "username",
        "password",
        "logDir",
    },
    "add_naming_instance": {
        "service_name",
        "ip",
        "port",
        "cluster_name",
        "weight",
        "metadata",
        "enable",
        "healthy",
        "ephemeral",
        "group_name",
        "heartbeat_interval",
    },
    "remove_naming_instance": {
        "service_name",
        "ip",
        "port",
        "cluster_name",
        "ephemeral",
        "group_name",
    },
    "list_naming_instance": {
        "service_name",
        "clusters",
        "namespace_id",
        "group_name",
        "healthy_only",
    },
    "get_config": {"data_id", "group", "timeout"},
}


def parse_release_version(value: str) -> Tuple[int, int, int]:
    """Return the numeric release triplet from a supported SDK version."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[.+-].*)?", value)
    if match is None:
        raise ValueError(f"unsupported SDK version format: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def validate_version(version: str, expected: Optional[str] = None) -> None:
    """Require the installed SDK to be in the supported 2.x range."""
    parsed = parse_release_version(version)
    if parsed < MINIMUM_VERSION or parsed[0] >= MAXIMUM_MAJOR:
        raise ValueError(
            f"{SDK_DISTRIBUTION} {version} is outside the supported >=2.0.0,<3.0.0 range"
        )
    if expected is not None and version != expected:
        raise ValueError(
            f"expected {SDK_DISTRIBUTION} {expected}, found {version}"
        )


def _parameter_names(callable_object) -> Set[str]:
    return set(inspect.signature(callable_object).parameters)


def validate_client_surface(client_class) -> None:
    """Require every constructor/method parameter used by Flask-Nacos."""
    callables = {"NacosClient": client_class}
    callables.update(
        {
            method_name: getattr(client_class, method_name, None)
            for method_name in REQUIRED_PARAMETERS
            if method_name != "NacosClient"
        }
    )
    problems = []
    for name, required in REQUIRED_PARAMETERS.items():
        callable_object = callables[name]
        if callable_object is None or not callable(callable_object):
            problems.append(f"missing callable: {name}")
            continue
        missing = sorted(required - _parameter_names(callable_object))
        if missing:
            problems.append(f"{name} missing parameters: {', '.join(missing)}")
    if problems:
        raise ValueError("; ".join(problems))


def check(expected_version: Optional[str] = None) -> str:
    """Validate the installed distribution and return its version."""
    import nacos

    version = metadata.version(SDK_DISTRIBUTION)
    validate_version(version, expected_version)
    validate_client_surface(nacos.NacosClient)
    return version


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version")
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        version = check(args.expected_version)
    except (ImportError, metadata.PackageNotFoundError, ValueError) as exc:
        print(f"[check_sdk_compatibility] FAILED - {exc}", file=sys.stderr)
        return 1
    print(f"[check_sdk_compatibility] OK - {SDK_DISTRIBUTION} {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
