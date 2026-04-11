from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from .models import ChannelState, RuntimeState


class JsonPersistence:
    def __init__(self, root: str = "backend_data") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def room_config_path(self) -> Path:
        return self.root / "room_config_v1.json"

    @property
    def runtime_state_path(self) -> Path:
        return self.root / "runtime_state_v1.json"

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def save_room_config(self, state: RuntimeState) -> None:
        payload = {
            "schema_version": 1,
            "room_id": "room_main",
            "pin": state.pin,
            "room_name": state.room_name,
            "target_capacity": state.target_capacity,
            "channels": [
                {
                    "channel_id": ch.channel_id,
                    "channel_label": ch.channel_label,
                    "listen": ch.listen,
                }
                for ch in state.channels
            ],
            "updated_ts": int(time.time()),
        }
        self._atomic_write_json(self.room_config_path, payload)

    def save_runtime(self, state: RuntimeState) -> None:
        payload = {
            "schema_version": 1,
            "room_status": state.room_status,
            "owners": {ch.channel_id: ch.owner for ch in state.channels},
            "publisher_online": {pub_id: pub.online for pub_id, pub in state.publishers.items()},
            "overrides": dict(state.overrides),
            "updated_ts": int(time.time()),
        }
        self._atomic_write_json(self.runtime_state_path, payload)

    def load(self) -> RuntimeState:
        state = RuntimeState()
        if self.room_config_path.exists():
            config = json.loads(self.room_config_path.read_text(encoding="utf-8"))
            state.pin = config.get("pin", state.pin)
            state.room_name = config.get("room_name", state.room_name)
            state.target_capacity = int(config.get("target_capacity", state.target_capacity))
            state.max_active_listeners = int(state.target_capacity * 1.05)
            state.max_new_connections_per_sec = max(1, int(state.target_capacity / 15))
            channels = []
            for row in config.get("channels", []):
                channels.append(
                    ChannelState(
                        channel_id=row["channel_id"],
                        channel_label=row["channel_label"],
                        listen=bool(row["listen"]),
                    )
                )
            if channels:
                state.channels = channels

        if self.runtime_state_path.exists():
            runtime = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
            state.room_status = runtime.get("room_status", state.room_status)
            owners = runtime.get("owners", {})
            for ch in state.channels:
                ch.owner = owners.get(ch.channel_id)
            overrides = runtime.get("overrides", {})
            state.overrides["blocked"] = overrides.get("blocked")
            state.overrides["closed"] = overrides.get("closed")
        return state
