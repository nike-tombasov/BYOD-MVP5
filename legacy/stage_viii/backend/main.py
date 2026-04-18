import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import DATA_DIR, DEFAULT_ROOM_CONFIG, LIVEKIT_URL, RECORDING_STATE_PATH, ROOM_CONFIG_PATH, RUNTIME_STATE_PATH
from backend.console.commands import console_command_loop
from backend.persistence.storage import JsonStorage
from backend.services.room_service import RoomService
from backend.services.state_service import RuntimeConfig, StateService
from backend.transport.admin_api import build_admin_router
from backend.transport.ws_handlers import build_ws_router, send_json_safe

app = FastAPI(title="BYOD Backend MVP Stage VII - implementation 2-3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime_config = RuntimeConfig(
    pin=DEFAULT_ROOM_CONFIG["pin"],
    room_name=DEFAULT_ROOM_CONFIG["i18n_library"]["room_name_i18n"]["en"],
    room_status="OPENED",
    target_capacity=DEFAULT_ROOM_CONFIG["target_capacity"],
    max_active_listeners=int(DEFAULT_ROOM_CONFIG["target_capacity"] * 1.05),
    max_new_connections_per_sec=max(1, int(DEFAULT_ROOM_CONFIG["target_capacity"] / 15)),
    i18n_library=DEFAULT_ROOM_CONFIG["i18n_library"],
)
state_service = StateService(channels=DEFAULT_ROOM_CONFIG["channels"], runtime_config=runtime_config)
state_lock = asyncio.Lock()
storage = JsonStorage(DATA_DIR, ROOM_CONFIG_PATH, RUNTIME_STATE_PATH, RECORDING_STATE_PATH)
room_service = RoomService(state_service=state_service, storage=storage, livekit_url=LIVEKIT_URL)

ws_router, broadcast_states = build_ws_router(state_service=state_service, room_service=room_service, state_lock=state_lock)
admin_router = build_admin_router(
    state_service=state_service,
    room_service=room_service,
    state_lock=state_lock,
    broadcast_cb=broadcast_states,
)
app.include_router(ws_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup() -> None:
    storage.ensure_data_dir()
    room_config_exists = room_service.load_from_persistence()
    if not room_config_exists:
        storage.log_event("bootstrap_defaults_applied")

    async with state_lock:
        if state_service.runtime.room_status == "OPENED" and not state_service.recording_active:
            await room_service.start_recording_locked(reason="startup_opened")

    room_service.persist_all()
    storage.log_event("backend_started")
    asyncio.create_task(room_service.monitor_timeouts(state_lock=state_lock, broadcast_cb=broadcast_states))
    asyncio.create_task(
        console_command_loop(
            state_service=state_service,
            room_service=room_service,
            state_lock=state_lock,
            broadcast_cb=broadcast_states,
            send_json_safe=send_json_safe,
        )
    )
