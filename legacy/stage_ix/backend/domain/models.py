from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelConfig:
    channel_id: str
    channel_label: str
    listen: bool


@dataclass
class I18NLibrary:
    room_name_i18n: dict[str, str]
    custom_status_text_blocked_i18n: dict[str, str]
    custom_status_text_closed_i18n: dict[str, str]


@dataclass
class RoomConfig:
    pin: str
    target_capacity: int
    channels: list[ChannelConfig]
    i18n_library: I18NLibrary


@dataclass
class PublisherSession:
    publisher_id: str
    hostname: str
    websocket: Any
    connected_at_ts: float
    last_seen_ts: float
    online: bool = True


@dataclass
class ListenerSession:
    listener_id: str
    websocket: Any
    connected_at_ts: float
    last_seen_ts: float
    last_heartbeat_ts: float
    active_play_started: bool = False
    active_play: bool = False
    selected_channel: str | None = None


@dataclass
class RuntimeState:
    channels: list[dict[str, Any]]
    publishers: dict[str, PublisherSession] = field(default_factory=dict)
    listeners: dict[str, ListenerSession] = field(default_factory=dict)
    publisher_counter: int = 0
    listener_counter: int = 0


@dataclass
class ImportValidationError:
    line: int
    field: str
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }
