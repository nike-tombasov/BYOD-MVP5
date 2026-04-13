import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def ensure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def current_day_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()
