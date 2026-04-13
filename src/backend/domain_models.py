import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublisherSession:
    publisher_id: str
    hostname: str
    websocket: Any
    connected_at_ts: float
    last_seen_ts: float
    online: bool = True


@dataclass
class ServerState:
    channels: list[dict[str, Any]]
    publishers: dict[str, PublisherSession] = field(default_factory=dict)
    listeners: set[Any] = field(default_factory=set)
    publisher_counter: int = 0
    listener_counter: int = 0


@dataclass
class ListenerRuntime:
    connect_sec: int = field(default_factory=lambda: int(time.time()))
    connect_count: int = 0
    last_connect_by_ip: dict[str, int] = field(default_factory=dict)


@dataclass
class BackendRuntime:
    pin: str
    room_name: str
    room_status: str
    status_text: str
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    jwt_lifetime_seconds: int
    heartbeat_timeout_seconds: int
    schema_version: int
    target_capacity: int
    max_active_listeners: int
    max_new_connections_per_sec: int
    overrides: dict[str, str | None]
    i18n_library: dict[str, dict[str, str]]
    state: ServerState
    listener_runtime: ListenerRuntime
    recording_active: bool = False
    recording_started_ts: int | None = None
    recording_files: list[dict[str, Any]] = field(default_factory=list)
