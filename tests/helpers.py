"""Small synchronization helpers shared by lifecycle tests."""

import time


def wait_until(predicate, timeout=2.0):
    """Wait until ``predicate`` is true or fail with a useful assertion."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("condition was not reached before timeout")


def wait_registered(nacos, app, expected=True, timeout=2.0):
    """Wait for registration work to settle at the expected local state."""
    wait_until(
        lambda: (
            nacos.get_status(app)["operation_running"] is False
            and nacos.get_status(app)["registered"] is expected
        ),
        timeout=timeout,
    )
