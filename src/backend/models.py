from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PublisherSession:
    publisher_id: str
    hostname: str
    websocket: Any
    connected_at_ts: float
    last_seen_ts: float
    ip: str
    online: bool = True


@dataclass(slots=True)
class ListenerSession:
    listener_id: str
    websocket: Any
    connected_at_ts: float
    last_seen_ts: float
    ip: str


@dataclass(slots=True)
class ChannelState:
    channel_id: str
    channel_label: str
    listen: bool
    owner: str | None = None

    def to_publisher_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "channel_label": self.channel_label,
            "listen": self.listen,
            "owner": self.owner,
        }

    def to_listener_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "channel_label": self.channel_label,
            "listen": self.listen,
        }


@dataclass(slots=True)
class RuntimeState:
    room_status: str = "CLOSED"
    room_name: str = "test room"
    pin: str = "123456"
    target_capacity: int = 300
    max_active_listeners: int = 315
    max_new_connections_per_sec: int = 20
    publisher_counter: int = 0
    listener_counter: int = 0
    channels: list[ChannelState] = field(default_factory=list)
    publishers: dict[str, PublisherSession] = field(default_factory=dict)
    listeners: dict[str, ListenerSession] = field(default_factory=dict)
    overrides: dict[str, str | None] = field(default_factory=lambda: {"blocked": None, "closed": None})
    room_name_i18n: dict[str, str] = field(default_factory=lambda: {"en": "test room", "ru": "тестовая комната"})
    custom_status_text_blocked_i18n: dict[str, str] = field(
        default_factory=lambda: {"en": "Temporarily blocked", "ru": "Временно заблокировано"}
    )
    custom_status_text_closed_i18n: dict[str, str] = field(
        default_factory=lambda: {"en": "Room is closed", "ru": "Зал закрыт"}
    )

    def effective_blocked_i18n(self) -> dict[str, str]:
        override = self.overrides.get("blocked")
        if override:
            payload = dict(self.custom_status_text_blocked_i18n)
            payload["en"] = override
            return payload
        return dict(self.custom_status_text_blocked_i18n)

    def effective_closed_i18n(self) -> dict[str, str]:
        override = self.overrides.get("closed")
        if override:
            payload = dict(self.custom_status_text_closed_i18n)
            payload["en"] = override
            return payload
        return dict(self.custom_status_text_closed_i18n)
