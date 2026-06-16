#!/usr/bin/env python3
"""Stage XI BYOD Protocol/engine Listener Loader.

Console-only Windows-oriented load runner. It uses the normal backend Listener
WebSocket protocol and joins LiveKit as real WebRTC participants. It never opens
Web Listener UI and never plays audio to a physical output device.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import csv
import json
import logging
import random
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import websockets
from websockets import ConnectionClosedOK, WebSocketClientProtocol

try:
    from livekit import rtc
except Exception:  # pragma: no cover - dependency validation is done by operator install
    rtc = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"
SCHEMA_VERSION = 1


def local_ts() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_bool(value: str | bool | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def build_ws_url(server: str) -> str:
    parsed = urlparse(server)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--server must be http://host or https://host")
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/ws/listener", "", "", ""))


def build_health_url(server: str) -> str:
    parsed = urlparse(server)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--server must be http://host or https://host")
    return urlunparse((parsed.scheme, parsed.netloc, "/health", "", "", ""))


def token_exp_utc(token: str) -> str | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


@dataclass
class Args:
    server: str
    listeners: int
    ramp_mode: str
    listener_every_sec: float
    channel_mode: str
    channel_id: str | None
    hold_sec: float
    runner_id: str
    heartbeat_sec: float
    connect_timeout_sec: float
    channels_timeout_sec: float
    reconnect: bool
    log_level: str
    loader_run_id: str
    debug_publications: bool
    subscription_timeout_sec: float


@dataclass
class Counters:
    workers_started: int = 0
    backend_connected: int = 0
    livekit_connected: int = 0
    subscription_requested: int = 0
    subscribed: int = 0
    waiting_for_track: int = 0
    playing_heartbeat_sent: int = 0
    failed: int = 0
    reconnecting: int = 0
    holding: int = 0
    completed: int = 0


@dataclass
class SharedState:
    args: Args
    backend_ws_url: str
    health_url: str
    stop_event: asyncio.Event
    counters: Counters = field(default_factory=Counters)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    jsonl_path: Path | None = None
    csv_path: Path | None = None

    def should_log_jsonl(self, level: str) -> bool:
        return getattr(logging, level.upper(), logging.INFO) >= getattr(logging, self.args.log_level, logging.INFO)

    async def inc(self, field_name: str, delta: int = 1) -> None:
        async with self.lock:
            setattr(self.counters, field_name, getattr(self.counters, field_name) + delta)

    async def snapshot(self) -> dict[str, int]:
        async with self.lock:
            return dict(self.counters.__dict__)


class Worker:
    def __init__(self, index: int, shared: SharedState) -> None:
        self.index = index
        self.shared = shared
        self.worker_id = f"{shared.args.runner_id}-L{index:04d}"
        self.listener_id: str | None = None
        self.selected_channel: str | None = None
        self.ws: WebSocketClientProtocol | None = None
        self.room: Any = None
        self.subscribed = False
        self.subscription_requested = False
        self.subscription_counted = False
        self.waiting_for_track_counted = False
        self.media_receive_not_confirmed_logged = False
        self.closing = False
        self.closed = False
        self.loop: asyncio.AbstractEventLoop | None = None
        self.loop_closed_logged = False
        self.subscription_task: asyncio.Task[None] | None = None
        self.heartbeat_task: asyncio.Task[None] | None = None
        self.last_waiting_log_ts = 0.0
        self.last_pending_log_ts = 0.0
        self.participant_connected_logged = False
        self.publication_inventory_logged = False
        self.selected_publication_state: tuple[bool, bool, bool] | None = None
        self.selected_publication_diagnostics_logged: set[str] = set()
        self.subscription_lifecycle = 0
        self.subscribed_lifecycle_logged: set[int] = set()
        self.logger = logging.getLogger(f"worker.{self.worker_id}")


    def safe_create_task(self, coro: Any, event_name: str | None = None) -> asyncio.Task[Any] | None:
        if self.shared.stop_event.is_set() or self.closing or self.closed:
            with contextlib.suppress(Exception):
                coro.close()
            return None
        loop = self.loop
        try:
            if loop is None:
                loop = asyncio.get_running_loop()
                self.loop = loop
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
            task_holder: dict[str, asyncio.Task[Any]] = {}

            def _schedule() -> None:
                if self.shared.stop_event.is_set() or self.closing or self.closed:
                    with contextlib.suppress(Exception):
                        coro.close()
                    return
                task_holder["task"] = loop.create_task(coro)

            loop.call_soon_threadsafe(_schedule)
            return task_holder.get("task")
        except RuntimeError as exc:
            with contextlib.suppress(Exception):
                coro.close()
            if "Event loop is closed" in str(exc) and not self.loop_closed_logged:
                self.loop_closed_logged = True
                self.logger.debug("livekit_callback_suppressed_after_loop_closed event=%s", event_name)
            return None

    async def stop_background_tasks(self) -> None:
        for task in (self.subscription_task, self.heartbeat_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self.subscription_task, self.heartbeat_task):
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self.subscription_task = None
        self.heartbeat_task = None

    async def event(self, event: str, level: str = "INFO", **fields: Any) -> None:
        payload = {
            "ts_local": local_ts(),
            "ts_utc": utc_iso(),
            "level": level,
            "event": event,
            "runner_id": self.shared.args.runner_id,
            "loader_run_id": self.shared.args.loader_run_id,
            "worker_id": self.worker_id,
            "worker_index": self.index,
            **fields,
        }
        if self.shared.jsonl_path and self.shared.should_log_jsonl(level):
            with self.shared.jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        getattr(self.logger, level.lower(), self.logger.info)("%s %s", event, fields)

    def envelope(self, msg_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": msg_type,
            "schema_version": SCHEMA_VERSION,
            "ts": int(time.time()),
            "request_id": f"{self.worker_id}-{msg_type}-{int(time.time() * 1000)}",
            "payload": payload,
        }

    async def run(self) -> None:
        self.loop = asyncio.get_running_loop()
        await self.shared.inc("workers_started")
        while not self.shared.stop_event.is_set():
            try:
                await self.single_run()
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.event("worker_failed", "ERROR", error_type=type(exc).__name__, error=str(exc))
                await self.shared.inc("failed")
                if not self.shared.args.reconnect or self.shared.stop_event.is_set():
                    return
                await self.shared.inc("reconnecting")
                await asyncio.sleep(min(5.0, self.shared.args.heartbeat_sec))
            finally:
                await self.close()

    async def single_run(self) -> None:
        await self.preflight()
        async with websockets.connect(
            self.shared.backend_ws_url,
            open_timeout=self.shared.args.connect_timeout_sec,
            ping_interval=20,
            ping_timeout=20,
            max_queue=32,
        ) as ws:
            self.ws = ws
            await self.shared.inc("backend_connected")
            await self.event("backend_ws_connected", backend_ws_url=self.shared.backend_ws_url)
            await ws.send(json.dumps(self.envelope("connecting", {
                "client_role": "listener",
                "client_type": "load_runner",
                "runner_id": self.shared.args.runner_id,
                "loader_run_id": self.shared.args.loader_run_id,
                "worker_id": self.worker_id,
                "worker_index": self.index,
                "selected_channel_mode": self.shared.args.channel_mode,
            })))
            try:
                token, livekit_url, channels = await self.wait_for_connect_and_channels(ws)
            except ConnectionClosedOK:
                if self.shared.stop_event.is_set() or self.closing:
                    await self.event("backend_ws_closed_normal")
                    return
                raise
            self.selected_channel = self.choose_channel(channels)
            await self.connect_livekit(livekit_url, token)
            self.subscription_task = asyncio.create_task(self.subscription_monitor_loop())
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop(ws))
            try:
                await self.shared.inc("holding")
                hold_deadline = time.monotonic() + self.shared.args.hold_sec
                while time.monotonic() < hold_deadline and not self.shared.stop_event.is_set():
                    await asyncio.sleep(0.5)
                await self.shared.inc("completed")
                await self.event("worker_hold_completed", selected_channel=self.selected_channel)
            finally:
                await self.stop_background_tasks()

    async def preflight(self) -> None:
        import urllib.request

        def get_status() -> int:
            with urllib.request.urlopen(self.shared.health_url, timeout=self.shared.args.connect_timeout_sec) as response:
                return int(response.status)

        status_code = await asyncio.to_thread(get_status)
        await self.event("http_preflight", status_code=status_code, health_url=self.shared.health_url)
        if status_code >= 400:
            raise RuntimeError(f"HTTP preflight failed: {status_code}")

    async def wait_for_connect_and_channels(self, ws: WebSocketClientProtocol) -> tuple[str, str, list[dict[str, Any]]]:
        token: str | None = None
        livekit_url: str | None = None
        channels: list[dict[str, Any]] | None = None
        deadline = time.monotonic() + self.shared.args.channels_timeout_sec
        while time.monotonic() < deadline:
            timeout = max(0.1, deadline - time.monotonic())
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            msg_type = msg.get("type")
            payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
            if msg_type == "error":
                raise RuntimeError(f"backend error: {payload.get('code')}")
            if msg_type == "connecting" and payload.get("ok") is True:
                token = str(payload.get("token") or "")
                livekit_url = str(payload.get("livekit_url") or "")
                self.listener_id = str(payload.get("listener_id") or "")
                await self.event(
                    "backend_connecting_ok",
                    listener_id=self.listener_id,
                    token_length=len(token),
                    token_exp_utc=token_exp_utc(token),
                    livekit_url=livekit_url,
                )
            elif msg_type == "i18n_library":
                await self.event("i18n_library_received")
            elif msg_type == "listener_state":
                candidate = payload.get("channels")
                if isinstance(candidate, list):
                    channels = [item for item in candidate if isinstance(item, dict)]
                    await self.event("listener_state_received", channels_count=len(channels))
            if token and livekit_url and channels is not None:
                return token, livekit_url, channels
        raise TimeoutError("no channels received within channels timeout")

    def choose_channel(self, channels: list[dict[str, Any]]) -> str:
        if self.shared.args.channel_mode == "fixed":
            channel_id = self.shared.args.channel_id
            channel = next((ch for ch in channels if ch.get("channel_id") == channel_id), None)
            if channel is None:
                raise RuntimeError(f"fixed channel not found: {channel_id}")
            if channel.get("listen") is not True:
                raise RuntimeError(f"fixed channel is not listenable: {channel_id}")
            return str(channel_id)
        listenable = [str(ch.get("channel_id")) for ch in channels if ch.get("listen") is True and ch.get("channel_id")]
        if not listenable:
            raise RuntimeError("no listenable channels received")
        return random.choice(listenable)

    def _value_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if text else None

    def get_publication_name(self, publication: Any, track: Any = None) -> str | None:
        for attr in ("track_name", "trackName", "name"):
            name = self._value_or_none(getattr(publication, attr, None))
            if name:
                return name
        track_name = self._value_or_none(getattr(track, "name", None))
        if track_name:
            return track_name
        for attr in ("sid", "track_sid", "trackSid"):
            diagnostic_name = self._value_or_none(getattr(publication, attr, None))
            if diagnostic_name:
                return diagnostic_name
        return None

    def name_candidates(self, publication: Any, track: Any = None) -> dict[str, str | None]:
        return {
            "publication.track_name": self._value_or_none(getattr(publication, "track_name", None)),
            "publication.trackName": self._value_or_none(getattr(publication, "trackName", None)),
            "publication.name": self._value_or_none(getattr(publication, "name", None)),
            "track.name": self._value_or_none(getattr(track, "name", None)),
            "publication.sid": self._value_or_none(getattr(publication, "sid", None)),
            "publication.track_sid": self._value_or_none(getattr(publication, "track_sid", None)),
            "publication.trackSid": self._value_or_none(getattr(publication, "trackSid", None)),
        }

    def is_audio_publication(self, publication: Any, track: Any = None) -> bool:
        for candidate in (getattr(publication, "kind", None), getattr(track, "kind", None)):
            if candidate is None:
                continue
            enum_name = getattr(candidate, "name", None)
            if isinstance(enum_name, str) and "AUDIO" in enum_name.upper():
                return True
            text = str(candidate).lower()
            if "audio" in text:
                return True
            if rtc is not None and hasattr(rtc, "TrackKind") and candidate == getattr(rtc.TrackKind, "KIND_AUDIO", None):
                return True
        return False

    def _iter_collection_values(self, collection: Any) -> list[Any]:
        if collection is None:
            return []
        if hasattr(collection, "values"):
            return list(collection.values())
        if isinstance(collection, (list, tuple, set)):
            return list(collection)
        return []

    def iter_audio_publications(self) -> list[tuple[Any, Any]]:
        if self.room is None:
            return []
        results: list[tuple[Any, Any]] = []
        participants = self._iter_collection_values(getattr(self.room, "remote_participants", None))
        for participant in participants:
            seen_ids: set[int] = set()
            for attr in (
                "track_publications",
                "trackPublications",
                "audio_track_publications",
                "audioTrackPublications",
            ):
                for publication in self._iter_collection_values(getattr(participant, attr, None)):
                    object_id = id(publication)
                    if object_id in seen_ids:
                        continue
                    seen_ids.add(object_id)
                    track = getattr(publication, "track", None)
                    if self.is_audio_publication(publication, track):
                        results.append((participant, publication))
        return results

    async def mark_subscribed(self, track_name: str | None) -> None:
        self.subscribed = True
        if not self.subscription_counted:
            self.subscription_counted = True
            await self.shared.inc("subscribed")
        if self.subscription_lifecycle not in self.subscribed_lifecycle_logged:
            self.subscribed_lifecycle_logged.add(self.subscription_lifecycle)
            await self.event("livekit_track_subscribed", track_name=track_name, selected_channel=self.selected_channel)
        if not self.media_receive_not_confirmed_logged:
            self.media_receive_not_confirmed_logged = True
            await self.event("livekit_media_receive_not_confirmed", selected_channel=self.selected_channel)

    async def try_subscribe_selected_channel(self) -> bool:
        found_match = False
        for participant, publication in self.iter_audio_publications():
            track = getattr(publication, "track", None)
            resolved_name = self.get_publication_name(publication, track)
            publication_subscribed = bool(getattr(publication, "subscribed", False))
            publication_state = (resolved_name == self.selected_channel, publication_subscribed, track is not None)
            should_log_publication = self.shared.args.debug_publications
            should_log_publication = should_log_publication or (not self.publication_inventory_logged)
            should_log_publication = should_log_publication or (resolved_name == self.selected_channel and publication_state != self.selected_publication_state)
            if should_log_publication:
                self.publication_inventory_logged = True
                if resolved_name == self.selected_channel:
                    self.selected_publication_state = publication_state
                await self.event(
                    "livekit_publication_seen",
                    "DEBUG" if self.shared.args.debug_publications else "INFO",
                    participant_identity=getattr(participant, "identity", None),
                    participant_sid=getattr(participant, "sid", None),
                    name_candidates=self.name_candidates(publication, track),
                    resolved_name=resolved_name,
                    kind=str(getattr(publication, "kind", None) or getattr(track, "kind", None)),
                    subscribed=publication_subscribed,
                    track_present=track is not None,
                )
            if resolved_name != self.selected_channel:
                continue

            found_match = True
            action = "already_subscribed" if publication_subscribed and track is not None else "pending_track"
            if not self.subscription_requested and not publication_subscribed:
                try:
                    publication.set_subscribed(True)
                except Exception as exc:
                    await self.event(
                        "livekit_subscription_request_failed",
                        "ERROR",
                        selected_channel=self.selected_channel,
                        publication_sid=getattr(publication, "sid", None),
                        publication_name=resolved_name,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    raise
                self.subscription_requested = True
                action = "requested_subscription"
                await self.shared.inc("subscription_requested")
                await self.event(
                    "livekit_subscription_requested",
                    selected_channel=self.selected_channel,
                    publication_sid=getattr(publication, "sid", None),
                    publication_name=resolved_name,
                )

            track = getattr(publication, "track", None)
            publication_subscribed = bool(getattr(publication, "subscribed", False))
            if publication_subscribed and track is not None:
                action = "already_subscribed"
            diag_key = f"{getattr(publication, 'sid', None)}:{action}"
            if diag_key not in self.selected_publication_diagnostics_logged:
                self.selected_publication_diagnostics_logged.add(diag_key)
                await self.event(
                    "livekit_selected_publication_diagnostic",
                    selected_channel=self.selected_channel,
                    publication_name=resolved_name,
                    publication_sid=getattr(publication, "sid", None),
                    publication_kind=str(getattr(publication, "kind", None) or getattr(track, "kind", None)),
                    publication_subscribed=publication_subscribed,
                    track_present=track is not None,
                    action=action,
                )

            if track is None:
                if not self.waiting_for_track_counted:
                    self.waiting_for_track_counted = True
                    await self.shared.inc("waiting_for_track")
                now = time.monotonic()
                event_name = "livekit_subscription_pending" if self.subscription_requested else "livekit_selected_track_waiting"
                last_ts = self.last_pending_log_ts if self.subscription_requested else self.last_waiting_log_ts
                if now - last_ts >= 10.0:
                    if self.subscription_requested:
                        self.last_pending_log_ts = now
                    else:
                        self.last_waiting_log_ts = now
                    await self.event(event_name, selected_channel=self.selected_channel)
                continue

            if publication_subscribed:
                await self.mark_subscribed(resolved_name)
                return True
        if not found_match:
            if not self.waiting_for_track_counted:
                self.waiting_for_track_counted = True
                await self.shared.inc("waiting_for_track")
            now = time.monotonic()
            if now - self.last_waiting_log_ts >= 10.0:
                self.last_waiting_log_ts = now
                await self.event("livekit_selected_track_waiting", selected_channel=self.selected_channel)
        return self.subscribed

    async def subscription_monitor_loop(self) -> None:
        started = time.monotonic()
        while not self.shared.stop_event.is_set():
            await self.try_subscribe_selected_channel()
            timeout = self.shared.args.subscription_timeout_sec
            if timeout > 0 and not self.subscribed and time.monotonic() - started >= timeout:
                await self.event("livekit_subscription_timeout", "ERROR", selected_channel=self.selected_channel, timeout_sec=timeout)
                await self.shared.inc("failed")
                return
            await asyncio.sleep(1.0)

    async def connect_livekit(self, livekit_url: str, token: str) -> None:
        if rtc is None:
            raise RuntimeError("livekit.rtc is not importable; install requirements.txt")
        room = rtc.Room()
        self.room = room

        @room.on("track_published")
        def on_track_published(publication: Any, participant: Any) -> None:
            track = getattr(publication, "track", None)
            self.safe_create_task(
                self.event(
                    "livekit_track_published",
                    participant_identity=getattr(participant, "identity", None),
                    track_name=self.get_publication_name(publication, track),
                )
            )
            self.safe_create_task(self.try_subscribe_selected_channel(), "try_subscribe_selected_channel")

        @room.on("track_subscribed")
        def on_track_subscribed(track: Any, publication: Any, participant: Any) -> None:
            name = self.get_publication_name(publication, track)
            if name == self.selected_channel:
                self.safe_create_task(self.mark_subscribed(name), "track_subscribed")


        @room.on("track_subscription_failed")
        def on_track_subscription_failed(participant: Any, track_sid: Any, error: Any) -> None:
            self.safe_create_task(
                self.event(
                    "livekit_track_subscription_failed",
                    "ERROR",
                    participant_identity=getattr(participant, "identity", None),
                    participant_sid=getattr(participant, "sid", None),
                    track_sid=str(track_sid) if track_sid is not None else None,
                    error=str(error),
                    selected_channel=self.selected_channel,
                ),
                "track_subscription_failed",
            )

        @room.on("track_unpublished")
        def on_track_unpublished(publication: Any, participant: Any) -> None:
            track_name = self.get_publication_name(publication, getattr(publication, "track", None))
            if track_name == self.selected_channel:
                self.subscribed = False
                self.subscription_requested = False
                self.subscription_lifecycle += 1
                self.safe_create_task(self.event("livekit_track_unpublished", track_name=track_name), "track_unpublished")

        @room.on("participant_connected")
        def on_participant_connected(participant: Any) -> None:
            if self.shared.args.debug_publications or not self.participant_connected_logged:
                self.participant_connected_logged = True
                self.safe_create_task(
                    self.event(
                        "livekit_participant_connected",
                        "DEBUG" if self.shared.args.debug_publications else "INFO",
                        participant_identity=getattr(participant, "identity", None),
                        participant_sid=getattr(participant, "sid", None),
                    ),
                    "participant_connected",
                )
            self.safe_create_task(self.try_subscribe_selected_channel(), "try_subscribe_selected_channel")

        await room.connect(livekit_url, token, rtc.RoomOptions(auto_subscribe=False, connect_timeout=self.shared.args.connect_timeout_sec))
        await self.shared.inc("livekit_connected")
        await self.event("livekit_connected", selected_channel=self.selected_channel)
        await self.try_subscribe_selected_channel()

    async def heartbeat_loop(self, ws: WebSocketClientProtocol) -> None:
        while not self.shared.stop_event.is_set():
            await ws.send(json.dumps(self.envelope("heartbeat", {
                "client_role": "listener",
                "selected_channel": self.selected_channel,
                "playback_state": "PLAYING",
            })))
            await self.shared.inc("playing_heartbeat_sent")
            await self.event("listener_heartbeat_sent", selected_channel=self.selected_channel)
            await asyncio.sleep(self.shared.args.heartbeat_sec)

    async def close(self) -> None:
        if self.closed:
            return
        self.closing = True
        await self.stop_background_tasks()
        if self.room is not None:
            with contextlib.suppress(Exception):
                result = self.room.disconnect()
                if hasattr(result, "__await__"):
                    await result
            await asyncio.sleep(0.1)
            self.room = None
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.close(code=1000)
            self.ws = None
        self.closed = True

def run_validity(args: Args, snap: dict[str, int]) -> str:
    fatal_errors = snap.get("failed", 0) > 0 and snap.get("subscribed", 0) == 0
    if snap.get("subscribed", 0) == 0:
        return "INVALID_RUN"
    if not fatal_errors and (snap.get("subscribed") == snap.get("workers_started") or snap.get("subscribed") == snap.get("livekit_connected")):
        return "VALID_RUN"
    return "PARTIAL_RUN"


async def write_final_summary(shared: SharedState, csv_summary: Path) -> dict[str, Any]:
    snap = await shared.snapshot()
    summary = {
        "workers_target": shared.args.listeners,
        **snap,
        "run_validity": run_validity(shared.args, snap),
    }
    with csv_summary.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_local", *summary.keys()])
        writer.writeheader()
        writer.writerow({"ts_local": local_ts(), **summary})
    if shared.jsonl_path:
        payload = {"ts_local": local_ts(), "ts_utc": utc_iso(), "level": "INFO", "event": "loader_final_summary", "runner_id": shared.args.runner_id, "loader_run_id": shared.args.loader_run_id, **summary}
        with shared.jsonl_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    print("FINAL " + " ".join(f"{k}={v}" for k, v in summary.items()), flush=True)
    return summary


async def status_loop(shared: SharedState) -> None:
    while not shared.stop_event.is_set():
        snap = await shared.snapshot()
        print(
            f"[{local_ts()}] "
            + " ".join(f"{k}={v}" for k, v in snap.items()),
            flush=True,
        )
        await asyncio.sleep(5)


def parse_args() -> Args:
    parser = argparse.ArgumentParser(description="BYOD Stage XI Protocol/engine Listener Loader")
    parser.add_argument("--server", required=True, help="VPS server URL, for example http://80.78.244.210")
    parser.add_argument("--listeners", required=True, type=int)
    parser.add_argument("--ramp-mode", required=True, choices=["linear", "burst"])
    parser.add_argument("--listener-every-sec", type=float, default=1.0)
    parser.add_argument("--channel-mode", required=True, choices=["random", "fixed"])
    parser.add_argument("--channel-id")
    parser.add_argument("--hold-sec", required=True, type=float)
    parser.add_argument("--runner-id", required=True)
    parser.add_argument("--heartbeat-sec", type=float, default=10.0)
    parser.add_argument("--connect-timeout-sec", type=float, default=30.0)
    parser.add_argument("--channels-timeout-sec", type=float, default=60.0)
    parser.add_argument("--reconnect", nargs="?", const="true", default="false", type=parse_bool)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--loader-run-id", help="Unique run id; default is <runner_id>-<YYYYMMDD-HHMMSS>-pid<PID>")
    parser.add_argument("--debug-publications", action="store_true", help="Write verbose LiveKit publication/participant debug events")
    parser.add_argument("--subscription-timeout-sec", type=float, default=0.0, help="0 means wait indefinitely")
    ns = parser.parse_args()
    if ns.listeners < 1:
        parser.error("--listeners must be >= 1")
    if ns.hold_sec < 0:
        parser.error("--hold-sec must be >= 0")
    if ns.listener_every_sec < 0:
        parser.error("--listener-every-sec must be >= 0")
    if ns.channel_mode == "fixed" and not ns.channel_id:
        parser.error("--channel-id is required when --channel-mode fixed")
    if not ns.runner_id.strip():
        parser.error("--runner-id is mandatory and cannot be empty")
    if ns.subscription_timeout_sec < 0:
        parser.error("--subscription-timeout-sec must be >= 0")
    ns.runner_id = ns.runner_id.strip()
    if not ns.loader_run_id:
        ns.loader_run_id = f"{ns.runner_id}-{datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-pid{os.getpid()}"
    return Args(**vars(ns))


def setup_logging(level: str, loader_run_id: str) -> tuple[Path, Path, Path]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in loader_run_id)
    human_log = LOG_DIR / f"byod_loader_{safe_run_id}.log"
    jsonl_log = LOG_DIR / f"byod_loader_{safe_run_id}.jsonl"
    csv_summary = LOG_DIR / f"byod_loader_{safe_run_id}.csv"
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(human_log, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return human_log, jsonl_log, csv_summary


async def main_async() -> int:
    args = parse_args()
    backend_ws_url = build_ws_url(args.server)
    health_url = build_health_url(args.server)
    human_log, jsonl_log, csv_summary = setup_logging(args.log_level, args.loader_run_id)
    stop_event = asyncio.Event()
    shared = SharedState(args=args, backend_ws_url=backend_ws_url, health_url=health_url, stop_event=stop_event, jsonl_path=jsonl_log, csv_path=csv_summary)

    print("BYOD Stage XI Protocol/engine Listener Loader")
    print(f"server={args.server}")
    print(f"backend_ws_url={backend_ws_url}")
    print(f"listeners_target={args.listeners}")
    print(f"ramp_mode={args.ramp_mode}")
    print(f"listener_every_sec={args.listener_every_sec}")
    print(f"channel_mode={args.channel_mode} channel_id={args.channel_id or '-'}")
    print(f"hold_sec={args.hold_sec}")
    print(f"runner_id={args.runner_id}")
    print(f"loader_run_id={args.loader_run_id}")
    print(f"python={sys.version.split()[0]}")
    print(f"log_path={LOG_DIR}")
    print("No PIN is required. Tokens are not logged.")

    loop = asyncio.get_running_loop()
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop_event.set)

    status = asyncio.create_task(status_loop(shared))
    workers: list[asyncio.Task[None]] = []
    try:
        for idx in range(1, args.listeners + 1):
            if stop_event.is_set():
                break
            task = asyncio.create_task(Worker(idx, shared).run())
            workers.append(task)
            if args.ramp_mode == "linear" and idx < args.listeners:
                await asyncio.sleep(args.listener_every_sec)
        if workers:
            wait_all = asyncio.gather(*workers, return_exceptions=True)
            stop_wait = asyncio.create_task(stop_event.wait())
            done, _ = await asyncio.wait({wait_all, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
            if stop_wait in done and not wait_all.done():
                await asyncio.wait(workers, timeout=5.0)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        status.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await status
        done, pending = await asyncio.wait(workers, timeout=5.0) if workers else (set(), set())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await write_final_summary(shared, csv_summary)
        print(f"Logs: {human_log} {jsonl_log} {csv_summary}")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
