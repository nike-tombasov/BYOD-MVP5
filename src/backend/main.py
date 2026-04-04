import asyncio
import time
from datetime import timedelta
from dataclasses import dataclass, field
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
JWT_LIFETIME_SECONDS = 5 * 60 * 60
HEARTBEAT_TIMEOUT_SECONDS = 15

CHANNELS = [
    {"channel_id": "channel_0", "channel_label": "floor", "listen": True, "owner": None},
    {"channel_id": "channel_1", "channel_label": "rus", "listen": True, "owner": None},
    {"channel_id": "channel_2", "channel_label": "eng", "listen": True, "owner": None},
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


app = FastAPI(title="BYOD Backend MVP Step 1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = ServerState()
state_lock = asyncio.Lock()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def now_ts() -> float:
    return time.time()


def build_state_payload() -> dict[str, Any]:
    return {
        "room_name": ROOM_NAME,
        "room_status": ROOM_STATUS,
        "status_custom_text": STATUS_TEXT,
        "channels": state.channels,
    }


def create_livekit_token(identity: str) -> str:
    token = (
        livekit_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_grants(livekit_api.VideoGrants(room_join=True, room=ROOM_NAME))
        .with_ttl(timedelta(seconds=JWT_LIFETIME_SECONDS))
    )
    return token.to_jwt()


async def send_json_safe(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


async def broadcast_state() -> None:
    payload = {"type": "state", "state": build_state_payload()}
    print("[backend] broadcast_state")

    dead_publishers: list[str] = []
    for publisher_id, session in state.publishers.items():
        ok = await send_json_safe(session.websocket, payload)
        if not ok:
            dead_publishers.append(publisher_id)

    dead_listeners: list[WebSocket] = []
    for ws in state.listeners:
        ok = await send_json_safe(ws, payload)
        if not ok:
            dead_listeners.append(ws)

    for publisher_id in dead_publishers:
        await drop_publisher(publisher_id)

    for ws in dead_listeners:
        state.listeners.discard(ws)


async def drop_publisher(publisher_id: str) -> None:
    session = state.publishers.get(publisher_id)
    if session is None:
        return

    session.online = False
    print(f"[backend] drop_publisher publisher_id={publisher_id}")
    for channel in state.channels:
        if channel["owner"] == publisher_id:
            channel["owner"] = None

    state.publishers.pop(publisher_id, None)


def find_channel(channel_id: str) -> dict[str, Any] | None:
    for channel in state.channels:
        if channel["channel_id"] == channel_id:
            return channel
    return None


@app.websocket("/ws/publisher")
async def publisher_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[backend] publisher websocket accepted")
    publisher_id: str | None = None

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "connecting":
                pin = message.get("pin")
                hostname = str(message.get("hostname") or "publisher-host")
                if pin != PIN:
                    print(f"[backend] invalid pin from hostname={hostname}")
                    await websocket.send_json({"type": "error", "code": "INVALID_PIN"})
                    continue

                async with state_lock:
                    publisher_id = f"{hostname}_{state.publisher_counter}"
                    state.publisher_counter += 1
                    state.publishers[publisher_id] = PublisherSession(
                        publisher_id=publisher_id,
                        hostname=hostname,
                        websocket=websocket,
                        connected_at_ts=now_ts(),
                        last_seen_ts=now_ts(),
                    )

                    await websocket.send_json(
                        {
                            "type": "connected",
                            "publisher_id": publisher_id,
                            "token": create_livekit_token(publisher_id),
                            "livekit_url": LIVEKIT_URL,
                            "state": build_state_payload(),
                        }
                    )
                    print(f"[backend] publisher connected publisher_id={publisher_id}")
                    await broadcast_state()
                continue

            if publisher_id is None:
                await websocket.send_json({"type": "error", "code": "NOT_CONNECTED"})
                continue

            if msg_type == "heartbeat":
                async with state_lock:
                    session = state.publishers.get(publisher_id)
                    if session:
                        session.last_seen_ts = now_ts()
                        print(f"[backend] heartbeat publisher_id={publisher_id}")
                continue

            if msg_type == "on_air":
                channel_id = message.get("channel_id")
                async with state_lock:
                    channel = find_channel(channel_id)
                    if channel is None:
                        await websocket.send_json({"type": "error", "code": "UNKNOWN_CHANNEL"})
                        continue

                    owner = channel["owner"]
                    # idempotent ON AIR: first owner wins, duplicate from same owner is accepted
                    if owner is None:
                        channel["owner"] = publisher_id
                        channel["on_air_ts"] = now_ts()
                        print(f"[backend] ON_AIR owner set channel={channel_id} owner={publisher_id}")
                    elif owner == publisher_id:
                        channel["request_on_air_ts"] = message.get("request_on_air_ts")
                        print(f"[backend] ON_AIR duplicate ignored channel={channel_id} owner={publisher_id}")
                    else:
                        print(
                            f"[backend] ON_AIR rejected channel={channel_id} "
                            f"owner={owner} requester={publisher_id}"
                        )
                        await websocket.send_json(
                            {
                                "type": "on_air_rejected",
                                "channel_id": channel_id,
                                "owner": owner,
                            }
                        )
                    await broadcast_state()
                continue

            if msg_type == "stop":
                channel_id = message.get("channel_id")
                async with state_lock:
                    channel = find_channel(channel_id)
                    if channel is None:
                        await websocket.send_json({"type": "error", "code": "UNKNOWN_CHANNEL"})
                        continue

                    owner = channel["owner"]
                    if owner == publisher_id:
                        channel["owner"] = None
                        channel["off_air_ts"] = now_ts()
                        print(f"[backend] STOP owner cleared channel={channel_id} owner={publisher_id}")
                    elif owner is None:
                        channel["request_off_air_ts"] = message.get("request_off_air_ts")
                        print(f"[backend] STOP duplicate ignored channel={channel_id}")
                    await broadcast_state()
                continue

    except WebSocketDisconnect:
        print("[backend] publisher websocket disconnected")
        pass
    finally:
        async with state_lock:
            if publisher_id:
                await drop_publisher(publisher_id)
                await broadcast_state()


@app.websocket("/ws/listener")
async def listener_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[backend] listener websocket accepted")
    try:
        first = await websocket.receive_json()
        if first.get("type") != "connecting":
            print("[backend] listener invalid flow")
            await websocket.send_json({"type": "error", "code": "INVALID_FLOW"})
            return

        async with state_lock:
            listener_id = f"listener_{state.listener_counter}"
            state.listener_counter += 1
            state.listeners.add(websocket)
            await websocket.send_json(
                {
                    "type": "connected",
                    "listener_id": listener_id,
                    "token": create_livekit_token(listener_id),
                    "livekit_url": LIVEKIT_URL,
                    "state": build_state_payload(),
                }
            )
            print(f"[backend] listener connected listener_id={listener_id}")

        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "heartbeat":
                print("[backend] listener heartbeat")
                await websocket.send_json({"type": "heartbeat_ack", "ts": now_ts()})

    except WebSocketDisconnect:
        print("[backend] listener websocket disconnected")
        pass
    finally:
        async with state_lock:
            state.listeners.discard(websocket)


async def monitor_timeouts() -> None:
    while True:
        await asyncio.sleep(1)
        expired: list[str] = []
        async with state_lock:
            now = now_ts()
            for publisher_id, session in state.publishers.items():
                if now - session.last_seen_ts > HEARTBEAT_TIMEOUT_SECONDS:
                    expired.append(publisher_id)

            for publisher_id in expired:
                await drop_publisher(publisher_id)
                print(f"[backend] heartbeat timeout publisher_id={publisher_id}")

            if expired:
                await broadcast_state()


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(monitor_timeouts())
