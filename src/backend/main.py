from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as livekit_api

from .csv_import import parse_room_csv
from .models import ChannelState, ListenerSession, PublisherSession
from .persistence import JsonPersistence
from .protocol import (
    ERROR_CHANNEL_NOT_FOUND,
    ERROR_INVALID_PIN,
    ERROR_OWNER_MISMATCH,
    ERROR_RATE_LIMITED,
    ProtocolValidationError,
    make_envelope,
    parse_client_message,
    validate_connecting_payload,
)

LIVEKIT_URL = "ws://127.0.0.1:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "secret"
JWT_LIFETIME_SECONDS = 2 * 60 * 60
PUBLISHER_HEARTBEAT_TIMEOUT_SECONDS = 30

DEFAULT_CHANNELS = [
    ChannelState(channel_id="channel_0", channel_label="FLOOR", listen=False),
    ChannelState(channel_id="channel_1", channel_label="RUS", listen=True),
]


app = FastAPI(title="BYOD Backend Stage VII - implementation 1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

persistence = JsonPersistence(root="backend_data")
state = persistence.load()
if not state.channels:
    state.channels = DEFAULT_CHANNELS

state_lock = asyncio.Lock()
connection_history: deque[float] = deque()


def now_ts() -> float:
    return time.time()


def create_livekit_token(identity: str) -> str:
    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_grants(livekit_api.VideoGrants(room_join=True, room=state.room_name))
        .with_ttl(timedelta(seconds=JWT_LIFETIME_SECONDS))
    )
    return token.to_jwt()


def build_publisher_state_payload() -> dict[str, Any]:
    return {
        "room_name": state.room_name,
        "room_status": state.room_status,
        "channels": [ch.to_publisher_dict() for ch in state.channels],
    }


def build_listener_state_payload() -> dict[str, Any]:
    return {
        "room_status": state.room_status,
        "channels": [ch.to_listener_dict() for ch in state.channels],
    }


def build_i18n_payload() -> dict[str, Any]:
    return {
        "library_version": 1,
        "room_name_i18n": dict(state.room_name_i18n),
        "custom_status_text_blocked_i18n": state.effective_blocked_i18n(),
        "custom_status_text_closed_i18n": state.effective_closed_i18n(),
    }


def snapshot_sessions() -> tuple[list[WebSocket], list[WebSocket]]:
    publisher_sockets = [session.websocket for session in state.publishers.values()]
    listener_sockets = [session.websocket for session in state.listeners.values()]
    return publisher_sockets, listener_sockets


async def send_json_safe(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


async def broadcast_states() -> None:
    async with state_lock:
        publisher_payload = make_envelope("publisher_state", build_publisher_state_payload())
        listener_payload = make_envelope("listener_state", build_listener_state_payload())
        publishers, listeners = snapshot_sessions()

    for ws in publishers:
        await send_json_safe(ws, publisher_payload)
    for ws in listeners:
        await send_json_safe(ws, listener_payload)


async def broadcast_i18n() -> None:
    async with state_lock:
        payload = make_envelope("i18n_library", build_i18n_payload())
        publishers, listeners = snapshot_sessions()
    for ws in [*publishers, *listeners]:
        await send_json_safe(ws, payload)


def find_channel(channel_id: str) -> ChannelState | None:
    for channel in state.channels:
        if channel.channel_id == channel_id:
            return channel
    return None


def check_connection_rate_limit() -> bool:
    now = now_ts()
    while connection_history and now - connection_history[0] > 1:
        connection_history.popleft()

    if len(connection_history) >= state.max_new_connections_per_sec:
        return False

    connection_history.append(now)
    return True


async def send_error(ws: WebSocket, code: str, message: str, request_id: str) -> None:
    await ws.send_json(make_envelope("error", {"code": code, "message": message, "retryable": False}, request_id))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/admin/import_csv")
async def import_csv(file: UploadFile) -> dict[str, Any]:
    content = (await file.read()).decode("utf-8")
    result = parse_room_csv(content)
    if not result.ok:
        raise HTTPException(status_code=400, detail={"ok": False, "errors": result.errors})

    async with state_lock:
        state.channels = [
            ChannelState(channel_id=ch["channel_id"], channel_label=ch["channel_label"], listen=ch["listen"])
            for ch in result.channels
        ]
        if result.room_name:
            state.room_name = result.room_name
            state.room_name_i18n["en"] = result.room_name
        if result.pin:
            state.pin = result.pin
        state.target_capacity = int(result.target_capacity or state.target_capacity)
        state.max_active_listeners = int(state.target_capacity * 1.05)
        state.max_new_connections_per_sec = max(1, int(state.target_capacity / 15))
        persistence.save_room_config(state)
        persistence.save_runtime(state)

    await broadcast_states()
    return {"ok": True, "channels": len(state.channels)}


@app.post("/admin/command")
async def admin_command(cmd: dict[str, Any]) -> dict[str, Any]:
    command = cmd.get("command")
    args = cmd.get("args", {})

    async with state_lock:
        if command == "room_status":
            status = args.get("value")
            if status not in {"OPENED", "BLOCKED", "CLOSED"}:
                raise HTTPException(status_code=400, detail="invalid room_status")
            state.room_status = status
        elif command == "channel_label":
            channel = find_channel(str(args.get("channel_id")))
            if not channel:
                raise HTTPException(status_code=404, detail="channel not found")
            channel.channel_label = str(args.get("value", ""))
            persistence.save_room_config(state)
        elif command == "listen":
            channel = find_channel(str(args.get("channel_id")))
            if not channel:
                raise HTTPException(status_code=404, detail="channel not found")
            channel.listen = bool(args.get("value"))
            persistence.save_room_config(state)
        elif command == "recording":
            pass
        elif command == "override":
            target = args.get("target")
            value = args.get("value")
            if target not in {"blocked", "closed"}:
                raise HTTPException(status_code=400, detail="invalid override target")
            state.overrides[target] = value
        elif command == "override_reset":
            target = args.get("target")
            if target not in {"blocked", "closed"}:
                raise HTTPException(status_code=400, detail="invalid override target")
            state.overrides[target] = None
        else:
            raise HTTPException(status_code=400, detail="unknown command")

        persistence.save_runtime(state)

    if command in {"override", "override_reset"}:
        await broadcast_i18n()
    await broadcast_states()
    return {"ok": True}


@app.websocket("/ws/publisher")
async def publisher_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    publisher_id: str | None = None
    try:
        while True:
            raw = await websocket.receive_json()
            try:
                message = parse_client_message(raw)
            except ProtocolValidationError as exc:
                request_id = raw.get("request_id", "unknown") if isinstance(raw, dict) else "unknown"
                await send_error(websocket, "SCHEMA_VALIDATION_ERROR", str(exc), request_id)
                continue

            msg_type = message["type"]
            request_id = message["request_id"]
            payload = message["payload"]

            if msg_type == "connecting":
                try:
                    validate_connecting_payload(payload, expected_role="publisher")
                except ProtocolValidationError as exc:
                    await send_error(websocket, "SCHEMA_VALIDATION_ERROR", str(exc), request_id)
                    continue

                if payload["pin"] != state.pin:
                    await send_error(websocket, ERROR_INVALID_PIN, "invalid pin", request_id)
                    continue

                if not check_connection_rate_limit():
                    await send_error(websocket, ERROR_RATE_LIMITED, "connection rate limit reached", request_id)
                    continue

                async with state_lock:
                    hostname = payload["hostname"]
                    publisher_id = f"{hostname}_{state.publisher_counter}"
                    state.publisher_counter += 1
                    state.publishers[publisher_id] = PublisherSession(
                        publisher_id=publisher_id,
                        hostname=hostname,
                        websocket=websocket,
                        connected_at_ts=now_ts(),
                        last_seen_ts=now_ts(),
                        ip=str(websocket.client),
                    )

                    response = make_envelope(
                        "connecting",
                        {
                            "ok": True,
                            "client_role": "publisher",
                            "publisher_id": publisher_id,
                            "token": create_livekit_token(publisher_id),
                            "livekit_url": LIVEKIT_URL,
                            "room_name": state.room_name,
                            "room_status": state.room_status,
                        },
                        request_id,
                    )
                    i18n_payload = make_envelope("i18n_library", build_i18n_payload())
                    publisher_state_payload = make_envelope("publisher_state", build_publisher_state_payload())

                await websocket.send_json(response)
                await websocket.send_json(i18n_payload)
                await websocket.send_json(publisher_state_payload)
                await broadcast_states()
                continue

            if publisher_id is None:
                await send_error(websocket, "UNAUTHORIZED", "connect first", request_id)
                continue

            if msg_type == "heartbeat":
                async with state_lock:
                    session = state.publishers.get(publisher_id)
                    if session:
                        session.last_seen_ts = now_ts()
                continue

            if msg_type == "on_air":
                channel_id = payload.get("channel_id")
                async with state_lock:
                    channel = find_channel(str(channel_id))
                    if channel is None:
                        await send_error(websocket, ERROR_CHANNEL_NOT_FOUND, "channel not found", request_id)
                        continue

                    if channel.owner is None:
                        channel.owner = publisher_id
                    elif channel.owner != publisher_id:
                        await send_error(websocket, ERROR_OWNER_MISMATCH, "owner is another publisher", request_id)
                    persistence.save_runtime(state)
                await broadcast_states()
                continue

            if msg_type == "stop":
                channel_id = payload.get("channel_id")
                async with state_lock:
                    channel = find_channel(str(channel_id))
                    if channel is None:
                        await send_error(websocket, ERROR_CHANNEL_NOT_FOUND, "channel not found", request_id)
                        continue
                    if channel.owner == publisher_id:
                        channel.owner = None
                    persistence.save_runtime(state)
                await broadcast_states()
                continue

    except WebSocketDisconnect:
        pass
    finally:
        async with state_lock:
            if publisher_id and publisher_id in state.publishers:
                for ch in state.channels:
                    if ch.owner == publisher_id:
                        ch.owner = None
                state.publishers.pop(publisher_id, None)
                persistence.save_runtime(state)
        await broadcast_states()


@app.websocket("/ws/listener")
async def listener_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    listener_id: str | None = None
    try:
        first_raw = await websocket.receive_json()
        first = parse_client_message(first_raw)
        request_id = first["request_id"]
        if first["type"] != "connecting":
            await send_error(websocket, "SCHEMA_VALIDATION_ERROR", "first message must be connecting", request_id)
            return

        validate_connecting_payload(first["payload"], expected_role="listener")

        if not check_connection_rate_limit():
            await send_error(websocket, ERROR_RATE_LIMITED, "connection rate limit reached", request_id)
            return

        async with state_lock:
            if len(state.listeners) >= state.max_active_listeners:
                await send_error(websocket, ERROR_RATE_LIMITED, "max active listeners reached", request_id)
                return

            listener_id = f"listener_{state.listener_counter}"
            state.listener_counter += 1
            state.listeners[listener_id] = ListenerSession(
                listener_id=listener_id,
                websocket=websocket,
                connected_at_ts=now_ts(),
                last_seen_ts=now_ts(),
                ip=str(websocket.client),
            )

            response = make_envelope(
                "connecting",
                {
                    "ok": True,
                    "client_role": "listener",
                    "listener_id": listener_id,
                    "token": create_livekit_token(listener_id),
                    "livekit_url": LIVEKIT_URL,
                    "room_status": state.room_status,
                },
                request_id,
            )
            i18n_payload = make_envelope("i18n_library", build_i18n_payload())
            listener_state_payload = make_envelope("listener_state", build_listener_state_payload())

        await websocket.send_json(response)
        await websocket.send_json(i18n_payload)
        await websocket.send_json(listener_state_payload)

        while True:
            raw = await websocket.receive_json()
            message = parse_client_message(raw)
            if message["type"] == "heartbeat":
                async with state_lock:
                    session = state.listeners.get(listener_id)
                    if session:
                        session.last_seen_ts = now_ts()

    except WebSocketDisconnect:
        pass
    finally:
        async with state_lock:
            if listener_id and listener_id in state.listeners:
                state.listeners.pop(listener_id, None)
