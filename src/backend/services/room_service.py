from __future__ import annotations

import contextlib
import logging
import socket
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse, urlunparse

from livekit import api as livekit_api

from backend.config import (
    HEARTBEAT_TIMEOUT_SECONDS,
    JWT_LIFETIME_SECONDS,
    LISTENER_ACTIVE_PLAY_STALE_SECONDS,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS,
)
from backend.domain.models import RoomConfig
from backend.persistence.storage import JsonStorage
from backend.services.state_service import StateService


logger = logging.getLogger("byod.backend.room_service")


class RoomService:
    def __init__(self, state_service: StateService, storage: JsonStorage, livekit_url: str) -> None:
        self.state_service = state_service
        self.storage = storage
        self.livekit_url = livekit_url

    def _livekit_tcp_target(self) -> tuple[str, int] | None:
        parsed = urlparse(self.livekit_url)
        host = parsed.hostname
        if host is None:
            return None
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        return host, port

    def is_livekit_reachable(self) -> bool:
        return bool(self.get_livekit_reachability()["ok"])

    def get_livekit_reachability(self) -> dict[str, Any]:
        target = self._livekit_tcp_target()
        if target is None:
            return {
                "ok": False,
                "host": None,
                "port": None,
                "timeout": LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS,
                "error_type": "InvalidLiveKitUrl",
                "error_message": "LiveKit URL has no hostname",
            }
        host, port = target
        try:
            with socket.create_connection(target, timeout=LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS):
                return {
                    "ok": True,
                    "host": host,
                    "port": port,
                    "timeout": LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS,
                    "error_type": None,
                    "error_message": None,
                }
        except OSError as exc:
            return {
                "ok": False,
                "host": host,
                "port": port,
                "timeout": LIVEKIT_HEALTHCHECK_TIMEOUT_SECONDS,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

    def log_livekit_unavailable(self, context: str, **fields: Any) -> None:
        self.storage.log_event("livekit_unreachable", context=context, livekit_url=self.livekit_url, **fields)
        logger.error("livekit_unreachable context=%s fields=%s", context, fields)

    def livekit_http_api_url(self) -> str:
        parsed = urlparse(self.livekit_url)
        scheme = "https" if parsed.scheme == "wss" else "http"
        return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))

    async def get_livekit_participant_snapshot(self) -> dict[str, Any]:
        """Best-effort LiveKit RoomService visibility for local admin metrics.

        The returned payload intentionally contains only room/participant/track
        labels and counts. It never includes API keys, API secrets, JWTs, or PINs.
        """
        result: dict[str, Any] = {
            "livekit_api_ok": False,
            "livekit_api_error": None,
            "livekit_rooms_count": 0,
            "livekit_participants_count": 0,
            "livekit_listener_participants_count": 0,
            "livekit_publisher_participants_count": 0,
            "livekit_participants_by_identity_prefix": {},
            "livekit_room_names": [],
            "livekit_participant_identities_sample": [],
            "livekit_published_tracks_sample": [],
            "livekit_room_participants": {},
        }
        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=2.0)
            lk = livekit_api.LiveKitAPI(
                url=self.livekit_http_api_url(),
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET,
                timeout=timeout,
            )
            try:
                rooms_response = await lk.room.list_rooms(livekit_api.ListRoomsRequest())
                rooms = list(rooms_response.rooms)
                result["livekit_rooms_count"] = len(rooms)
                result["livekit_room_names"] = [str(room.name) for room in rooms]

                prefix_counts: dict[str, int] = {}
                participants_count = 0
                listener_count = 0
                publisher_count = 0
                room_participants: dict[str, list[dict[str, Any]]] = {}
                participant_identity_sample: list[str] = []
                published_tracks_sample: list[dict[str, Any]] = []

                for room in rooms:
                    room_name = str(room.name)
                    participants_response = await lk.room.list_participants(
                        livekit_api.ListParticipantsRequest(room=room_name)
                    )
                    summaries: list[dict[str, Any]] = []
                    for participant in participants_response.participants:
                        identity = str(participant.identity or "")
                        prefix = identity.split("_", 1)[0] if "_" in identity else (identity or "unknown")
                        prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                        participants_count += 1
                        if identity.startswith("listener_"):
                            listener_count += 1
                        else:
                            publisher_count += 1

                        tracks = list(getattr(participant, "tracks", []) or [])
                        published_track_names = [str(getattr(track, "name", "") or "") for track in tracks]
                        if len(participant_identity_sample) < 25:
                            participant_identity_sample.append(identity)
                        for track_name in published_track_names:
                            if track_name and len(published_tracks_sample) < 25:
                                published_tracks_sample.append({"room": room_name, "identity": identity, "track_name": track_name})
                        audio_tracks = [
                            track for track in tracks
                            if str(getattr(track, "type", "")).lower().endswith("audio")
                            or str(getattr(track, "kind", "")).lower().endswith("audio")
                        ]
                        summaries.append({
                            "identity": identity,
                            "sid": str(getattr(participant, "sid", "") or ""),
                            "state": str(getattr(participant, "state", "") or ""),
                            "tracks_count": len(tracks),
                            "published_audio_tracks_count": len(audio_tracks),
                            "published_track_names": published_track_names,
                        })
                    room_participants[room_name] = summaries

                result.update({
                    "livekit_api_ok": True,
                    "livekit_participants_count": participants_count,
                    "livekit_listener_participants_count": listener_count,
                    "livekit_publisher_participants_count": publisher_count,
                    "livekit_participants_by_identity_prefix": prefix_counts,
                    "livekit_participant_identities_sample": participant_identity_sample,
                    "livekit_published_tracks_sample": published_tracks_sample,
                    "livekit_room_participants": room_participants,
                })
            finally:
                await lk.aclose()
        except Exception as exc:
            result["livekit_api_error"] = f"{type(exc).__name__}: {exc}"
        return result

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
            "subsite_name": runtime.subsite_name,
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
            "listener_online": len(self.state_service.state.listeners),
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
            persisted_subsite = room_config.get("subsite_name")
            runtime.subsite_name = persisted_subsite if isinstance(persisted_subsite, str) and persisted_subsite else None
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
            listeners_to_close = [session.websocket for session in self.state_service.state.listeners.values()]

            self.state_service.state.publishers.clear()
            self.state_service.state.listeners.clear()

            runtime = self.state_service.runtime
            runtime.pin = config.pin
            runtime.subsite_name = config.subsite_name
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
            expired_publishers: list[str] = []
            stale_listener_sessions: list[tuple[str, Any, str, str]] = []
            async with state_lock:
                now = float(self.state_service.now_ts())
                for publisher_id, session in self.state_service.state.publishers.items():
                    if now - session.last_seen_ts > HEARTBEAT_TIMEOUT_SECONDS:
                        expired_publishers.append(publisher_id)
                for publisher_id in expired_publishers:
                    await self.drop_publisher_locked(publisher_id)
                for listener_id, listener_session in list(self.state_service.state.listeners.items()):
                    no_active_play_timeout = (
                        not listener_session.active_play_started
                        and now - listener_session.connected_at_ts > LISTENER_ACTIVE_PLAY_STALE_SECONDS
                    )
                    active_play_heartbeat_timeout = (
                        listener_session.active_play_started
                        and listener_session.active_play
                        and now - listener_session.last_heartbeat_ts > LISTENER_ACTIVE_PLAY_STALE_SECONDS
                    )
                    if not no_active_play_timeout and not active_play_heartbeat_timeout:
                        continue

                    reconnect_code = "LISTENER_NO_ACTIVE_PLAY_TIMEOUT" if no_active_play_timeout else "LISTENER_SESSION_STALE"
                    reconnect_reason = "NO_ACTIVE_PLAY_TRIGGER" if no_active_play_timeout else "MISSING_ACTIVE_PLAY_HEARTBEAT"
                    stale_note = "no_active_play_timeout" if no_active_play_timeout else "active_play_heartbeat_timeout"
                    stale_listener_sessions.append((listener_id, listener_session.websocket, reconnect_code, reconnect_reason))
                    self.state_service.state.listeners.pop(listener_id, None)
                    self.storage.log_connection(
                        "listener_stale_removed",
                        listener_id=listener_id,
                        stale_seconds=LISTENER_ACTIVE_PLAY_STALE_SECONDS,
                        reason=stale_note,
                    )
                if expired_publishers or stale_listener_sessions:
                    self.persist_all()
            for listener_id, ws, reconnect_code, reconnect_reason in stale_listener_sessions:
                with contextlib.suppress(Exception):
                    await ws.send_json(
                        self.state_service.make_envelope(
                            "reconnect_required",
                            {
                                "ok": False,
                                "code": reconnect_code,
                                "reason": reconnect_reason,
                                "listener_id": listener_id,
                            },
                            request_id=self.state_service.next_request_id("reconnect-required"),
                        )
                    )
                with contextlib.suppress(Exception):
                    await ws.close()
            if expired_publishers:
                await broadcast_cb()
