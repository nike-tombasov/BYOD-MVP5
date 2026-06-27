import os
import subprocess
import sys


def test_listener_min_reconnect_interval_accepts_zero():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["BYOD_LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS"] = "0"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.config import LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS; print(LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS)",
        ],
        check=True,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.stdout.strip() == "0"
