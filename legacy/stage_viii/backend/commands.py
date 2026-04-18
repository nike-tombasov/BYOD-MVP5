from __future__ import annotations

import asyncio
from typing import Any

from backend.services.room_service import RoomService
from backend.services.state_service import StateService


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
    )


async def process_console_command(
    line: str,
    state_service: StateService,
    room_service: RoomService,
    state_lock: Any,
    broadcast_cb: Any,
    send_json_safe: Any,
) -> str:
    parts = line.strip().split()
    if not parts:
        return "Empty command. Use: help"
    cmd = parts[0].lower()

    if cmd == "help":
        return format_console_help()

    if cmd == "status":
        runtime = state_service.runtime
        return (
            f"room_status={runtime.room_status}, recording_active={state_service.recording_active}, "
            f"channels={len(state_service.state.channels)}, publishers={len(state_service.state.publishers)}, "
            f"listeners={len(state_service.state.listeners)}, target_capacity={runtime.target_capacity}, "
            f"max_active_listeners={runtime.max_active_listeners}, "
            f"max_new_connections_per_sec={runtime.max_new_connections_per_sec}"
        )

    if cmd == "set_room_status" and len(parts) == 2:
        async with state_lock:
            ok = await room_service.set_room_status_locked(parts[1].upper(), reason="console")
            if not ok:
                return "Invalid status. Use OPENED, BLOCKED, or CLOSED."
            room_service.persist_all()
        await broadcast_cb()
        return f"room_status changed to {state_service.runtime.room_status}"

    if cmd == "start_recording":
        async with state_lock:
            await room_service.start_recording_locked(reason="console")
            room_service.persist_all()
        return "recording started"

    if cmd == "stop_recording":
        async with state_lock:
            await room_service.stop_recording_locked(reason="console")
            room_service.persist_all()
        return "recording stopped"

    if cmd == "set_channel_label" and len(parts) >= 3:
        channel_id = parts[1]
        new_label = " ".join(parts[2:]).strip()
        async with state_lock:
            channel = state_service.find_channel(channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            channel["channel_label"] = new_label
            room_service.persist_all()
            room_service.storage.log_event("channel_label_changed", channel_id=channel_id, channel_label=new_label, actor="console")
        await broadcast_cb()
        return f"{channel_id} label updated"

    if cmd == "set_listen" and len(parts) == 3:
        channel_id = parts[1]
        value = parts[2].lower()
        if value not in {"true", "false"}:
            return "set_listen value must be true or false."
        listen_value = value == "true"
        async with state_lock:
            channel = state_service.find_channel(channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            channel["listen"] = listen_value
            room_service.persist_all()
            room_service.storage.log_event("channel_listen_changed", channel_id=channel_id, listen=listen_value, actor="console")
        await broadcast_cb()
        return f"{channel_id} listen set to {value}"

    if cmd == "off_air" and len(parts) == 2:
        channel_id = parts[1]
        owner_ws = None
        async with state_lock:
            channel = state_service.find_channel(channel_id)
            if channel is None:
                return f"Unknown channel_id: {channel_id}"
            previous_owner = channel.get("owner")
            channel["owner"] = None
            channel["off_air_ts"] = state_service.now_ts()
            room_service.persist_all()
            room_service.storage.log_event("off_air_forced", channel_id=channel_id, previous_owner=previous_owner, actor="console")
            if previous_owner and previous_owner in state_service.state.publishers:
                owner_ws = state_service.state.publishers[previous_owner].websocket
        if owner_ws is not None:
            await send_json_safe(
                owner_ws,
                state_service.make_envelope("force_off_air", {"channel_id": channel_id, "reason": "console_off_air"}),
            )
        await broadcast_cb()
        return f"{channel_id} owner cleared"

    return "Unknown command. Use: help"


async def console_command_loop(
    state_service: StateService,
    room_service: RoomService,
    state_lock: Any,
    broadcast_cb: Any,
    send_json_safe: Any,
) -> None:
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

        result = await process_console_command(
            line=line,
            state_service=state_service,
            room_service=room_service,
            state_lock=state_lock,
            broadcast_cb=broadcast_cb,
            send_json_safe=send_json_safe,
        )
        print(f"[backend] {result}")
