from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, UploadFile

from backend.importers.room_config_json import parse_room_config_json_bytes
from backend.services.room_service import RoomService
from backend.services.state_service import StateService


def build_admin_router(state_service: StateService, room_service: RoomService, state_lock: Any, broadcast_cb: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/admin/import_json")
    async def import_json(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        result = parse_room_config_json_bytes(content)
        if result.errors:
            return {"ok": False, "errors": [err.to_dict() for err in result.errors]}

        await room_service.apply_imported_room_config(result.config, state_lock=state_lock)
        await broadcast_cb()

        runtime = state_service.runtime
        return {
            "ok": True,
            "applied": {
                "room_name": runtime.room_name,
                "target_capacity": runtime.target_capacity,
                "max_active_listeners": runtime.max_active_listeners,
                "max_new_connections_per_sec": runtime.max_new_connections_per_sec,
                "channels": len(state_service.state.channels),
            },
        }

    @router.get("/admin/check_ws_compat")
    async def check_ws_compat() -> dict[str, Any]:
        channels_snapshot = [dict(channel) for channel in state_service.state.channels]
        publisher_state = state_service.build_publisher_state_snapshot(channels_snapshot)
        listener_state = state_service.build_listener_state_snapshot(channels_snapshot)

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
            "publisher_schema_version": 1,
            "listener_schema_version": 1,
        }
        room_service.storage.log_event("ws_compat_check", **result)
        return result

    return router
