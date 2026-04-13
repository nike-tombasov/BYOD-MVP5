from typing import Any


def build_import_result(room_name: str, target_capacity: int, max_active_listeners: int, max_new_connections_per_sec: int, channels_count: int) -> dict[str, Any]:
    return {
        "ok": True,
        "applied": {
            "room_name": room_name,
            "target_capacity": target_capacity,
            "max_active_listeners": max_active_listeners,
            "max_new_connections_per_sec": max_new_connections_per_sec,
            "channels": channels_count,
        },
    }
