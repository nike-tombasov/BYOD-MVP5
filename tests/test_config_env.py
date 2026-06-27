import os
import subprocess
import sys


def read_config_values(**overrides):
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env.update(overrides)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.config import LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS, derive_max_new_connections_per_sec; print(LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS); print(derive_max_new_connections_per_sec(1500))",
        ],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip().splitlines()


def test_listener_min_reconnect_interval_accepts_zero():
    values = read_config_values(BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS="0")
    assert values[0] == "0"


def test_max_new_connections_override_empty_keeps_derived_behavior():
    values = read_config_values(BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE="")
    assert values[1] == "100"


def test_max_new_connections_override_accepts_integer():
    values = read_config_values(BYOD_MAX_NEW_CONNECTIONS_PER_SEC_OVERRIDE="500")
    assert values[1] == "500"
