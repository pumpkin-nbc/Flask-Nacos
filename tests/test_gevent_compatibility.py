"""Opt-in smoke for a gevent-monkey-patched Flask 1.1 runtime."""

import subprocess
import sys
import textwrap

import pytest


def test_gevent_monkey_patched_registration_lifecycle():
    pytest.importorskip("gevent")
    script = textwrap.dedent(
        """
        from gevent import monkey
        monkey.patch_all()

        import time

        from flask import Flask

        import flask_nacos.extension as extension_module
        from flask_nacos import FlaskNacos


        class FakeClient:
            def __init__(self):
                self.register_calls = 0
                self.deregister_calls = 0

            def add_naming_instance(self, *_args, **_kwargs):
                self.register_calls += 1
                return True

            def remove_naming_instance(self, *_args, **_kwargs):
                self.deregister_calls += 1
                return True


        fake_client = FakeClient()
        extension_module.create_client = lambda _config: fake_client

        app = Flask(__name__)
        app.config.update(
            NACOS_SERVER_ADDR="127.0.0.1:8848",
            NACOS_SERVICE_NAME="gevent-smoke",
            NACOS_SERVICE_IP="127.0.0.1",
            NACOS_SERVICE_PORT=8080,
            NACOS_AUTO_REGISTER=True,
            NACOS_DEREGISTER_ON_EXIT=False,
            NACOS_RETRY_INTERVAL=0,
        )
        nacos = FlaskNacos(app)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            status = nacos.get_status(app)
            if status["registered"] and not status["operation_running"]:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("gevent-patched registration did not converge")

        status = nacos.get_status(app)
        assert status["target_registered"] is True
        assert status["registered"] is True
        assert status["operation_running"] is False
        assert status["last_error"] is None
        assert nacos.deregister_instance(app) is True

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            status = nacos.get_status(app)
            if not status["registered"] and not status["operation_running"]:
                break
            time.sleep(0.01)
        else:
            raise AssertionError("gevent-patched deregistration did not converge")

        assert fake_client.register_calls == 1
        assert fake_client.deregister_calls == 1
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
