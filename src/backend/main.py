import asyncio
import csv
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from io import StringIO
from itertools import count
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
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
TARGET_CAPACITY = 300
MAX_ACTIVE_LISTENERS = int(TARGET_CAPACITY * 1.05)
MAX_NEW_CONNECTIONS_PER_SEC = max(1, int(TARGET_CAPACITY / 15))
OVERRIDES: dict[str, str | None] = {"blocked": None, "closed": None}

DATA_DIR = Path("backend_data")
ROOM_CONFIG_PATH = DATA_DIR / "room_config_v1.json"
RUNTIME_STATE_PATH = DATA_DIR / "runtime_state_v1.json"
RECORDING_STATE_PATH = DATA_DIR / "recording_state_v1.json"
RECORDINGS_DIR = Path("recordings")

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
listener_connect_sec = int(time.time())
listener_connect_count = 0
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def current_day_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def get_connections_log_path() -> Path:
    return DATA_DIR / f"connections_log_{current_day_suffix()}.jsonl"


def get_events_log_path() -> Path:
    return DATA_DIR / f"events_log_{current_day_suffix()}.jsonl"


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
        f.flush()


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def sanitize_label_for_filename(label: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label.strip())
    return safe[:64] or "channel"


async def start_recording_locked(reason: str) -> None:
    global recording_active, recording_started_ts, recording_files
    if recording_active:
        return
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    recording_started_ts = now_ts()
    stamp = datetime.fromtimestamp(recording_started_ts, tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    recording_files = []
    for channel in state.channels:
        filename = f"{stamp}-{channel['channel_id']}-{sanitize_label_for_filename(channel['channel_label'])}.mp3"
        path = RECORDINGS_DIR / filename
        path.touch(exist_ok=True)
        recording_files.append({"channel_id": channel["channel_id"], "path": str(path), "created_ts": now_ts()})
    recording_active = True
    log_event("recording_started", reason=reason, files=len(recording_files))


async def stop_recording_locked(reason: str) -> None:
    global recording_active, recording_started_ts, recording_files
    if not recording_active:
        return
    recording_active = False
    log_event("recording_stopped", reason=reason, files=len(recording_files), started_ts=recording_started_ts)
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


def validate_csv_rows(rows: list[dict[str, str]], headers: list[str]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    required_headers = {"channel_id", "channel_label", "listen"}
    optional_headers = {"room_name", "pin", "target_capacity"}

    header_set = set(headers)
    missing = required_headers - header_set
    unknown = header_set - required_headers - optional_headers
    if missing:
        for field in sorted(missing):
            errors.append({"line": 1, "field": field, "code": "MISSING_HEADER", "message": f"Header {field} is required"})
    if unknown:
        for field in sorted(unknown):
            errors.append({"line": 1, "field": field, "code": "UNKNOWN_HEADER", "message": f"Header {field} is not allowed"})

    seen_ids: set[str] = set()
    room_name_values: set[str] = set()
    pin_values: set[str] = set()
    target_capacity_values: set[str] = set()

    for idx, row in enumerate(rows, start=2):
        channel_id = (row.get("channel_id") or "").strip()
        channel_label = (row.get("channel_label") or "").strip()
        listen = (row.get("listen") or "").strip()

        if not channel_id.startswith("channel_") or not channel_id.replace("channel_", "", 1).isdigit():
            errors.append({"line": idx, "field": "channel_id", "code": "INVALID_CHANNEL_ID", "message": f"Invalid channel_id: {channel_id}"})
        if channel_id in seen_ids:
            errors.append({"line": idx, "field": "channel_id", "code": "DUPLICATE_CHANNEL_ID", "message": f"{channel_id} already used"})
        seen_ids.add(channel_id)

        if len(channel_label) < 1 or len(channel_label) > 80:
            errors.append({"line": idx, "field": "channel_label", "code": "EMPTY_CHANNEL_LABEL", "message": "channel_label must be 1..80 chars"})

        if listen not in {"true", "false"}:
            errors.append({"line": idx, "field": "listen", "code": "INVALID_LISTEN_VALUE", "message": f"listen must be true/false, got: {listen}"})

        room_name = (row.get("room_name") or "").strip()
        if room_name:
            room_name_values.add(room_name)

        pin = (row.get("pin") or "").strip()
        if pin:
            pin_values.add(pin)

        target_capacity = (row.get("target_capacity") or "").strip()
        if target_capacity:
            target_capacity_values.add(target_capacity)

    if len(room_name_values) > 1:
        errors.append({"line": 1, "field": "room_name", "code": "INCONSISTENT_ROOM_NAME", "message": "room_name must be identical in all rows"})
    if len(pin_values) > 1:
        errors.append({"line": 1, "field": "pin", "code": "INCONSISTENT_PIN", "message": "pin must be identical in all rows"})

    if not target_capacity_values:
        errors.append({"line": 1, "field": "target_capacity", "code": "MISSING_TARGET_CAPACITY", "message": "target_capacity required in CSV for now"})
    elif len(target_capacity_values) > 1:
        errors.append({"line": 1, "field": "target_capacity", "code": "INVALID_TARGET_CAPACITY", "message": "target_capacity must be identical in all rows"})
    else:
        value = next(iter(target_capacity_values))
        if not value.isdigit() or int(value) <= 0:
            errors.append({"line": 1, "field": "target_capacity", "code": "INVALID_TARGET_CAPACITY", "message": "target_capacity must be positive integer"})

    return errors


@app.post("/admin/import_csv")
async def import_csv(file: UploadFile = File(...)) -> dict[str, Any]:
    global PIN, ROOM_NAME

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return {"ok": False, "errors": [{"line": 1, "field": "file", "code": "INVALID_ENCODING", "message": "File must be UTF-8"}]}

    reader = csv.DictReader(StringIO(text), delimiter=";")
    rows = list(reader)
    headers = reader.fieldnames or []

    errors = validate_csv_rows(rows, headers)
    if errors:
        return {"ok": False, "errors": errors}

    first = rows[0]
    imported_room_name = (first.get("room_name") or ROOM_NAME).strip() or ROOM_NAME
    imported_pin = (first.get("pin") or PIN).strip() or PIN
    imported_target_capacity = int((first.get("target_capacity") or TARGET_CAPACITY))

    imported_channels = []
    for row in rows:
        imported_channels.append(
            {
                "channel_id": row["channel_id"].strip(),
                "channel_label": row["channel_label"].strip(),
                "listen": row["listen"].strip() == "true",
                "owner": None,
            }
        )

    async with state_lock:
        PIN = imported_pin
        ROOM_NAME = imported_room_name
        I18N_LIBRARY["room_name_i18n"]["en"] = ROOM_NAME
        update_derived_limits(imported_target_capacity)

        state.channels = imported_channels
        for session in state.publishers.values():
            session.online = True

        await persist_state_locked()

    log_event(
        "csv_import_applied",
        request_id=next_request_id("csv-import"),
        target_capacity=TARGET_CAPACITY,
        max_active_listeners=MAX_ACTIVE_LISTENERS,
        max_new_connections_per_sec=MAX_NEW_CONNECTIONS_PER_SEC,
    )

    await broadcast_states()
    return {
        "ok": True,
        "applied": {
            "room_name": ROOM_NAME,
            "target_capacity": TARGET_CAPACITY,
            "max_active_listeners": MAX_ACTIVE_LISTENERS,
            "max_new_connections_per_sec": MAX_NEW_CONNECTIONS_PER_SEC,
            "channels": len(state.channels),
        },
    }


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
                await send_json_safe(
                    state.publishers[previous_owner].websocket,
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
    global listener_connect_sec, listener_connect_count

    await websocket.accept()
    print("[backend] listener websocket accepted")
    try:
        first = await websocket.receive_json()
        schema_error = validate_message_envelope(first)
        if schema_error is not None or first.get("type") != "connecting":
            print("[backend] listener invalid flow")
            await send_error(websocket, "INVALID_FLOW")
            return

        now = now_ts()
        if now != listener_connect_sec:
            listener_connect_sec = now
            listener_connect_count = 0
        listener_connect_count += 1

        reject_code: str | None = None
        async with state_lock:
            if len(state.listeners) >= MAX_ACTIVE_LISTENERS:
                reject_code = "LISTENER_OVERFLOW"
            elif listener_connect_count > MAX_NEW_CONNECTIONS_PER_SEC:
                reject_code = "CONNECTION_RATE_LIMIT"
            if reject_code:
                pass
            else:
                listener_id = f"listener_{state.listener_counter}"
                state.listener_counter += 1
                state.listeners.add(websocket)
                print(f"[backend] listener connected listener_id={listener_id}")
                log_connection("listener_connected", listener_id=listener_id)

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
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    load_from_persistence()
    async with state_lock:
        if ROOM_STATUS == "OPENED" and not recording_active:
            await start_recording_locked(reason="startup_opened")
    persist_room_config()
    persist_runtime_state()
    persist_recording_state()
    log_event("backend_started")
    asyncio.create_task(monitor_timeouts())
    asyncio.create_task(console_command_loop())
