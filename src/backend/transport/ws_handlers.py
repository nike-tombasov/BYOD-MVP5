from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS
from backend.services.room_service import RoomService
from backend.services.state_service import StateService


logger = logging.getLogger("byod.backend.ws")


def _client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return websocket.client.host if websocket.client else "unknown"


def _message_context(message: Any) -> tuple[str | None, str | None]:
    if not isinstance(message, dict):
        return None, None
    request_id = message.get("request_id") if isinstance(message.get("request_id"), str) else None
    msg_type = message.get("type") if isinstance(message.get("type"), str) else None
    return request_id, msg_type


async def send_json_safe(ws: WebSocket, payload: dict[str, Any]) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


def build_ws_router(state_service: StateService, room_service: RoomService, state_lock: Any) -> tuple[APIRouter, Any]:
    router = APIRouter()
    storage = room_service.storage

    async def send_error(
        websocket: WebSocket,
        code: str,
        request_id: str | None = None,
        client_role: str = "listener",
        publisher_id: str | None = None,
        listener_id: str | None = None,
    ) -> bool:
        sent = await send_json_safe(
            websocket,
            state_service.make_envelope("error", {"ok": False, "code": code}, request_id=request_id),
        )
        fields = {"code": code, "request_id": request_id}
        if publisher_id:
            fields["publisher_id"] = publisher_id
        if listener_id:
            fields["listener_id"] = listener_id
        error_event = "publisher_error_sent" if client_role == "publisher" else "listener_error_sent"
        storage.log_event(error_event, **fields)
        if code in {"LIVEKIT_UNAVAILABLE", "SCHEMA_VALIDATION_ERROR"}:
            logger.error("websocket_error_sent role=%s fields=%s", client_role, fields)
        return sent

    async def broadcast_states() -> None:
        async with state_lock:
            channels_snapshot = [dict(ch) for ch in state_service.state.channels]
            publisher_state = state_service.build_publisher_state_snapshot(channels_snapshot)
            listener_state = state_service.build_listener_state_snapshot(channels_snapshot)
            publishers = list(state_service.state.publishers.values())
            listeners = list(state_service.state.listeners.values())

        publisher_payload = state_service.make_envelope("publisher_state", publisher_state)
        listener_payload = state_service.make_envelope("listener_state", listener_state)
        dead_publishers = [
            session.publisher_id
            for session in publishers
            if not await send_json_safe(session.websocket, publisher_payload)
        ]
        dead_listeners = [
            session.listener_id
            for session in listeners
            if not await send_json_safe(session.websocket, listener_payload)
        ]
        if not dead_publishers and not dead_listeners:
            return

        async with state_lock:
            for publisher_id in dead_publishers:
                await room_service.drop_publisher_locked(publisher_id)
            for listener_id in dead_listeners:
                state_service.state.listeners.pop(listener_id, None)
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

        state_payload = (
            state_service.build_publisher_state_snapshot(channels_snapshot)
            if client_role == "publisher"
            else state_service.build_listener_state_snapshot(channels_snapshot)
        )
        client_id = publisher_id if client_role == "publisher" else listener_id
        id_key = "publisher_id" if client_role == "publisher" else "listener_id"
        await websocket.send_json(
            state_service.make_envelope(
                "connecting",
                {
                    "ok": True,
                    "client_role": client_role,
                    id_key: client_id,
                    "token": token,
                    "livekit_url": room_service.livekit_url,
                },
                request_id=request_id,
            )
        )
        connect_event = (
            "publisher_connect_success_sent"
            if client_role == "publisher"
            else "listener_connect_success_sent"
        )
        storage.log_event(connect_event, **{id_key: client_id}, request_id=request_id)
        await websocket.send_json(
            state_service.make_envelope("i18n_library", state_service.build_i18n_library_payload())
        )
        i18n_event = "publisher_i18n_sent" if client_role == "publisher" else "listener_i18n_sent"
        storage.log_event(i18n_event, **{id_key: client_id})
        await websocket.send_json(
            state_service.make_envelope(f"{client_role}_state", state_payload)
        )
        state_event = "publisher_state_sent" if client_role == "publisher" else "listener_state_sent"
        storage.log_event(state_event, **{id_key: client_id})

    def log_reachability(event: str, request_id: str | None) -> dict[str, Any]:
        result = room_service.get_livekit_reachability()
        fields = {
            "request_id": request_id,
            "livekit_url": room_service.livekit_url,
            "target_host": result["host"],
            "target_port": result["port"],
            "timeout": result["timeout"],
            "ok": result["ok"],
        }
        if result["error_message"]:
            fields["error"] = result["error_message"]
            fields["error_type"] = result["error_type"]
        storage.log_event(event, **fields)
        if not result["ok"]:
            logger.error("%s fields=%s", event, fields)
        return result

    @router.websocket("/ws/publisher")
    async def publisher_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        client_ip = _client_ip(websocket)
        storage.log_connection("publisher_ws_accepted", client_ip=client_ip, path=websocket.url.path)
        publisher_id: str | None = None
        allowed_types = {"connecting", "heartbeat", "on_air", "stop"}
        disconnect_code: int | None = None
        try:
            while True:
                message = await websocket.receive_json()
                request_id, msg_type = _message_context(message)
                storage.log_event(
                    "publisher_ws_message_received",
                    msg_type=msg_type,
                    request_id=request_id,
                    publisher_id=publisher_id,
                )
                schema_error = state_service.validate_message_envelope(message)
                if schema_error is not None or msg_type not in allowed_types:
                    reason = schema_error or f"unsupported message type: {msg_type}"
                    storage.log_event(
                        "publisher_ws_schema_error",
                        request_id=request_id,
                        msg_type=msg_type,
                        schema_error=reason,
                    )
                    logger.error("publisher_ws_schema_error request_id=%s reason=%s", request_id, reason)
                    await send_error(websocket, "SCHEMA_VALIDATION_ERROR", request_id, "publisher", publisher_id=publisher_id)
                    continue

                payload = state_service.get_payload(message)
                if msg_type == "connecting":
                    pin = str(payload.get("pin") or "")
                    hostname = str(payload.get("hostname") or "publisher-host")
                    if pin != state_service.runtime.pin:
                        storage.log_event(
                            "publisher_invalid_pin",
                            request_id=request_id,
                            hostname=hostname,
                            pin_length=len(pin),
                        )
                        logger.warning("publisher_invalid_pin request_id=%s hostname=%s pin_length=%s", request_id, hostname, len(pin))
                        await send_error(websocket, "INVALID_PIN", request_id, "publisher", publisher_id=publisher_id)
                        continue

                    if not log_reachability("publisher_livekit_reachability_check", request_id)["ok"]:
                        await send_error(websocket, "LIVEKIT_UNAVAILABLE", request_id, "publisher", publisher_id=publisher_id)
                        continue

                    async with state_lock:
                        session = state_service.add_publisher(websocket=websocket, hostname=hostname)
                        publisher_id = session.publisher_id
                        room_service.persist_all()
                        storage.log_connection(
                            "publisher_connected",
                            publisher_id=publisher_id,
                            hostname=hostname,
                            livekit_url=room_service.livekit_url,
                        )

                    await send_connect_success(
                        websocket,
                        "publisher",
                        room_service.create_livekit_token(publisher_id),
                        request_id or state_service.next_request_id("pub-connect"),
                        publisher_id=publisher_id,
                    )
                    await broadcast_states()
                    continue

                if publisher_id is None:
                    await send_error(websocket, "NOT_CONNECTED", request_id, "publisher", publisher_id=publisher_id)
                    continue

                if msg_type == "heartbeat":
                    async with state_lock:
                        session = state_service.state.publishers.get(publisher_id)
                        if session:
                            session.last_seen_ts = float(state_service.now_ts())
                    continue

                channel_id = payload.get("channel_id")
                if msg_type == "on_air":
                    if not log_reachability("publisher_livekit_reachability_check", request_id)["ok"]:
                        await send_error(websocket, "LIVEKIT_UNAVAILABLE", request_id, "publisher", publisher_id=publisher_id)
                        continue
                    rejected_owner = None
                    unknown_channel = False
                    async with state_lock:
                        channel = state_service.find_channel(channel_id)
                        if channel is None:
                            unknown_channel = True
                        elif channel.get("owner") is None:
                            channel["owner"] = publisher_id
                            channel["on_air_ts"] = state_service.now_ts()
                            room_service.persist_all()
                            storage.log_event("on_air_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                        elif channel.get("owner") == publisher_id:
                            channel["request_on_air_ts"] = payload.get("request_on_air_ts")
                            storage.log_event("on_air_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                        else:
                            rejected_owner = channel.get("owner")
                            storage.log_event("on_air_rejected", publisher_id=publisher_id, channel_id=channel_id, owner=rejected_owner, request_id=request_id)
                    if unknown_channel:
                        await send_error(websocket, "UNKNOWN_CHANNEL", request_id, "publisher", publisher_id=publisher_id)
                        continue
                    if rejected_owner is not None:
                        await send_error(websocket, "OWNER_MISMATCH", request_id, "publisher", publisher_id=publisher_id)
                    await broadcast_states()
                    continue

                if msg_type == "stop":
                    unknown_channel = False
                    async with state_lock:
                        channel = state_service.find_channel(channel_id)
                        if channel is None:
                            unknown_channel = True
                        elif channel.get("owner") == publisher_id:
                            channel["owner"] = None
                            channel["off_air_ts"] = state_service.now_ts()
                            room_service.persist_all()
                            storage.log_event("stop_granted", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                        elif channel.get("owner") is None:
                            channel["request_off_air_ts"] = payload.get("request_off_air_ts")
                            storage.log_event("stop_duplicate", publisher_id=publisher_id, channel_id=channel_id, request_id=request_id)
                    if unknown_channel:
                        await send_error(websocket, "UNKNOWN_CHANNEL", request_id, "publisher", publisher_id=publisher_id)
                        continue
                    await broadcast_states()
        except WebSocketDisconnect as exc:
            disconnect_code = exc.code
        except Exception as exc:
            summary = traceback.format_exc()
            storage.log_event(
                "publisher_ws_exception",
                publisher_id=publisher_id,
                exception_type=type(exc).__name__,
                exception_repr=repr(exc),
                traceback_summary=summary,
            )
            logger.exception("publisher_ws_exception publisher_id=%s", publisher_id)
        finally:
            storage.log_connection("publisher_ws_disconnect", publisher_id=publisher_id, close_code=disconnect_code)
            async with state_lock:
                if publisher_id:
                    await room_service.drop_publisher_locked(publisher_id)
                    room_service.persist_all()
            await broadcast_states()

    @router.websocket("/ws/listener")
    async def listener_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        client_ip = _client_ip(websocket)
        storage.log_connection("listener_ws_accepted", client_ip=client_ip, path=websocket.url.path)
        listener_id: str | None = None
        disconnect_code: int | None = None
        allowed_types = {"connecting", "heartbeat"}
        try:
            first = await websocket.receive_json()
            request_id, msg_type = _message_context(first)
            storage.log_event("listener_first_message_received", msg_type=msg_type, request_id=request_id)
            schema_error = state_service.validate_message_envelope(first)
            if schema_error is not None or msg_type != "connecting":
                reason = schema_error or f"expected connecting, got {msg_type}"
                storage.log_event("listener_schema_error", request_id=request_id, msg_type=msg_type, schema_error=reason)
                logger.error("listener_schema_error request_id=%s reason=%s", request_id, reason)
                await send_error(websocket, "SCHEMA_VALIDATION_ERROR", request_id, "listener", listener_id=listener_id)
                return
            payload = state_service.get_payload(first)
            diagnostic_metadata = {
                key: payload.get(key)
                for key in ("client_type", "runner_id", "loader_run_id", "worker_id", "worker_index", "selected_channel_mode")
                if key in payload
            }

            now = state_service.now_ts()
            if now != state_service.listener_connect_sec:
                state_service.listener_connect_sec = now
                state_service.listener_connect_count = 0
            state_service.listener_connect_count += 1

            reject_code = None
            async with state_lock:
                last_connect = state_service.listener_last_connect_by_ip.get(client_ip)
                last_connect_delta_seconds = now - last_connect if last_connect is not None else None
                if (
                    last_connect_delta_seconds is not None
                    and LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS > 0
                    and last_connect_delta_seconds <= LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS
                ):
                    reject_code = "RECONNECT_TOO_FAST"
                if len(state_service.state.listeners) >= state_service.runtime.max_active_listeners:
                    reject_code = "LISTENER_OVERFLOW"
                elif state_service.listener_connect_count > state_service.runtime.max_new_connections_per_sec:
                    reject_code = "CONNECTION_RATE_LIMIT"
                if reject_code is None:
                    state_service.listener_last_connect_by_ip[client_ip] = now
                    listener_id = state_service.add_listener(
                        websocket=websocket,
                        diagnostic_metadata=diagnostic_metadata,
                    ).listener_id
                    storage.log_connection(
                        "listener_connected",
                        listener_id=listener_id,
                        ip=client_ip,
                        client_type=diagnostic_metadata.get("client_type"),
                        runner_id=diagnostic_metadata.get("runner_id"),
                        loader_run_id=diagnostic_metadata.get("loader_run_id"),
                        worker_id=diagnostic_metadata.get("worker_id"),
                    )
                    room_service.persist_all()

            if reject_code:
                state_service.record_listener_reject(reject_code)
                reject_fields = {
                    "reject_code": reject_code,
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "min_reconnect_interval_per_ip_seconds": LISTENER_MIN_RECONNECT_INTERVAL_PER_IP_SECONDS,
                    "last_connect_delta_seconds": last_connect_delta_seconds,
                }
                storage.log_event("listener_rejected", **reject_fields)
                logger.warning("listener_rejected fields=%s", reject_fields)
                await send_error(websocket, reject_code, request_id, "listener", listener_id=listener_id)
                return

            if not log_reachability("listener_livekit_reachability_check", request_id)["ok"]:
                await send_error(websocket, "LIVEKIT_UNAVAILABLE", request_id, "listener", listener_id=listener_id)
                return

            await send_connect_success(
                websocket,
                "listener",
                room_service.create_livekit_token(listener_id),
                request_id or state_service.next_request_id("lst-connect"),
                listener_id=listener_id,
            )

            while True:
                msg = await websocket.receive_json()
                request_id, msg_type = _message_context(msg)
                schema_error = state_service.validate_message_envelope(msg)
                if schema_error is not None or msg_type not in allowed_types:
                    reason = schema_error or f"unsupported message type: {msg_type}"
                    storage.log_event("listener_schema_error", request_id=request_id, msg_type=msg_type, schema_error=reason)
                    logger.error("listener_schema_error request_id=%s reason=%s", request_id, reason)
                    await send_error(websocket, "SCHEMA_VALIDATION_ERROR", request_id, "listener", listener_id=listener_id)
                    continue
                if msg_type == "heartbeat":
                    payload = state_service.get_payload(msg)
                    async with state_lock:
                        listener_session = state_service.state.listeners.get(listener_id)
                        if listener_session:
                            now_ts = float(state_service.now_ts())
                            listener_session.last_seen_ts = now_ts
                            playback_state = str(payload.get("playback_state") or "")
                            selected_channel = payload.get("selected_channel")
                            listener_session.active_play = playback_state in {"WAITING", "PLAYING"} and isinstance(selected_channel, str) and selected_channel != ""
                            listener_session.selected_channel = selected_channel if listener_session.active_play else None
                            if listener_session.active_play:
                                listener_session.active_play_started = True
                                listener_session.last_heartbeat_ts = now_ts
        except WebSocketDisconnect as exc:
            disconnect_code = exc.code
        except Exception as exc:
            summary = traceback.format_exc()
            storage.log_event(
                "listener_ws_exception",
                listener_id=listener_id,
                exception_type=type(exc).__name__,
                exception_repr=repr(exc),
                traceback_summary=summary,
            )
            logger.exception("listener_ws_exception listener_id=%s", listener_id)
        finally:
            storage.log_connection("listener_ws_disconnect", listener_id=listener_id, close_code=disconnect_code)
            async with state_lock:
                state_service.remove_listener_by_ws(websocket)
                room_service.persist_all()

    return router, broadcast_states
