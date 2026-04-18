from __future__ import annotations

import contextlib
from datetime import timedelta
from typing import Any

from livekit import api as livekit_api

from backend.config import HEARTBEAT_TIMEOUT_SECONDS, JWT_LIFETIME_SECONDS, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
from backend.domain.models import RoomConfig
from backend.persistence.storage import JsonStorage
from backend.services.state_service import StateService


class RoomService:
    def __init__(self, state_service: StateService, storage: JsonStorage, livekit_url: str) -> None:
        self.state_service = state_service
        self.storage = storage
        self.livekit_url = livekit_url

    def create_livekit_token(self, identity: str) -> str:
        token = (
            livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_grants(livekit_api.VideoGrants(room_join=True, room=self.state_service.runtime.room_name))
            .with_ttl(timedelta(seconds=JWT_LIFETIME_SECONDS))
        )
        return token.to_jwt()

    def room_config_payload(self) -> dict[str, Any]:
        runtime = self.state_service.runtime
        return {
            "schema_version": 1,
            "room_id": "room_main",
            "pin": runtime.pin,
            "room_name": runtime.room_name,
            "target_capacity": runtime.target_capacity,
            "channels": [
                {
                    "channel_id": channel["channel_id"],
                    "channel_label": channel["channel_label"],
                    "listen": channel.get("listen", True),
                }
                for channel in self.state_service.state.channels
            ],
            "i18n_library": runtime.i18n_library,
            "updated_ts": self.storage.now_ts(),
        }

    def runtime_state_payload(self) -> dict[str, Any]:
        runtime = self.state_service.runtime
        return {
            "schema_version": 1,
            "room_status": runtime.room_status,
            "owners": {
                channel["channel_id"]: channel.get("owner") for channel in self.state_service.state.channels
            },
            "publisher_online": {
                publisher_id: True for publisher_id in self.state_service.state.publishers.keys()
            },
            "updated_ts": self.storage.now_ts(),
        }

    def recording_state_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "recording_active": self.state_service.recording_active,
            "recording_started_ts": self.state_service.recording_started_ts,
            "active_files": self.state_service.recording_files,
            "updated_ts": self.storage.now_ts(),
        }

    def persist_all(self) -> None:
        self.storage.save_room_config(self.room_config_payload())
        self.storage.save_runtime_state(self.runtime_state_payload())
        self.storage.save_recording_state(self.recording_state_payload())

    def load_from_persistence(self) -> bool:
        runtime = self.state_service.runtime
        room_config_exists = self.storage.room_config_path.exists()

        room_config = self.storage.load_room_config()
        if room_config:
            runtime.pin = str(room_config.get("pin") or runtime.pin)
            runtime.room_name = str(room_config.get("room_name") or runtime.room_name)
            target_capacity = int(room_config.get("target_capacity") or runtime.target_capacity)
            self.state_service.update_derived_limits(target_capacity)

            persisted_channels = room_config.get("channels")
            if isinstance(persisted_channels, list) and persisted_channels:
                owners = {
                    channel["channel_id"]: channel.get("owner")
                    for channel in self.state_service.state.channels
                }
                self.state_service.state.channels = []
                for channel in persisted_channels:
                    cid = str(channel.get("channel_id") or "")
                    if not cid:
                        continue
                    self.state_service.state.channels.append(
                        {
                            "channel_id": cid,
                            "channel_label": str(channel.get("channel_label") or cid),
                            "listen": bool(channel.get("listen", True)),
                            "owner": owners.get(cid),
                        }
                    )

            persisted_i18n = room_config.get("i18n_library")
            if isinstance(persisted_i18n, dict):
                for key in (
                    "room_name_i18n",
                    "custom_status_text_blocked_i18n",
                    "custom_status_text_closed_i18n",
                ):
                    value = persisted_i18n.get(key)
                    if isinstance(value, dict):
                        runtime.i18n_library[key] = {str(k): str(v) for k, v in value.items()}
                runtime.room_name = str(runtime.i18n_library.get("room_name_i18n", {}).get("en", runtime.room_name))

        runtime_state = self.storage.load_runtime_state()
        if runtime_state:
            runtime.room_status = str(runtime_state.get("room_status") or runtime.room_status)
            owners = runtime_state.get("owners") or {}
            if isinstance(owners, dict):
                for channel in self.state_service.state.channels:
                    channel["owner"] = owners.get(channel["channel_id"])
        recording_state = self.storage.load_recording_state()
        if recording_state:
            self.state_service.recording_active = bool(recording_state.get("recording_active", False))
            self.state_service.recording_started_ts = recording_state.get("recording_started_ts")
            files = recording_state.get("active_files")
            if isinstance(files, list):
                self.state_service.recording_files = files

        runtime.i18n_library["room_name_i18n"]["en"] = runtime.room_name
        return room_config_exists

    async def apply_imported_room_config(self, config: RoomConfig, state_lock: Any) -> tuple[list[Any], list[Any]]:
        publishers_to_close: list[Any] = []
        listeners_to_close: list[Any] = []
        async with state_lock:
            publishers_to_close = [session.websocket for session in self.state_service.state.publishers.values()]
            listeners_to_close = list(self.state_service.state.listeners)

            self.state_service.state.publishers.clear()
            self.state_service.state.listeners.clear()

            runtime = self.state_service.runtime
            runtime.pin = config.pin
            runtime.room_name = config.i18n_library.room_name_i18n["en"]
            runtime.i18n_library["room_name_i18n"] = dict(config.i18n_library.room_name_i18n)
            runtime.i18n_library["custom_status_text_blocked_i18n"] = dict(config.i18n_library.custom_status_text_blocked_i18n)
            runtime.i18n_library["custom_status_text_closed_i18n"] = dict(config.i18n_library.custom_status_text_closed_i18n)

            self.state_service.recording_active = False
            self.state_service.recording_started_ts = None
            self.state_service.recording_files = []
            self.state_service.update_derived_limits(config.target_capacity)

            self.state_service.state.channels = [
                {
                    "channel_id": channel.channel_id,
                    "channel_label": channel.channel_label,
                    "listen": channel.listen,
                    "owner": None,
                }
                for channel in config.channels
            ]
            self.persist_all()

        for ws in publishers_to_close + listeners_to_close:
            with contextlib.suppress(Exception):
                await ws.close()

        self.storage.log_event(
            "json_import_applied",
            request_id=self.state_service.next_request_id("json-import"),
            target_capacity=self.state_service.runtime.target_capacity,
            max_active_listeners=self.state_service.runtime.max_active_listeners,
            max_new_connections_per_sec=self.state_service.runtime.max_new_connections_per_sec,
        )
        return publishers_to_close, listeners_to_close

    async def drop_publisher_locked(self, publisher_id: str) -> None:
        session = self.state_service.state.publishers.get(publisher_id)
        if session is None:
            return
        session.online = False
        released_channels: list[str] = []
        for channel in self.state_service.state.channels:
            if channel.get("owner") == publisher_id:
                channel["owner"] = None
                channel["off_air_ts"] = self.state_service.now_ts()
                released_channels.append(channel["channel_id"])
                self.storage.log_event(
                    "channel_released_on_disconnect",
                    publisher_id=publisher_id,
                    channel_id=channel["channel_id"],
                )
        self.state_service.state.publishers.pop(publisher_id, None)
        self.storage.log_connection(
            "publisher_disconnected",
            publisher_id=publisher_id,
            released_channels=released_channels,
        )

    async def start_recording_locked(self, reason: str) -> None:
        if self.state_service.recording_active:
            return
        self.state_service.recording_active = True
        self.state_service.recording_started_ts = self.state_service.now_ts()
        self.state_service.recording_files = []
        self.storage.log_event("recording_marked_active", reason=reason, note="real multitrack recording is disabled")

    async def stop_recording_locked(self, reason: str) -> None:
        if not self.state_service.recording_active:
            return
        self.storage.log_event(
            "recording_marked_inactive",
            reason=reason,
            started_ts=self.state_service.recording_started_ts,
        )
        self.state_service.recording_active = False
        self.state_service.recording_started_ts = None
        self.state_service.recording_files = []

    async def set_room_status_locked(self, new_status: str, reason: str) -> bool:
        if new_status not in {"OPENED", "BLOCKED", "CLOSED"}:
            return False
        self.state_service.runtime.room_status = new_status
        if new_status == "OPENED":
            await self.start_recording_locked(reason=reason)
        if new_status == "CLOSED":
            await self.stop_recording_locked(reason=reason)
        self.storage.log_event("room_status_changed", room_status=self.state_service.runtime.room_status, reason=reason)
        return True

    async def monitor_timeouts(self, state_lock: Any, broadcast_cb: Any) -> None:
        import asyncio

        while True:
            await asyncio.sleep(1)
            expired: list[str] = []
            async with state_lock:
                now = float(self.state_service.now_ts())
                for publisher_id, session in self.state_service.state.publishers.items():
                    if now - session.last_seen_ts > HEARTBEAT_TIMEOUT_SECONDS:
                        expired.append(publisher_id)
                for publisher_id in expired:
                    await self.drop_publisher_locked(publisher_id)
                if expired:
                    self.persist_all()
            if expired:
                await broadcast_cb()
