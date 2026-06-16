#!/usr/bin/env python3
"""BYOD Stage XI VPS metrics analyzer helper.

Writes CSV, JSONL, and human-readable log samples to /opt/byod/metrics.
Uses only Python stdlib and common Ubuntu 22.04 files/commands.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRICS_DIR = Path("/opt/byod/metrics")
BACKEND_SNAPSHOT_URL = "http://127.0.0.1:8000/admin/metrics_snapshot"
FIELDS = [
    "timestamp_local",
    "timestamp_utc",
    "cpu_percent",
    "ram_used_gb",
    "ram_total_gb",
    "disk_used_gb",
    "disk_total_gb",
    "net_iface",
    "rx_mbps",
    "tx_mbps",
    "livekit_publishers_count",
    "livekit_listeners_count",
    "livekit_rooms_count",
    "backend_publishers_count",
    "backend_listeners_count",
    "backend_active_play_count",
    "byod_backend_status",
    "byod_livekit_status",
    "nginx_status",
]


def local_ts() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_proc_stat() -> tuple[int, int]:
    first = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
    values = [int(v) for v in first]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


def cpu_percent(prev: tuple[int, int] | None, current: tuple[int, int]) -> float:
    if prev is None:
        return 0.0
    total_delta = current[0] - prev[0]
    idle_delta = current[1] - prev[1]
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0)), 2)


def ram_gb() -> tuple[float, float]:
    meminfo: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        meminfo[key] = int(value.strip().split()[0])
    total = meminfo.get("MemTotal", 0) / 1024 / 1024
    available = meminfo.get("MemAvailable", 0) / 1024 / 1024
    return round(total - available, 3), round(total, 3)


def disk_gb() -> tuple[float, float]:
    target = Path("/opt/byod") if Path("/opt/byod").exists() else Path("/")
    usage = shutil.disk_usage(target)
    return round(usage.used / 1024**3, 3), round(usage.total / 1024**3, 3)


def default_iface() -> str:
    try:
        output = subprocess.check_output(["ip", "route", "show", "default"], text=True, timeout=1.5)
        parts = output.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    except Exception:
        pass
    for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
        iface = line.split(":", 1)[0].strip()
        if iface and iface != "lo":
            return iface
    return "lo"


def net_bytes(iface: str) -> tuple[int, int]:
    for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
        name, data = line.split(":", 1)
        if name.strip() == iface:
            fields = data.split()
            return int(fields[0]), int(fields[8])
    return 0, 0


def service_status(name: str) -> str:
    try:
        result = subprocess.run(["systemctl", "is-active", name], text=True, capture_output=True, timeout=2)
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception as exc:
        return f"unknown:{type(exc).__name__}"


def http_json(url: str, timeout: float = 2.0) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def read_backend_env() -> dict[str, str]:
    env_path = Path("/opt/byod/config/backend.env")
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def livekit_api_url(livekit_url: str) -> str:
    parsed = urlparse(livekit_url)
    scheme = "https" if parsed.scheme == "wss" else "http"
    return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))


def try_livekit_api() -> tuple[dict[str, int], str | None]:
    """Best-effort LiveKit API probe with quick fallback."""
    env = read_backend_env()
    url = env.get("BYOD_LIVEKIT_URL", "ws://127.0.0.1:7880")
    api_key = env.get("BYOD_LIVEKIT_API_KEY")
    api_secret = env.get("BYOD_LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        return {}, "LiveKit API credentials not found; using backend metrics snapshot"

    async def probe() -> dict[str, int]:
        import asyncio
        import aiohttp
        from livekit import api as livekit_api

        timeout = aiohttp.ClientTimeout(total=2.0)
        lk = livekit_api.LiveKitAPI(
            url=livekit_api_url(url),
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
        )
        try:
            rooms_response = await lk.room.list_rooms(livekit_api.ListRoomsRequest())
            rooms = list(rooms_response.rooms)
            publishers = 0
            listeners = 0
            for room in rooms:
                participants_response = await lk.room.list_participants(
                    livekit_api.ListParticipantsRequest(room=room.name)
                )
                for participant in participants_response.participants:
                    identity = str(participant.identity)
                    if identity.startswith("listener_"):
                        listeners += 1
                    else:
                        publishers += 1
            return {
                "livekit_publishers_count": publishers,
                "livekit_listeners_count": listeners,
                "livekit_rooms_count": len(rooms),
            }
        finally:
            await lk.aclose()

    try:
        import asyncio

        return asyncio.run(asyncio.wait_for(probe(), timeout=3.0)), None
    except Exception as exc:
        return {}, f"LiveKit API failed quickly ({type(exc).__name__}: {exc}); using backend metrics snapshot"


def make_sample(
    prev_cpu: tuple[int, int] | None,
    current_cpu: tuple[int, int],
    iface: str,
    prev_net: tuple[int, int] | None,
    current_net: tuple[int, int],
    elapsed: float,
) -> tuple[dict[str, Any], str | None]:
    ram_used, ram_total = ram_gb()
    disk_used, disk_total = disk_gb()
    rx_mbps = tx_mbps = 0.0
    if prev_net and elapsed > 0:
        rx_mbps = round((current_net[0] - prev_net[0]) * 8 / elapsed / 1_000_000, 3)
        tx_mbps = round((current_net[1] - prev_net[1]) * 8 / elapsed / 1_000_000, 3)

    backend_snapshot, backend_warning = http_json(BACKEND_SNAPSHOT_URL)
    livekit_counts, livekit_warning = try_livekit_api()
    backend_snapshot = backend_snapshot or {}
    warning = livekit_warning or backend_warning

    sample = {
        "timestamp_local": local_ts(),
        "timestamp_utc": utc_ts(),
        "cpu_percent": cpu_percent(prev_cpu, current_cpu),
        "ram_used_gb": ram_used,
        "ram_total_gb": ram_total,
        "disk_used_gb": disk_used,
        "disk_total_gb": disk_total,
        "net_iface": iface,
        "rx_mbps": rx_mbps,
        "tx_mbps": tx_mbps,
        "livekit_publishers_count": livekit_counts.get("livekit_publishers_count", 0),
        "livekit_listeners_count": livekit_counts.get("livekit_listeners_count", 0),
        "livekit_rooms_count": livekit_counts.get("livekit_rooms_count", 0),
        "backend_publishers_count": backend_snapshot.get("backend_publishers_count", 0),
        "backend_listeners_count": backend_snapshot.get("backend_listeners_count", 0),
        "backend_active_play_count": backend_snapshot.get("backend_active_play_count", 0),
        "byod_backend_status": service_status("byod-backend"),
        "byod_livekit_status": service_status("byod-livekit"),
        "nginx_status": service_status("nginx"),
        "backend_metrics_snapshot": backend_snapshot,
    }
    return sample, warning


def run(interval_sec: int) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    csv_path = METRICS_DIR / f"byod_metrics_{timestamp}.csv"
    jsonl_path = METRICS_DIR / f"byod_metrics_{timestamp}.jsonl"
    log_path = METRICS_DIR / f"byod_metrics_{timestamp}.log"
    iface = default_iface()
    prev_cpu: tuple[int, int] | None = None
    prev_net: tuple[int, int] | None = None
    prev_time: float | None = None

    with csv_path.open("w", newline="", encoding="utf-8") as csv_fh, jsonl_path.open("a", encoding="utf-8") as jsonl_fh, log_path.open("a", encoding="utf-8") as log_fh:
        writer = csv.DictWriter(csv_fh, fieldnames=FIELDS)
        writer.writeheader()
        log_fh.write(f"{local_ts()} analyzer_start interval_sec={interval_sec} iface={iface}\n")
        log_fh.flush()
        while True:
            now = time.monotonic()
            current_cpu = read_proc_stat()
            current_net = net_bytes(iface)
            elapsed = interval_sec if prev_time is None else max(0.001, now - prev_time)
            sample, warning = make_sample(prev_cpu, current_cpu, iface, prev_net, current_net, elapsed)
            writer.writerow({field: sample.get(field) for field in FIELDS})
            csv_fh.flush()
            jsonl_fh.write(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n")
            jsonl_fh.flush()
            log_fh.write(
                f"{sample['timestamp_local']} cpu={sample['cpu_percent']} ram={sample['ram_used_gb']}/{sample['ram_total_gb']}GB "
                f"rx={sample['rx_mbps']}Mbps tx={sample['tx_mbps']}Mbps backend_listeners={sample['backend_listeners_count']} "
                f"active_play={sample['backend_active_play_count']} backend={sample['byod_backend_status']} "
                f"livekit={sample['byod_livekit_status']} nginx={sample['nginx_status']}\n"
            )
            if warning:
                log_fh.write(f"{local_ts()} WARNING {warning}\n")
            log_fh.flush()
            prev_cpu = current_cpu
            prev_net = current_net
            prev_time = now
            time.sleep(interval_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BYOD VPS metrics analyzer")
    parser.add_argument("--interval-sec", type=int, default=120)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.interval_sec < 1:
        raise SystemExit("--interval-sec must be >= 1")
    run(args.interval_sec)
