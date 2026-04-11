import json
from pathlib import Path


class PublisherStateStore:
    def __init__(self) -> None:
        self.path = Path.home() / ".byod_publisher_state.json"

    def load(self) -> dict:
        if not self.path.exists():
            return {"backend_ws_url": "", "pin": "", "device_map": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"backend_ws_url": "", "pin": "", "device_map": {}}
            data.setdefault("backend_ws_url", "")
            data.setdefault("pin", "")
            data.setdefault("device_map", {})
            if not isinstance(data["device_map"], dict):
                data["device_map"] = {}
            return data
        except Exception:
            return {"backend_ws_url": "", "pin": "", "device_map": {}}

    def save(self, payload: dict) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
