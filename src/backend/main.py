import asyncio
import contextlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from livekit import api as livekit_api
from src.backend.importer import ImportValidationError, parse_import_payload, room_import_to_runtime_dict
from src.backend.persistence import (
    append_jsonl as append_jsonl_file,
    atomic_write_json as atomic_write_json_file,
    current_day_suffix as current_day_suffix_utc,
    ensure_data_dir as ensure_data_dir_path,
    load_json_if_exists as load_json_if_exists_file,
)
from src.backend.runtime import ListenerRuntime
from src.backend.service import build_import_result
from src.backend.transport import (
    get_payload as extract_payload,
    make_envelope as build_envelope,
    validate_message_envelope as validate_envelope,
)

PIN = "123456"
ROOM_NAME = "Conference room"
ROOM_STATUS = "OPENED"
STATUS_TEXT = ""
LIVEKIT_URL = "ws://127.0.0.1:7880"
LIVEKIT_API_KEY = "devkey"
LIVEKIT_API_SECRET = "secret"
JWT_LIFETIME_SECONDS = 2 * 60 * 60
HEARTBEAT_TIMEOUT_SECONDS = 30
SCHEMA_VERSION = 1
TARGET_CAPACITY = 200
MAX_ACTIVE_LISTENERS = int(TARGET_CAPACITY * 1.05)
MAX_NEW_CONNECTIONS_PER_SEC = max(1, int(TARGET_CAPACITY / 15))
OVERRIDES: dict[str, str | None] = {"blocked": None, "closed": None}

DATA_DIR = Path("backend_data")
ROOM_CONFIG_PATH = DATA_DIR / "room_config_v1.json"
RUNTIME_STATE_PATH = DATA_DIR / "runtime_state_v1.json"
RECORDING_STATE_PATH = DATA_DIR / "recording_state_v1.json"

I18N_LIBRARY = {
    "room_name_i18n": {
        "en": "Conference room",
        "ru": "Зал конференции",
    },
    "custom_status_text_blocked_i18n": {
        "en": "Stream temporarily stopped",
        "ru": "Трансляция временно остановлена",
    },
    "custom_status_text_closed_i18n": {
        "en": "The conference is over. Thank you for your participation",
        "ru": "Конференция окончена. Благодарим за участие",
    },
}

CHANNELS = [
    {"channel_id": "channel_0", "channel_label": "Original - FLOOR - Оригинал", "listen": False, "owner": None},
    {"channel_id": "channel_1", "channel_label": "Russian - RUS - Русский", "listen": True, "owner": None},
    {"channel_id": "channel_2", "channel_label": "English - ENG - English", "listen": True, "owner": None},
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


app = FastAPI(title="BYOD Backend MVP Stage VII - implementation 2-3")
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
listener_runtime = ListenerRuntime(connect_sec=int(time.time()), connect_count=0)
recording_active = False
recording_started_ts: int | None = None
recording_files: list[dict[str, Any]] = []


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def now_ts() -> int:
    return int(time.time())


def next_request_id(prefix: str = "server") -> str:
    return f"{prefix}-{next(request_counter)}"


def update_derived_limits(target_capacity: int) -> None:
    global TARGET_CAPACITY, MAX_ACTIVE_LISTENERS, MAX_NEW_CONNECTIONS_PER_SEC
    TARGET_CAPACITY = target_capacity
    MAX_ACTIVE_LISTENERS = int(target_capacity * 1.05)
    MAX_NEW_CONNECTIONS_PER_SEC = max(1, int(target_capacity / 15))


def ensure_data_dir() -> None:
    ensure_data_dir_path(DATA_DIR)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json_file(path, payload)


def current_day_suffix() -> str:
    return current_day_suffix_utc()


def get_connections_log_path() -> Path:
    return DATA_DIR / f"connections_log_{current_day_suffix()}.jsonl"


def get_events_log_path() -> Path:
    return DATA_DIR / f"events_log_{current_day_suffix()}.jsonl"


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    append_jsonl_file(path, event)


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    return load_json_if_exists_file(path)


def persist_room_config() -> None:
    payload = {
        "schema_version": 1,
        "room_id": "room_main",
        "pin": PIN,
        "room_name": ROOM_NAME,
        "target_capacity": TARGET_CAPACITY,
        "channels": [
            {
                "channel_id": channel["channel_id"],
                "channel_label": channel["channel_label"],
                "listen": channel.get("listen", True),
            }
            for channel in state.channels
        ],
        "i18n_library": I18N_LIBRARY,
        "updated_ts": now_ts(),
    }
    atomic_write_json(ROOM_CONFIG_PATH, payload)


def persist_runtime_state() -> None:
    payload = {
        "schema_version": 1,
        "room_status": ROOM_STATUS,
        "owners": {channel["channel_id"]: channel.get("owner") for channel in state.channels},
        "publisher_online": {publisher_id: True for publisher_id in state.publishers.keys()},
        "overrides": dict(OVERRIDES),
        "updated_ts": now_ts(),
    }
    atomic_write_json(RUNTIME_STATE_PATH, payload)


def persist_recording_state() -> None:
    payload = {
        "schema_version": 1,
        "recording_active": recording_active,
        "recording_started_ts": recording_started_ts,
        "active_files": recording_files,
        "updated_ts": now_ts(),
    }
    atomic_write_json(RECORDING_STATE_PATH, payload)


def load_from_persistence() -> None:
    global PIN, ROOM_NAME, ROOM_STATUS, recording_active, recording_started_ts, recording_files

    room_config = load_json_if_exists(ROOM_CONFIG_PATH)
    if room_config:
        PIN = str(room_config.get("pin") or PIN)
        ROOM_NAME = str(room_config.get("room_name") or ROOM_NAME)
        target_capacity = int(room_config.get("target_capacity") or TARGET_CAPACITY)
        update_derived_limits(target_capacity)

        persisted_channels = room_config.get("channels")
        if isinstance(persisted_channels, list) and persisted_channels:
            owners = {channel["channel_id"]: channel.get("owner") for channel in state.channels}
            state.channels = []
            for channel in persisted_channels:
                cid = str(channel.get("channel_id") or "")
                if not cid:
                    continue
                state.channels.append(
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
                    I18N_LIBRARY[key] = {str(k): str(v) for k, v in value.items()}
            ROOM_NAME = str(I18N_LIBRARY.get("room_name_i18n", {}).get("en", ROOM_NAME))

    runtime_state = load_json_if_exists(RUNTIME_STATE_PATH)
    if runtime_state:
        ROOM_STATUS = str(runtime_state.get("room_status") or ROOM_STATUS)
        owners = runtime_state.get("owners") or {}
        if isinstance(owners, dict):
            for channel in state.channels:
                channel["owner"] = owners.get(channel["channel_id"])
        overrides = runtime_state.get("overrides") or {}
        if isinstance(overrides, dict):
            OVERRIDES["blocked"] = overrides.get("blocked")
            OVERRIDES["closed"] = overrides.get("closed")

    recording_state = load_json_if_exists(RECORDING_STATE_PATH)
    if recording_state:
        recording_active = bool(recording_state.get("recording_active", False))
        recording_started_ts = recording_state.get("recording_started_ts")
        files = recording_state.get("active_files")
        if isinstance(files, list):
            recording_files = files

    I18N_LIBRARY["room_name_i18n"]["en"] = ROOM_NAME


def log_connection(event: str, **fields: Any) -> None:
    payload = {"ts": now_ts(), "event": event, **fields}
    append_jsonl(get_connections_log_path(), payload)


def log_event(event: str, **fields: Any) -> None:
    payload = {"ts": now_ts(), "event": event, **fields}
    append_jsonl(get_events_log_path(), payload)


def make_envelope(msg_type: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return build_envelope(
        msg_type=msg_type,
        payload=payload,
        schema_version=SCHEMA_VERSION,
        ts=now_ts(),
        request_id=request_id or next_request_id(msg_type),
    )


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
    custom_text = STATUS_TEXT
    if ROOM_STATUS == "BLOCKED" and OVERRIDES.get("blocked"):
        custom_text = str(OVERRIDES["blocked"])
    if ROOM_STATUS == "CLOSED" and OVERRIDES.get("closed"):
        custom_text = str(OVERRIDES["closed"])
    return {
        "room_status": ROOM_STATUS,
        "status_custom_text": custom_text,
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
    return extract_payload(message)


def validate_message_envelope(message: dict[str, Any]) -> str | None:
    return validate_envelope(message, SCHEMA_VERSION)


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
    return (
        build_publisher_state_snapshot(channels_snapshot),
        build_listener_state_snapshot(channels_snapshot),
        build_legacy_state_snapshot(channels_snapshot),
        list(state.publishers.values()),
        list(state.listeners),
    )


async def persist_state_locked() -> None:
    persist_room_config()
    persist_runtime_state()
    persist_recording_state()


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
        await persist_state_locked()


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
    log_connection("publisher_disconnected", publisher_id=publisher_id)


async def start_recording_locked(reason: str) -> None:
    global recording_active, recording_started_ts, recording_files
    if recording_active:
        return
    recording_active = True
    recording_started_ts = now_ts()
    recording_files = []
    log_event("recording_marked_active", reason=reason, note="real multitrack recording is disabled")


async def stop_recording_locked(reason: str) -> None:
    global recording_active, recording_started_ts, recording_files
    if not recording_active:
        return
    log_event("recording_marked_inactive", reason=reason, started_ts=recording_started_ts)
    recording_active = False
    recording_started_ts = None
    recording_files = []


async def set_room_status_locked(new_status: str, reason: str) -> bool:
    global ROOM_STATUS
    if new_status not in {"OPENED", "BLOCKED", "CLOSED"}:
        return False
    ROOM_STATUS = new_status
    if new_status == "OPENED":
        await start_recording_locked(reason=reason)
    if new_status == "CLOSED":
        await stop_recording_locked(reason=reason)
    log_event("room_status_changed", room_status=ROOM_STATUS, reason=reason)
    return True


@app.post("/admin/import_json")
async def import_json(file: UploadFile = File(...)) -> dict[str, Any]:
    global PIN, ROOM_NAME, recording_active, recording_started_ts, recording_files

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"ok": False, "errors": [{"line": 1, "field": "file", "code": "INVALID_ENCODING", "message": "JSON file must be UTF-8"}]}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "errors": [{"line": 1, "field": "file", "code": "INVALID_JSON", "message": "Invalid JSON"}]}
    if not isinstance(payload, dict):
        return {"ok": False, "errors": [{"line": 1, "field": "file", "code": "INVALID_JSON", "message": "Root JSON must be object"}]}

    try:
        import_model = parse_import_payload(payload)
    except ImportValidationError as exc:
        return {"ok": False, "errors": exc.errors}

    import_runtime = room_import_to_runtime_dict(import_model)
    imported_pin = import_runtime["pin"]
    imported_target_capacity = import_runtime["target_capacity"]
    imported_i18n_library = import_runtime["i18n_library"]
    imported_room_name = imported_i18n_library["room_name_i18n"]["en"]
    imported_channels = import_runtime["channels"]

    publishers_to_close: list[WebSocket] = []
    listeners_to_close: list[WebSocket] = []
    async with state_lock:
        publishers_to_close = [session.websocket for session in state.publishers.values()]
        listeners_to_close = list(state.listeners)

        state.publishers.clear()
        state.listeners.clear()
        PIN = imported_pin
        ROOM_NAME = imported_room_name
        I18N_LIBRARY["room_name_i18n"] = dict(imported_i18n_library["room_name_i18n"])
        I18N_LIBRARY["custom_status_text_blocked_i18n"] = dict(imported_i18n_library["custom_status_text_blocked_i18n"])
        I18N_LIBRARY["custom_status_text_closed_i18n"] = dict(imported_i18n_library["custom_status_text_closed_i18n"])
        OVERRIDES["blocked"] = None
        OVERRIDES["closed"] = None
        recording_active = False
        recording_started_ts = None
        recording_files = []
        update_derived_limits(imported_target_capacity)

        state.channels = imported_channels
        await persist_state_locked()

    for ws in publishers_to_close + listeners_to_close:
        with contextlib.suppress(Exception):
            await ws.close()

    log_event(
        "json_import_applied",
        request_id=next_request_id("json-import"),
        target_capacity=TARGET_CAPACITY,
        max_active_listeners=MAX_ACTIVE_LISTENERS,
        max_new_connections_per_sec=MAX_NEW_CONNECTIONS_PER_SEC,
    )

    await broadcast_states()
    return build_import_result(
        room_name=ROOM_NAME,
        target_capacity=TARGET_CAPACITY,
        max_active_listeners=MAX_ACTIVE_LISTENERS,
        max_new_connections_per_sec=MAX_NEW_CONNECTIONS_PER_SEC,
        channels_count=len(state.channels),
    )


@app.get("/admin/check_ws_compat")
async def check_ws_compat() -> dict[str, Any]:
    channels_snapshot = [dict(channel) for channel in state.channels]
    publisher_state = build_publisher_state_snapshot(channels_snapshot)
    listener_state = build_listener_state_snapshot(channels_snapshot)

    publisher_required = {"room_name", "room_status", "channels"}
    listener_required = {"room_status", "channels"}

    publisher_ok = publisher_required.issubset(set(publisher_state.keys()))
    listener_ok = listener_required.issubset(set(listener_state.keys()))

    channel_pub_ok = all(
        {"channel_id", "channel_label", "owner", "listen"}.issubset(set(channel.keys()))
        for channel in publisher_state["channels"]
    )
    channel_lst_ok = all(
        {"channel_id", "channel_label", "listen"}.issubset(set(channel.keys()))
        for channel in listener_state["channels"]
    )

    ok = publisher_ok and listener_ok and channel_pub_ok and channel_lst_ok
    result = {
        "ok": ok,
        "publisher_state_ok": publisher_ok and channel_pub_ok,
        "listener_state_ok": listener_ok and channel_lst_ok,
        "publisher_schema_version": SCHEMA_VERSION,
        "listener_schema_version": SCHEMA_VERSION,
    }
    log_event("ws_compat_check", **result)
    return result


def format_console_help() -> str:
    return (
        "Commands:\n"
        "  help\n"
        "  status\n"
        "  set_room_status <OPENED|BLOCKED|CLOSED>\n"
        "  start_recording\n"
        "  stop_recording\n"
        "  set_channel_label <channel_id> <new_label>\n"
        "  set_listen <channel_id> <true|false>\n"
        "  off_air <channel_id>\n"
        "  set_override <blocked|closed> <text>\n"
        "  clear_override <blocked|closed>\n"
        "  emergency_override <blocked|closed> <text>\n"
        "  emergency_override_reset <blocked|closed>\n"
    )


async def process_console_command(line: str) -> str:
    parts = line.strip().split()
    if not parts:
        return "Empty command. Use: help"
    cmd = parts[0].lower()

    if cmd == "help":
        return format_console_help()

    if cmd == "status":
        return (
            f"room_status={ROOM_STATUS}, recording_active={recording_active}, "
            f"channels={len(state.channels)}, publishers={len(state.publishers)}, listeners={len(state.listeners)}, "
            f"target_capacity={TARGET_CAPACITY}, max_active_listeners={MAX_ACTIVE_LISTENERS}, "
            f"max_new_connections_per_sec={MAX_NEW_CONNECTIONS_PER_SEC}"
        )

    if cmd == "set_room_status" and len(parts) == 2:
        async with state_lock:
            ok = await set_room_status_locked(parts[1].upper(), reason="console")
            if not ok:
                return "Invalid status. Use OPENED, BLOCKED, or CLOSED."
            await persist_state_locked()
        await broadcast_states()
        return f"room_status changed to {ROOM_STATUS}"

    if cmd == "start_recording":
        async with state_lock:
            await start_recording_locked(reason="console")
            await persist_state_locked()
        return "recording started"

    if cmd == "stop_recording":
        async with state_lock:
            await stop_recording_locked(reason="console")
            await persist_state_locked()
        return "recording stopped"

    if cmd == "set_channel_label" and len(parts) >= 3:
        channel_id = parts[1]
        new_label = " ".join(parts[2:]).strip()
        async with state_lock:
            channel = find_channel(state.channels, channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            channel["channel_label"] = new_label
            await persist_state_locked()
            log_event("channel_label_changed", channel_id=channel_id, channel_label=new_label, actor="console")
        await broadcast_states()
        return f"{channel_id} label updated"

    if cmd == "set_listen" and len(parts) == 3:
        channel_id = parts[1]
        value = parts[2].lower()
        if value not in {"true", "false"}:
            return "set_listen value must be true or false."
        listen_value = value == "true"
        async with state_lock:
            channel = find_channel(state.channels, channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            channel["listen"] = listen_value
            await persist_state_locked()
            log_event("channel_listen_changed", channel_id=channel_id, listen=listen_value, actor="console")
        await broadcast_states()
        return f"{channel_id} listen set to {value}"

    if cmd == "off_air" and len(parts) == 2:
        channel_id = parts[1]
        owner_ws: WebSocket | None = None
        async with state_lock:
            channel = find_channel(state.channels, channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            previous_owner = channel.get("owner")
            channel["owner"] = None
            channel["off_air_ts"] = now_ts()
            await persist_state_locked()
            log_event("off_air_forced", channel_id=channel_id, previous_owner=previous_owner, actor="console")

            if previous_owner and previous_owner in state.publishers:
                owner_ws = state.publishers[previous_owner].websocket
        if owner_ws is not None:
            await send_json_safe(
                owner_ws,
                make_envelope("force_off_air", {"channel_id": channel_id, "reason": "console_off_air"}),
            )
        await broadcast_states()
        return f"{channel_id} owner cleared"

    if cmd == "set_override" and len(parts) >= 3:
        key = parts[1].lower()
        if key not in {"blocked", "closed"}:
            return "set_override only supports blocked or closed."
        text = " ".join(parts[2:]).strip()
        async with state_lock:
            OVERRIDES[key] = text
            await persist_state_locked()
            log_event("override_set", key=key, text=text, actor="console")
        await broadcast_states()
        return f"override {key} updated"

    if cmd == "emergency_override" and len(parts) >= 3:
        key = parts[1].lower()
        if key not in {"blocked", "closed"}:
            return "emergency_override only supports blocked or closed."
        text = " ".join(parts[2:]).strip()
        async with state_lock:
            OVERRIDES[key] = text
            await persist_state_locked()
            log_event("emergency_override_set", key=key, text=text, actor="console")
        await broadcast_states()
        return f"emergency override {key} updated"

    if cmd == "clear_override" and len(parts) == 2:
        key = parts[1].lower()
        if key not in {"blocked", "closed"}:
            return "clear_override only supports blocked or closed."
        async with state_lock:
            OVERRIDES[key] = None
            await persist_state_locked()
            log_event("override_cleared", key=key, actor="console")
        await broadcast_states()
        return f"override {key} cleared"

    if cmd == "emergency_override_reset" and len(parts) == 2:
        key = parts[1].lower()
        if key not in {"blocked", "closed"}:
            return "emergency_override_reset only supports blocked or closed."
        async with state_lock:
            OVERRIDES[key] = None
            await persist_state_locked()
            log_event("emergency_override_cleared", key=key, actor="console")
        await broadcast_states()
        return f"emergency override {key} cleared"

    return "Unknown command. Use: help"


async def console_command_loop() -> None:
    print("[backend] console command loop started. Type 'help' for commands.")
    while True:
        try:
            line = await asyncio.to_thread(input, "backend> ")
        except EOFError:
            await asyncio.sleep(1)
            continue
        except Exception as exc:
            print(f"[backend] console input error: {exc}")
            await asyncio.sleep(1)
            continue

        result = await process_console_command(line)
        print(f"[backend] {result}")


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
                    await persist_state_locked()
                    print(f"[backend] publisher connected publisher_id={publisher_id}")
                    log_connection("publisher_connected", publisher_id=publisher_id, hostname=hostname)

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
                unknown_channel = False

                async with state_lock:
                    channel = find_channel(state.channels, channel_id)
                    if channel is None:
                        unknown_channel = True
                    else:
                        owner = channel["owner"]
                        if owner is None:
                            channel["owner"] = publisher_id
                            channel["on_air_ts"] = now_ts()
                            await persist_state_locked()
                            log_event("on_air_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            print(f"[backend] ON_AIR granted channel={channel_id} owner={publisher_id}")
                        elif owner == publisher_id:
                            channel["request_on_air_ts"] = payload.get("request_on_air_ts")
                            log_event("on_air_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            print(f"[backend] ON_AIR duplicate ignored channel={channel_id} owner={publisher_id}")
                        else:
                            rejected_owner = owner
                            log_event("on_air_rejected", publisher_id=publisher_id, channel_id=channel_id, owner=owner, request_id=request_id)
                            print(
                                f"[backend] ON_AIR rejected channel={channel_id} "
                                f"owner={owner} requester={publisher_id}"
                            )

                if unknown_channel:
                    await send_error(websocket, "UNKNOWN_CHANNEL", request_id=request_id)
                    continue

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
                unknown_channel = False
                async with state_lock:
                    channel = find_channel(state.channels, channel_id)
                    if channel is None:
                        unknown_channel = True
                    else:
                        owner = channel["owner"]
                        if owner == publisher_id:
                            channel["owner"] = None
                            channel["off_air_ts"] = now_ts()
                            await persist_state_locked()
                            log_event("stop_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            print(f"[backend] STOP owner cleared channel={channel_id} owner={publisher_id}")
                        elif owner is None:
                            channel["request_off_air_ts"] = payload.get("request_off_air_ts")
                            log_event("stop_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            print(f"[backend] STOP duplicate ignored channel={channel_id}")

                if unknown_channel:
                    await send_error(websocket, "UNKNOWN_CHANNEL", request_id=request_id)
                    continue

                await broadcast_states()
                continue

            await send_error(websocket, "UNKNOWN_MESSAGE_TYPE", request_id=request_id)

    except WebSocketDisconnect:
        print("[backend] publisher websocket disconnected")
    finally:
        async with state_lock:
            if publisher_id:
                await drop_publisher_locked(publisher_id)
                await persist_state_locked()
        await broadcast_states()


@app.websocket("/ws/listener")
async def listener_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    print("[backend] listener websocket accepted")
    client_ip = websocket.client.host if websocket.client else "unknown"
    try:
        first = await websocket.receive_json()
        schema_error = validate_message_envelope(first)
        if schema_error is not None or first.get("type") != "connecting":
            print("[backend] listener invalid flow")
            await send_error(websocket, "INVALID_FLOW")
            return

        now = now_ts()
        if now != listener_runtime.connect_sec:
            listener_runtime.connect_sec = now
            listener_runtime.connect_count = 0
        listener_runtime.connect_count += 1

        reject_code: str | None = None
        async with state_lock:
            last_connect = listener_runtime.last_connect_by_ip.get(client_ip)
            if last_connect is not None and now - last_connect <= 2:
                reject_code = "RECONNECT_TOO_FAST"
            if len(state.listeners) >= MAX_ACTIVE_LISTENERS:
                reject_code = "LISTENER_OVERFLOW"
            elif listener_runtime.connect_count > MAX_NEW_CONNECTIONS_PER_SEC:
                reject_code = "CONNECTION_RATE_LIMIT"
            if reject_code:
                pass
            else:
                listener_runtime.last_connect_by_ip[client_ip] = now
                listener_id = f"listener_{state.listener_counter}"
                state.listener_counter += 1
                state.listeners.add(websocket)
                print(f"[backend] listener connected listener_id={listener_id}")
                log_connection("listener_connected", listener_id=listener_id, ip=client_ip)

        if reject_code:
            await send_error(websocket, reject_code)
            return

        request_id = first.get("request_id") if isinstance(first.get("request_id"), str) else next_request_id("lst-connect")
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
            log_connection("listener_disconnected")


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
                await persist_state_locked()

        if expired:
            await broadcast_states()


@app.on_event("startup")
async def startup() -> None:
    ensure_data_dir()
    room_config_exists = ROOM_CONFIG_PATH.exists()
    load_from_persistence()
    if not room_config_exists:
        log_event("bootstrap_defaults_applied")
    async with state_lock:
        if ROOM_STATUS == "OPENED" and not recording_active:
            await start_recording_locked(reason="startup_opened")
    if not room_config_exists:
        persist_room_config()
    persist_runtime_state()
    persist_recording_state()
    log_event("backend_started")
    asyncio.create_task(monitor_timeouts())
    asyncio.create_task(console_command_loop())
