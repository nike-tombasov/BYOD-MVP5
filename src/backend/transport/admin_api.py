from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

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

    @router.get("/admin/metrics_snapshot")
    async def metrics_snapshot(request: Request) -> dict[str, Any]:
        """Local-only machine-readable backend metrics for the VPS Analyzer.

        The Stage X nginx configuration intentionally does not proxy this path.
        The payload contains counts and diagnostic labels only; it must not
        include tokens, PINs, API secrets, or private environment dumps.
        """
        client_host = request.client.host if request.client else ""
        forwarded_for = request.headers.get("x-forwarded-for", "")
        forwarded_hosts = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        loopback_hosts = {"127.0.0.1", "::1", "localhost"}
        if client_host not in loopback_hosts or any(host not in loopback_hosts for host in forwarded_hosts):
            raise HTTPException(status_code=403, detail="local_only")

        async with state_lock:
            now_ts = state_service.now_ts()
            listeners = list(state_service.state.listeners.values())
            publishers = list(state_service.state.publishers.values())
            active_play_count = sum(1 for session in listeners if session.active_play)
            listeners_by_runner: dict[str, int] = {}
            session_counts_by_client_type: dict[str, int] = {}
            active_by_channel: dict[str, int] = {}
            for session in listeners:
                runner_id = session.runner_id or "unknown"
                listeners_by_runner[runner_id] = listeners_by_runner.get(runner_id, 0) + 1
                client_type = session.client_type or "listener"
                session_counts_by_client_type[client_type] = session_counts_by_client_type.get(client_type, 0) + 1
                if session.active_play and session.selected_channel:
                    active_by_channel[session.selected_channel] = active_by_channel.get(session.selected_channel, 0) + 1

            channels = [
                {
                    "channel_id": channel["channel_id"],
                    "listen": channel.get("listen", True),
                    "owner": channel.get("owner"),
                    "active_listeners": active_by_channel.get(channel["channel_id"], 0),
                }
                for channel in state_service.state.channels
            ]
            snapshot = {
                "ts": now_ts,
                "room_status": state_service.runtime.room_status,
                "target_capacity": state_service.runtime.target_capacity,
                "max_active_listeners": state_service.runtime.max_active_listeners,
                "max_new_connections_per_sec": state_service.runtime.max_new_connections_per_sec,
                "backend_publishers_count": len(publishers),
                "backend_listeners_count": len(listeners),
                "backend_active_play_count": active_play_count,
                "backend_listeners_by_runner": listeners_by_runner,
                "channels": channels,
                "recent_connection_rate": state_service.listener_connect_count,
                "reject_counters": dict(state_service.listener_reject_counters),
                "session_counts_by_client_type": session_counts_by_client_type,
            }
        return snapshot

    return router
