from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.room_service import RoomService
from backend.services.state_service import StateService


async def send_json_safe(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


async def send_error(ws: WebSocket, state_service: StateService, code: str, request_id: str | None = None) -> None:
    await send_json_safe(
        ws,
        state_service.make_envelope("error", {"ok": False, "code": code}, request_id=request_id),
    )


def build_ws_router(state_service: StateService, room_service: RoomService, state_lock: Any) -> tuple[APIRouter, Any]:
    router = APIRouter()

    async def broadcast_states() -> None:
        async with state_lock:
            channels_snapshot = [dict(ch) for ch in state_service.state.channels]
            publisher_state = state_service.build_publisher_state_snapshot(channels_snapshot)
            listener_state = state_service.build_listener_state_snapshot(channels_snapshot)
            publishers = list(state_service.state.publishers.values())
            listeners = list(state_service.state.listeners)

        publisher_payload = state_service.make_envelope("publisher_state", publisher_state)
        listener_payload = state_service.make_envelope("listener_state", listener_state)

        dead_publishers: list[str] = []
        for session in publishers:
            if not await send_json_safe(session.websocket, publisher_payload):
                dead_publishers.append(session.publisher_id)

        dead_listeners: list[WebSocket] = []
        for ws in listeners:
            if not await send_json_safe(ws, listener_payload):
                dead_listeners.append(ws)

        if not dead_publishers and not dead_listeners:
            return

        async with state_lock:
            for publisher_id in dead_publishers:
                await room_service.drop_publisher_locked(publisher_id)
            for ws in dead_listeners:
                state_service.state.listeners.discard(ws)
            room_service.persist_all()

    async def send_connect_success(
        websocket: WebSocket,
        client_role: str,
        token: str,
        request_id: str,
        publisher_id: str | None = None,
        listener_id: str | None = None,
    ) -> None:
        async with state_lock:
            channels_snapshot = [dict(ch) for ch in state_service.state.channels]

        publisher_state = state_service.build_publisher_state_snapshot(channels_snapshot)
        listener_state = state_service.build_listener_state_snapshot(channels_snapshot)
        i18n_library = state_service.build_i18n_library_payload()

        if client_role == "publisher":
            await websocket.send_json(
                state_service.make_envelope(
                    "connecting",
                    {
                        "ok": True,
                        "client_role": "publisher",
                        "publisher_id": publisher_id,
                        "token": token,
                        "livekit_url": room_service.livekit_url,
                    },
                    request_id=request_id,
                )
            )
            await websocket.send_json(state_service.make_envelope("i18n_library", i18n_library))
            await websocket.send_json(state_service.make_envelope("publisher_state", publisher_state))
            return

        await websocket.send_json(
            state_service.make_envelope(
                "connecting",
                {
                    "ok": True,
                    "client_role": "listener",
                    "listener_id": listener_id,
                    "token": token,
                    "livekit_url": room_service.livekit_url,
                },
                request_id=request_id,
            )
        )
        await websocket.send_json(state_service.make_envelope("i18n_library", i18n_library))
        await websocket.send_json(state_service.make_envelope("listener_state", listener_state))

    @router.websocket("/ws/publisher")
    async def publisher_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        publisher_id: str | None = None
        allowed_types = {"connecting", "heartbeat", "on_air", "stop"}
        try:
            while True:
                message = await websocket.receive_json()
                schema_error = state_service.validate_message_envelope(message)
                request_id = message.get("request_id") if isinstance(message.get("request_id"), str) else None
                msg_type = message.get("type")
                if schema_error is not None:
                    await send_error(websocket, state_service, "SCHEMA_VALIDATION_ERROR", request_id=request_id)
                    continue
                if msg_type not in allowed_types:
                    await send_error(websocket, state_service, "SCHEMA_VALIDATION_ERROR", request_id=request_id)
                    continue

                payload = state_service.get_payload(message)

                if msg_type == "connecting":
                    pin = str(payload.get("pin") or "")
                    hostname = str(payload.get("hostname") or "publisher-host")
                    if pin != state_service.runtime.pin:
                        await send_error(websocket, state_service, "INVALID_PIN", request_id=request_id)
                        continue

                    async with state_lock:
                        session = state_service.add_publisher(websocket=websocket, hostname=hostname)
                        publisher_id = session.publisher_id
                        room_service.persist_all()
                        room_service.storage.log_connection("publisher_connected", publisher_id=publisher_id, hostname=hostname)

                    await send_connect_success(
                        websocket=websocket,
                        client_role="publisher",
                        publisher_id=publisher_id,
                        token=room_service.create_livekit_token(publisher_id),
                        request_id=request_id or state_service.next_request_id("pub-connect"),
                    )
                    await broadcast_states()
                    continue

                if publisher_id is None:
                    await send_error(websocket, state_service, "NOT_CONNECTED", request_id=request_id)
                    continue

                if msg_type == "heartbeat":
                    async with state_lock:
                        session = state_service.state.publishers.get(publisher_id)
                        if session:
                            session.last_seen_ts = float(state_service.now_ts())
                    continue

                if msg_type == "on_air":
                    channel_id = payload.get("channel_id")
                    rejected_owner = None
                    unknown_channel = False
                    async with state_lock:
                        channel = state_service.find_channel(channel_id)
                        if channel is None:
                            unknown_channel = True
                        else:
                            owner = channel.get("owner")
                            if owner is None:
                                channel["owner"] = publisher_id
                                channel["on_air_ts"] = state_service.now_ts()
                                room_service.persist_all()
                                room_service.storage.log_event("on_air_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            elif owner == publisher_id:
                                channel["request_on_air_ts"] = payload.get("request_on_air_ts")
                                room_service.storage.log_event("on_air_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            else:
                                rejected_owner = owner
                                room_service.storage.log_event("on_air_rejected", publisher_id=publisher_id, channel_id=channel_id, owner=owner, request_id=request_id)
                    if unknown_channel:
                        await send_error(websocket, state_service, "UNKNOWN_CHANNEL", request_id=request_id)
                        continue
                    if rejected_owner is not None:
                        await send_error(websocket, state_service, "OWNER_MISMATCH", request_id=request_id)
                    await broadcast_states()
                    continue

                if msg_type == "stop":
                    channel_id = payload.get("channel_id")
                    unknown_channel = False
                    async with state_lock:
                        channel = state_service.find_channel(channel_id)
                        if channel is None:
                            unknown_channel = True
                        else:
                            owner = channel.get("owner")
                            if owner == publisher_id:
                                channel["owner"] = None
                                channel["off_air_ts"] = state_service.now_ts()
                                room_service.persist_all()
                                room_service.storage.log_event("stop_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                            elif owner is None:
                                channel["request_off_air_ts"] = payload.get("request_off_air_ts")
                                room_service.storage.log_event("stop_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                    if unknown_channel:
                        await send_error(websocket, state_service, "UNKNOWN_CHANNEL", request_id=request_id)
                        continue
                    await broadcast_states()
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            async with state_lock:
                if publisher_id:
                    await room_service.drop_publisher_locked(publisher_id)
                    room_service.persist_all()
            await broadcast_states()

    @router.websocket("/ws/listener")
    async def listener_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        client_ip = websocket.client.host if websocket.client else "unknown"
        listener_id = ""
        allowed_types = {"connecting", "heartbeat"}
        try:
            first = await websocket.receive_json()
            request_id = first.get("request_id") if isinstance(first.get("request_id"), str) else None
            schema_error = state_service.validate_message_envelope(first)
            if schema_error is not None or first.get("type") != "connecting":
                await send_error(websocket, state_service, "SCHEMA_VALIDATION_ERROR", request_id=request_id)
                return

            now = state_service.now_ts()
            if now != state_service.listener_connect_sec:
                state_service.listener_connect_sec = now
                state_service.listener_connect_count = 0
            state_service.listener_connect_count += 1

            reject_code = None
            async with state_lock:
                last_connect = state_service.listener_last_connect_by_ip.get(client_ip)
                if last_connect is not None and now - last_connect <= 2:
                    reject_code = "RECONNECT_TOO_FAST"
                if len(state_service.state.listeners) >= state_service.runtime.max_active_listeners:
                    reject_code = "LISTENER_OVERFLOW"
                elif state_service.listener_connect_count > state_service.runtime.max_new_connections_per_sec:
                    reject_code = "CONNECTION_RATE_LIMIT"
                if reject_code is None:
                    state_service.listener_last_connect_by_ip[client_ip] = now
                    listener_id = f"listener_{state_service.state.listener_counter}"
                    state_service.state.listener_counter += 1
                    state_service.state.listeners.add(websocket)
                    room_service.storage.log_connection("listener_connected", listener_id=listener_id, ip=client_ip)

            if reject_code:
                await send_error(websocket, state_service, reject_code, request_id=request_id)
                return

            await send_connect_success(
                websocket=websocket,
                client_role="listener",
                listener_id=listener_id,
                token=room_service.create_livekit_token(listener_id),
                request_id=request_id or state_service.next_request_id("lst-connect"),
            )

            while True:
                msg = await websocket.receive_json()
                request_id = msg.get("request_id") if isinstance(msg.get("request_id"), str) else None
                schema_error = state_service.validate_message_envelope(msg)
                msg_type = msg.get("type")
                if schema_error is not None or msg_type not in allowed_types:
                    await send_error(websocket, state_service, "SCHEMA_VALIDATION_ERROR", request_id=request_id)
                    continue

        except WebSocketDisconnect:
            pass
        finally:
            async with state_lock:
                state_service.state.listeners.discard(websocket)
                room_service.storage.log_connection("listener_disconnected")

    return router, broadcast_states
