import asyncio
import time
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import count
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as livekit_api

PIN = "123456"
ROOM_NAME = "test room"
ROOM_STATUS = "OPENED"
STATUS_TEXT = ""
LIVEKIT_URL = "ws://127.0.0.1:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "secret"
JWT_LIFETIME_SECONDS = 2 * 60 * 60
HEARTBEAT_TIMEOUT_SECONDS = 30
SCHEMA_VERSION = 1

I18N_LIBRARY = {
    "room_name_i18n": {"en": ROOM_NAME},
    "custom_status_text_blocked_i18n": {"en": "Room is temporarily blocked"},
    "custom_status_text_closed_i18n": {"en": "Room is closed"},
}

CHANNELS = [
    {"channel_id": "channel_0", "channel_label": "FLOOR", "listen": False, "owner": None},
    {"channel_id": "channel_1", "channel_label": "RUS", "listen": True, "owner": None},
    {"channel_id": "channel_2", "channel_label": "ENG", "listen": True, "owner": None},
    {"channel_id": "channel_3", "channel_label": "ARA", "listen": True, "owner": None},
    {"channel_id": "channel_4", "channel_label": "FRE", "listen": True, "owner": None},
    {"channel_id": "channel_5", "channel_label": "CHI", "listen": True, "owner": None},
    {"channel_id": "channel_6", "channel_label": "TUR", "listen": True, "owner": None},
    {"channel_id": "channel_7", "channel_label": "SPA", "listen": True, "owner": None},
    {"channel_id": "channel_8", "channel_label": "GER", "listen": True, "owner": None},
    {"channel_id": "channel_9", "channel_label": "POR", "listen": True, "owner": None},
    {"channel_id": "channel_10", "channel_label": "ITA", "listen": True, "owner": None},
    {"channel_id": "channel_11", "channel_label": "JPN", "listen": True, "owner": None},
    {"channel_id": "channel_12", "channel_label": "KOR", "listen": True, "owner": None},
    {"channel_id": "channel_13", "channel_label": "HIN", "listen": True, "owner": None},
    {"channel_id": "channel_14", "channel_label": "UKR", "listen": True, "owner": None},
    {"channel_id": "channel_15", "channel_label": "POL", "listen": True, "owner": None},
    {"channel_id": "channel_16", "channel_label": "NLD", "listen": True, "owner": None},
    {"channel_id": "channel_17", "channel_label": "SWE", "listen": True, "owner": None},
    {"channel_id": "channel_18", "channel_label": "NOR", "listen": True, "owner": None},
    {"channel_id": "channel_19", "channel_label": "DAN", "listen": True, "owner": None},
    {"channel_id": "channel_20", "channel_label": "FIN", "listen": True, "owner": None},
    {"channel_id": "channel_21", "channel_label": "CES", "listen": True, "owner": None},
    {"channel_id": "channel_22", "channel_label": "SLK", "listen": True, "owner": None},
    {"channel_id": "channel_23", "channel_label": "RON", "listen": True, "owner": None},
    {"channel_id": "channel_24", "channel_label": "HUN", "listen": True, "owner": None},
    {"channel_id": "channel_25", "channel_label": "ELL", "listen": True, "owner": None},
    {"channel_id": "channel_26", "channel_label": "HEB", "listen": True, "owner": None},
    {"channel_id": "channel_27", "channel_label": "VIE", "listen": True, "owner": None},
    {"channel_id": "channel_28", "channel_label": "THA", "listen": True, "owner": None},
    {"channel_id": "channel_29", "channel_label": "IND", "listen": True, "owner": None},
    {"channel_id": "channel_30", "channel_label": "Reserve 1", "listen": False, "owner": None},
    {"channel_id": "channel_31", "channel_label": "Reserve 2", "listen": False, "owner": None},
]


@dataclass
class PublisherSession:
    publisher_id: str
    hostname: str
    websocket: WebSocket
    connected_at_ts: float
    last_seen_ts: float
    online: bool = True


@dataclass
class ServerState:
    channels: list[dict[str, Any]] = field(default_factory=lambda: [dict(ch) for ch in CHANNELS])
    publishers: dict[str, PublisherSession] = field(default_factory=dict)
    listeners: set[WebSocket] = field(default_factory=set)
    publisher_counter: int = 0
    listener_counter: int = 0


app = FastAPI(title="BYOD Backend MVP Stage VII - implementation 1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = ServerState()
state_lock = asyncio.Lock()
request_counter = count(1)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def now_ts() -> int:
    return int(time.time())


def next_request_id(prefix: str = "server") -> str:
    return f"{prefix}-{next(request_counter)}"


def make_envelope(msg_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return {
        "type": msg_type,
        "schema_version": SCHEMA_VERSION,
        "ts": now_ts(),
        "request_id": request_id or next_request_id(msg_type),
        "payload": payload,
    }


def build_publisher_state_snapshot(channels: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "room_name": ROOM_NAME,
        "room_status": ROOM_STATUS,
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


def build_listener_state_snapshot(channels: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "room_status": ROOM_STATUS,
        "status_custom_text": STATUS_TEXT,
        "channels": [
            {
                "channel_id": channel["channel_id"],
                "channel_label": channel["channel_label"],
                "listen": channel.get("listen", True),
            }
            for channel in channels
        ],
    }


def build_legacy_state_snapshot(channels: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "room_name": ROOM_NAME,
        "room_status": ROOM_STATUS,
        "status_custom_text": STATUS_TEXT,
        "channels": channels,
    }


def get_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload")
    if isinstance(payload, dict):
        return payload
    return message


def validate_message_envelope(message: dict[str, Any]) -> str | None:
    if "payload" not in message:
        return None
    if not isinstance(message.get("type"), str):
        return "INVALID_TYPE"
    if message.get("schema_version") != SCHEMA_VERSION:
        return "UNSUPPORTED_SCHEMA_VERSION"
    if not isinstance(message.get("request_id"), str):
        return "INVALID_REQUEST_ID"
    if not isinstance(message.get("payload"), dict):
        return "INVALID_PAYLOAD"
    return None


async def send_json_safe(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


async def send_error(ws: WebSocket, code: str, request_id: str | None = None) -> None:
    print(f"[backend] send_error code={code}")
    await send_json_safe(ws, {"type": "error", "code": code})
    await send_json_safe(ws, make_envelope("error", {"ok": False, "code": code}, request_id=request_id))


def find_channel(channels: list[dict[str, Any]], channel_id: str | None) -> dict[str, Any] | None:
    for channel in channels:
        if channel["channel_id"] == channel_id:
            return channel
    return None


def get_broadcast_snapshot() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[PublisherSession], list[WebSocket]]:
    channels_snapshot = [dict(ch) for ch in state.channels]
    publisher_state = build_publisher_state_snapshot(channels_snapshot)
    listener_state = build_listener_state_snapshot(channels_snapshot)
    legacy_state = build_legacy_state_snapshot(channels_snapshot)
    return (
        publisher_state,
        listener_state,
        legacy_state,
        list(state.publishers.values()),
        list(state.listeners),
    )


async def broadcast_states() -> None:
    async with state_lock:
        publisher_state, listener_state, legacy_state, publishers, listeners = get_broadcast_snapshot()

    publisher_payload = make_envelope("publisher_state", publisher_state)
    listener_payload = make_envelope("listener_state", listener_state)
    legacy_payload = {"type": "state", "state": legacy_state}

    dead_publishers: list[str] = []
    for session in publishers:
        ok_new = await send_json_safe(session.websocket, publisher_payload)
        ok_legacy = await send_json_safe(session.websocket, legacy_payload)
        if not ok_new and not ok_legacy:
            dead_publishers.append(session.publisher_id)

    dead_listeners: list[WebSocket] = []
    for ws in listeners:
        ok_new = await send_json_safe(ws, listener_payload)
        ok_legacy = await send_json_safe(ws, legacy_payload)
        if not ok_new and not ok_legacy:
            dead_listeners.append(ws)

    if not dead_publishers and not dead_listeners:
        return

    async with state_lock:
        for publisher_id in dead_publishers:
            await drop_publisher_locked(publisher_id)
        for ws in dead_listeners:
            state.listeners.discard(ws)


async def send_connect_success(
    websocket: WebSocket,
    client_role: str,
    token: str,
    livekit_url: str,
    request_id: str,
    publisher_id: str | None = None,
    listener_id: str | None = None,
) -> None:
    async with state_lock:
        channels_snapshot = [dict(ch) for ch in state.channels]

    publisher_state = build_publisher_state_snapshot(channels_snapshot)
    listener_state = build_listener_state_snapshot(channels_snapshot)
    legacy_state = build_legacy_state_snapshot(channels_snapshot)

    if client_role == "publisher":
        await websocket.send_json(
            {
                "type": "connected",
                "publisher_id": publisher_id,
                "token": token,
                "livekit_url": livekit_url,
                "state": legacy_state,
            }
        )
        await websocket.send_json(
            make_envelope(
                "connecting",
                {
                    "ok": True,
                    "client_role": "publisher",
                    "publisher_id": publisher_id,
                    "token": token,
                    "livekit_url": livekit_url,
                    "room_name": ROOM_NAME,
                    "room_status": ROOM_STATUS,
                },
                request_id=request_id,
            )
        )
        await websocket.send_json(make_envelope("i18n_library", I18N_LIBRARY))
        await websocket.send_json(make_envelope("publisher_state", publisher_state))
        return

    await websocket.send_json(
        {
            "type": "connected",
            "listener_id": listener_id,
            "token": token,
            "livekit_url": livekit_url,
            "state": legacy_state,
        }
    )
    await websocket.send_json(
        make_envelope(
            "connecting",
            {
                "ok": True,
                "client_role": "listener",
                "listener_id": listener_id,
                "token": token,
                "livekit_url": livekit_url,
                "room_status": ROOM_STATUS,
            },
            request_id=request_id,
        )
    )
    await websocket.send_json(make_envelope("i18n_library", I18N_LIBRARY))
    await websocket.send_json(make_envelope("listener_state", listener_state))


def create_livekit_token(identity: str) -> str:
    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_grants(livekit_api.VideoGrants(room_join=True, room=ROOM_NAME))
        .with_ttl(timedelta(seconds=JWT_LIFETIME_SECONDS))
    )
    return token.to_jwt()


async def drop_publisher_locked(publisher_id: str) -> None:
    session = state.publishers.get(publisher_id)
    if session is None:
        return

    session.online = False
    print(f"[backend] drop_publisher publisher_id={publisher_id}")
    for channel in state.channels:
        if channel["owner"] == publisher_id:
            channel["owner"] = None
            channel["off_air_ts"] = now_ts()

    state.publishers.pop(publisher_id, None)


@app.websocket("/ws/publisher")
async def publisher_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[backend] publisher websocket accepted")
    publisher_id: str | None = None

    try:
        while True:
            message = await websocket.receive_json()
            schema_error = validate_message_envelope(message)
            if schema_error is not None:
                await send_error(websocket, "SCHEMA_VALIDATION_ERROR")
                continue

            payload = get_payload(message)
            msg_type = message.get("type")
            request_id = message.get("request_id") if isinstance(message.get("request_id"), str) else None

            if msg_type == "connecting":
                pin = str(payload.get("pin") or "")
                hostname = str(payload.get("hostname") or "publisher-host")
                if pin != PIN:
                    print(f"[backend] invalid pin from hostname={hostname}")
                    await send_error(websocket, "INVALID_PIN", request_id=request_id)
                    continue

                async with state_lock:
                    publisher_id = f"{hostname}_{state.publisher_counter}"
                    state.publisher_counter += 1
                    state.publishers[publisher_id] = PublisherSession(
                        publisher_id=publisher_id,
                        hostname=hostname,
                        websocket=websocket,
                        connected_at_ts=float(now_ts()),
                        last_seen_ts=float(now_ts()),
                    )
                    print(f"[backend] publisher connected publisher_id={publisher_id}")

                await send_connect_success(
                    websocket=websocket,
                    client_role="publisher",
                    publisher_id=publisher_id,
                    token=create_livekit_token(publisher_id),
                    livekit_url=LIVEKIT_URL,
                    request_id=request_id or next_request_id("pub-connect"),
                )
                await broadcast_states()
                continue

            if publisher_id is None:
                await send_error(websocket, "NOT_CONNECTED", request_id=request_id)
                continue

            if msg_type == "heartbeat":
                async with state_lock:
                    session = state.publishers.get(publisher_id)
                    if session:
                        session.last_seen_ts = float(now_ts())
                continue

            if msg_type == "on_air":
                channel_id = payload.get("channel_id")
                rejected_owner: str | None = None

                async with state_lock:
                    channel = find_channel(state.channels, channel_id)
                    if channel is None:
                        await send_error(websocket, "UNKNOWN_CHANNEL", request_id=request_id)
                        continue

                    owner = channel["owner"]
                    if owner is None:
                        channel["owner"] = publisher_id
                        channel["on_air_ts"] = now_ts()
                        print(f"[backend] ON_AIR granted channel={channel_id} owner={publisher_id}")
                    elif owner == publisher_id:
                        channel["request_on_air_ts"] = payload.get("request_on_air_ts")
                        print(f"[backend] ON_AIR duplicate ignored channel={channel_id} owner={publisher_id}")
                    else:
                        rejected_owner = owner
                        print(
                            f"[backend] ON_AIR rejected channel={channel_id} "
                            f"owner={owner} requester={publisher_id}"
                        )

                if rejected_owner is not None:
                    await send_json_safe(
                        websocket,
                        {"type": "on_air_rejected", "channel_id": channel_id, "owner": rejected_owner},
                    )
                    await send_error(websocket, "OWNER_MISMATCH", request_id=request_id)
                await broadcast_states()
                continue

            if msg_type == "stop":
                channel_id = payload.get("channel_id")
                async with state_lock:
                    channel = find_channel(state.channels, channel_id)
                    if channel is None:
                        await send_error(websocket, "UNKNOWN_CHANNEL", request_id=request_id)
                        continue

                    owner = channel["owner"]
                    if owner == publisher_id:
                        channel["owner"] = None
                        channel["off_air_ts"] = now_ts()
                        print(f"[backend] STOP owner cleared channel={channel_id} owner={publisher_id}")
                    elif owner is None:
                        channel["request_off_air_ts"] = payload.get("request_off_air_ts")
                        print(f"[backend] STOP duplicate ignored channel={channel_id}")

                await broadcast_states()
                continue

            await send_error(websocket, "UNKNOWN_MESSAGE_TYPE", request_id=request_id)

    except WebSocketDisconnect:
        print("[backend] publisher websocket disconnected")
    finally:
        async with state_lock:
            if publisher_id:
                await drop_publisher_locked(publisher_id)
        await broadcast_states()


@app.websocket("/ws/listener")
async def listener_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[backend] listener websocket accepted")
    try:
        first = await websocket.receive_json()
        schema_error = validate_message_envelope(first)
        if schema_error is not None or first.get("type") != "connecting":
            print("[backend] listener invalid flow")
            await send_error(websocket, "INVALID_FLOW")
            return

        request_id = first.get("request_id") if isinstance(first.get("request_id"), str) else next_request_id("lst-connect")

        async with state_lock:
            listener_id = f"listener_{state.listener_counter}"
            state.listener_counter += 1
            state.listeners.add(websocket)
            print(f"[backend] listener connected listener_id={listener_id}")

        await send_connect_success(
            websocket=websocket,
            client_role="listener",
            listener_id=listener_id,
            token=create_livekit_token(listener_id),
            livekit_url=LIVEKIT_URL,
            request_id=request_id,
        )

        while True:
            msg = await websocket.receive_json()
            schema_error = validate_message_envelope(msg)
            if schema_error is not None:
                await send_error(websocket, "SCHEMA_VALIDATION_ERROR")
                continue
            if msg.get("type") == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack", "ts": now_ts()})

    except WebSocketDisconnect:
        print("[backend] listener websocket disconnected")
    finally:
        async with state_lock:
            state.listeners.discard(websocket)


async def monitor_timeouts() -> None:
    while True:
        await asyncio.sleep(1)
        expired: list[str] = []
        async with state_lock:
            now = float(now_ts())
            for publisher_id, session in state.publishers.items():
                if now - session.last_seen_ts > HEARTBEAT_TIMEOUT_SECONDS:
                    expired.append(publisher_id)

            for publisher_id in expired:
                await drop_publisher_locked(publisher_id)
                print(f"[backend] heartbeat timeout publisher_id={publisher_id}")

        if expired:
            await broadcast_states()


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(monitor_timeouts())
