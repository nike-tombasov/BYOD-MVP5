from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonStorage:
    def __init__(self, data_dir: Path, room_config_path: Path, runtime_state_path: Path, recording_state_path: Path) -> None:
        self.data_dir = data_dir
        self.room_config_path = room_config_path
        self.runtime_state_path = runtime_state_path
        self.recording_state_path = recording_state_path

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def now_ts(self) -> int:
        return int(time.time())

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def load_json_if_exists(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_room_config(self) -> dict[str, Any] | None:
        return self.load_json_if_exists(self.room_config_path)

    def save_room_config(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.room_config_path, payload)

    def load_runtime_state(self) -> dict[str, Any] | None:
        return self.load_json_if_exists(self.runtime_state_path)

    def save_runtime_state(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.runtime_state_path, payload)

    def load_recording_state(self) -> dict[str, Any] | None:
        return self.load_json_if_exists(self.recording_state_path)

    def save_recording_state(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.recording_state_path, payload)

    def current_day_suffix(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def get_connections_log_path(self) -> Path:
        return self.data_dir / f"connections_log_{self.current_day_suffix()}.jsonl"

    def get_events_log_path(self) -> Path:
        return self.data_dir / f"events_log_{self.current_day_suffix()}.jsonl"

    def append_jsonl(self, path: Path, event: dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()

    def log_connection(self, event: str, **fields: Any) -> None:
        payload = {"ts": self.now_ts(), "event": event, **fields}
        self.append_jsonl(self.get_connections_log_path(), payload)

    def log_event(self, event: str, **fields: Any) -> None:
        payload = {"ts": self.now_ts(), "event": event, **fields}
        self.append_jsonl(self.get_events_log_path(), payload)
