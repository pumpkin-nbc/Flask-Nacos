"""Test-only helpers for opt-in real Nacos integration gates."""

import os
import selectors
import socket
import tempfile
import threading
import time
from typing import Any, Dict, Tuple
from urllib.parse import urlsplit

import pytest


def require_nacos_environment(run_flag: str, *, authenticated: bool) -> Dict[str, str]:
    """Return the existing integration environment or skip without side effects."""
    if os.environ.get(run_flag) != "1":
        pytest.skip(f"set {run_flag}=1 to run this test")

    names = ["FLASK_NACOS_TEST_SERVER_ADDR"]
    if authenticated:
        names.extend(("FLASK_NACOS_TEST_USERNAME", "FLASK_NACOS_TEST_PASSWORD"))
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.skip(f"missing Nacos integration-test environment: {', '.join(missing)}")
    return {name: os.environ[name] for name in names}


def integration_nacos_config(environment: Dict[str, str]) -> Dict[str, Any]:
    """Build common extension config without introducing environment aliases."""
    return {
        "NACOS_SERVER_ADDR": environment["FLASK_NACOS_TEST_SERVER_ADDR"],
        "NACOS_NAMESPACE_ID": os.environ.get("FLASK_NACOS_TEST_NAMESPACE_ID", ""),
        "NACOS_USERNAME": os.environ.get("FLASK_NACOS_TEST_USERNAME"),
        "NACOS_PASSWORD": os.environ.get("FLASK_NACOS_TEST_PASSWORD"),
    }


def create_external_sdk_client(environment: Dict[str, str]) -> Any:
    """Create a second real SDK client for out-of-band test actions."""
    import nacos

    config = integration_nacos_config(environment)
    return nacos.NacosClient(
        config["NACOS_SERVER_ADDR"],
        namespace=config["NACOS_NAMESPACE_ID"],
        username=config["NACOS_USERNAME"],
        password=config["NACOS_PASSWORD"],
        logDir=tempfile.gettempdir(),
    )


def wait_for(predicate, *, timeout: float = 15.0, interval: float = 0.2) -> None:
    """Poll a real external system with a strict wall-clock deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("real Nacos condition was not reached before timeout")


def parse_single_server_address(server_address: str) -> Tuple[str, int]:
    """Parse the one upstream endpoint required by the TCP gate test."""
    if "," in server_address:
        raise ValueError("the TCP gate test requires one Nacos server")
    parsed = urlsplit(
        server_address if "://" in server_address else f"//{server_address}"
    )
    if not parsed.hostname or parsed.port is None:
        raise ValueError("invalid Nacos server address")
    return parsed.hostname, parsed.port


class TcpGate:
    """Small standard-library TCP proxy that can be opened after startup."""

    def __init__(self, upstream: Tuple[str, int]) -> None:
        self._upstream = upstream
        self._forwarding = threading.Event()
        self._stopping = threading.Event()
        self._count_lock = threading.Lock()
        self._connection_count = 0
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen()
        self._listener.settimeout(0.2)
        self._thread = threading.Thread(target=self._accept, daemon=True)

    @property
    def address(self) -> str:
        return f"127.0.0.1:{self._listener.getsockname()[1]}"

    @property
    def connection_count(self) -> int:
        with self._count_lock:
            return self._connection_count

    def __enter__(self) -> "TcpGate":
        self._thread.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        self._stopping.set()
        self._listener.close()
        self._thread.join(2.0)

    def open(self) -> None:
        self._forwarding.set()

    def _accept(self) -> None:
        while not self._stopping.is_set():
            try:
                downstream, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._count_lock:
                self._connection_count += 1
            threading.Thread(target=self._handle, args=(downstream,), daemon=True).start()

    def _handle(self, downstream: socket.socket) -> None:
        with downstream:
            if not self._forwarding.is_set():
                return
            try:
                upstream = socket.create_connection(self._upstream, timeout=3.0)
            except OSError:
                return
            with upstream:
                self._proxy(downstream, upstream)

    def _proxy(self, downstream: socket.socket, upstream: socket.socket) -> None:
        selector = selectors.DefaultSelector()
        try:
            downstream.setblocking(False)
            upstream.setblocking(False)
            selector.register(downstream, selectors.EVENT_READ, upstream)
            selector.register(upstream, selectors.EVENT_READ, downstream)
            while not self._stopping.is_set():
                for key, _ in selector.select(0.2):
                    source = key.fileobj
                    destination = key.data
                    try:
                        chunk = source.recv(65536)
                        if not chunk:
                            return
                        destination.sendall(chunk)
                    except OSError:
                        return
        finally:
            selector.close()
