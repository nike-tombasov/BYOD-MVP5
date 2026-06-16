from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import count
from typing import Any

from backend.config import (
    derive_max_active_listeners,
    derive_max_new_connections_per_sec,
)
from backend.domain.models import ListenerSession, PublisherSession, RuntimeState


@dataclass
class RuntimeConfig:
    pin: str
    room_name: str
    room_status: str
    target_capacity: int
    max_active_listeners: int
    max_new_connections_per_sec: int
    i18n_library: dict[str, dict[str, str]] | None = None


class StateService:
    def __init__(self, channels: list[dict[str, Any]], runtime_config: RuntimeConfig) -> None:
        self.state = RuntimeState(channels=[dict(ch) for ch in channels])
        self.runtime = runtime_config
        self.request_counter = count(1)
        self.listener_connect_sec = int(time.time())
        self.listener_connect_count = 0
        self.listener_last_connect_by_ip: dict[str, int] = {}
        self.listener_reject_counters: dict[str, int] = {}
        self.recording_active = False
        self.recording_started_ts: int | None = None
        self.recording_files: list[dict[str, Any]] = []
        if self.runtime.i18n_library is None:
            self.runtime.i18n_library = {}

    def now_ts(self) -> int:
        return int(time.time())

    def next_request_id(self, prefix: str = "server") -> str:
        return f"{prefix}-{next(self.request_counter)}"

    def update_derived_limits(self, target_capacity: int) -> None:
        self.runtime.target_capacity = target_capacity
        self.runtime.max_active_listeners = derive_max_active_listeners(target_capacity)
        self.runtime.max_new_connections_per_sec = derive_max_new_connections_per_sec(target_capacity)

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
        return {
            "room_status": self.runtime.room_status,
            "channels": [
                {
                    "channel_id": channel["channel_id"],
                    "channel_label": channel["channel_label"],
                    "listen": channel.get("listen", True),
                }
                for channel in channels
            ],
        }

    def build_i18n_library_payload(self) -> dict[str, Any]:
        return dict(self.runtime.i18n_library or {})

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

    def add_listener(self, websocket: Any, diagnostic_metadata: dict[str, Any] | None = None) -> ListenerSession:
        listener_id = f"listener_{self.state.listener_counter}"
        self.state.listener_counter += 1
        now = float(self.now_ts())
        metadata = diagnostic_metadata or {}
        worker_index = metadata.get("worker_index")
        parsed_worker_index = worker_index if isinstance(worker_index, int) else None
        session = ListenerSession(
            listener_id=listener_id,
            websocket=websocket,
            connected_at_ts=now,
            last_seen_ts=now,
            last_heartbeat_ts=now,
            active_play=False,
            selected_channel=None,
            client_type=metadata.get("client_type") if isinstance(metadata.get("client_type"), str) else None,
            runner_id=metadata.get("runner_id") if isinstance(metadata.get("runner_id"), str) else None,
            worker_id=metadata.get("worker_id") if isinstance(metadata.get("worker_id"), str) else None,
            worker_index=parsed_worker_index,
            selected_channel_mode=metadata.get("selected_channel_mode")
            if isinstance(metadata.get("selected_channel_mode"), str)
            else None,
        )
        self.state.listeners[listener_id] = session
        return session

    def record_listener_reject(self, reject_code: str) -> None:
        self.listener_reject_counters[reject_code] = self.listener_reject_counters.get(reject_code, 0) + 1

    def remove_listener_by_ws(self, websocket: Any) -> str | None:
        for listener_id, session in list(self.state.listeners.items()):
            if session.websocket is websocket:
                self.state.listeners.pop(listener_id, None)
                return listener_id
        return None
