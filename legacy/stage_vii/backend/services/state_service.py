from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import count
from typing import Any

from backend.domain.models import PublisherSession, RuntimeState


@dataclass
class RuntimeConfig:
    pin: str
    room_name: str
    room_status: str
    target_capacity: int
    max_active_listeners: int
    max_new_connections_per_sec: int
    status_text: str = ""
    overrides: dict[str, str | None] | None = None
    i18n_library: dict[str, dict[str, str]] | None = None


class StateService:
    def __init__(self, channels: list[dict[str, Any]], runtime_config: RuntimeConfig) -> None:
        self.state = RuntimeState(channels=[dict(ch) for ch in channels])
        self.runtime = runtime_config
        self.request_counter = count(1)
        self.listener_connect_sec = int(time.time())
        self.listener_connect_count = 0
        self.listener_last_connect_by_ip: dict[str, int] = {}
        self.recording_active = False
        self.recording_started_ts: int | None = None
        self.recording_files: list[dict[str, Any]] = []
        if self.runtime.overrides is None:
            self.runtime.overrides = {"blocked": None, "closed": None}
        if self.runtime.i18n_library is None:
            self.runtime.i18n_library = {}

    def now_ts(self) -> int:
        return int(time.time())

    def next_request_id(self, prefix: str = "server") -> str:
        return f"{prefix}-{next(self.request_counter)}"

    def update_derived_limits(self, target_capacity: int) -> None:
        self.runtime.target_capacity = target_capacity
        self.runtime.max_active_listeners = int(target_capacity * 1.05)
        self.runtime.max_new_connections_per_sec = max(1, int(target_capacity / 15))

    def make_envelope(self, msg_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
        return {
            "type": msg_type,
            "schema_version": 1,
            "ts": self.now_ts(),
            "request_id": request_id or self.next_request_id(msg_type),
            "payload": payload,
        }

    def get_payload(self, message: dict[str, Any]) -> dict[str, Any]:
        payload = message.get("payload")
        if isinstance(payload, dict):
            return payload
        return message

    def validate_message_envelope(self, message: dict[str, Any]) -> str | None:
        if "payload" not in message:
            return None
        if not isinstance(message.get("type"), str):
            return "INVALID_TYPE"
        if message.get("schema_version") != 1:
            return "UNSUPPORTED_SCHEMA_VERSION"
        if not isinstance(message.get("request_id"), str):
            return "INVALID_REQUEST_ID"
        if not isinstance(message.get("payload"), dict):
            return "INVALID_PAYLOAD"
        return None

    def build_publisher_state_snapshot(self, channels: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "room_name": self.runtime.room_name,
            "room_status": self.runtime.room_status,
            "channels": [
                {
                    "channel_id": channel["channel_id"],
                    "channel_label": channel["channel_label"],
                    "owner": channel.get("owner"),
                    "listen": channel.get("listen", True),
                }
                for channel in channels
            ],
        }

    def build_listener_state_snapshot(self, channels: list[dict[str, Any]]) -> dict[str, Any]:
        custom_text = self.runtime.status_text
        if self.runtime.room_status == "BLOCKED" and self.runtime.overrides and self.runtime.overrides.get("blocked"):
            custom_text = str(self.runtime.overrides["blocked"])
        if self.runtime.room_status == "CLOSED" and self.runtime.overrides and self.runtime.overrides.get("closed"):
            custom_text = str(self.runtime.overrides["closed"])
        return {
            "room_status": self.runtime.room_status,
            "status_custom_text": custom_text,
            "channels": [
                {
                    "channel_id": channel["channel_id"],
                    "channel_label": channel["channel_label"],
                    "listen": channel.get("listen", True),
                }
                for channel in channels
            ],
        }

    def build_legacy_state_snapshot(self, channels: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "room_name": self.runtime.room_name,
            "room_status": self.runtime.room_status,
            "status_custom_text": self.runtime.status_text,
            "channels": channels,
        }

    def find_channel(self, channel_id: str | None) -> dict[str, Any] | None:
        for channel in self.state.channels:
            if channel["channel_id"] == channel_id:
                return channel
        return None

    def add_publisher(self, websocket: Any, hostname: str) -> PublisherSession:
        publisher_id = f"{hostname}_{self.state.publisher_counter}"
        self.state.publisher_counter += 1
        session = PublisherSession(
            publisher_id=publisher_id,
            hostname=hostname,
            websocket=websocket,
            connected_at_ts=float(self.now_ts()),
            last_seen_ts=float(self.now_ts()),
        )
        self.state.publishers[publisher_id] = session
        return session
