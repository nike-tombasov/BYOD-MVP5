import asyncio
from pathlib import Path

from starlette.requests import Request

from backend.config import DEFAULT_ROOM_CONFIG, derive_max_active_listeners, derive_max_new_connections_per_sec
from backend.persistence.storage import JsonStorage
from backend.services.room_service import RoomService
from backend.services.state_service import RuntimeConfig, StateService
from backend.transport.admin_api import build_admin_router


def make_request(path: str, method: str = "GET", forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "client": ("127.0.0.1", 12345),
    })


def endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def make_router(tmp_path: Path):
    runtime = RuntimeConfig(
        pin=DEFAULT_ROOM_CONFIG["pin"],
        room_name=DEFAULT_ROOM_CONFIG["i18n_library"]["room_name_i18n"]["en"],
        room_status="BLOCKED",
        target_capacity=DEFAULT_ROOM_CONFIG["target_capacity"],
        max_active_listeners=derive_max_active_listeners(DEFAULT_ROOM_CONFIG["target_capacity"]),
        max_new_connections_per_sec=derive_max_new_connections_per_sec(DEFAULT_ROOM_CONFIG["target_capacity"]),
        i18n_library=DEFAULT_ROOM_CONFIG["i18n_library"],
    )
    state_service = StateService(channels=DEFAULT_ROOM_CONFIG["channels"], runtime_config=runtime)
    storage = JsonStorage(
        tmp_path,
        tmp_path / "room_config_v1.json",
        tmp_path / "runtime_state_v1.json",
        tmp_path / "recording_state_v1.json",
    )
    storage.ensure_data_dir()
    room_service = RoomService(state_service=state_service, storage=storage, livekit_url="ws://127.0.0.1:7880")

    async def broadcast_cb():
        return None

    router = build_admin_router(
        state_service=state_service,
        room_service=room_service,
        state_lock=asyncio.Lock(),
        broadcast_cb=broadcast_cb,
    )
    return router, state_service


def run(coro):
    return asyncio.run(coro)


def test_health_is_not_blocked_by_local_only_guard(tmp_path):
    router, _ = make_router(tmp_path)
    health = endpoint(router, "/health", "GET")
    assert run(health()) == {"status": "ok"}


def test_metrics_rejects_non_local_forwarded_for(tmp_path):
    router, _ = make_router(tmp_path)
    metrics = endpoint(router, "/admin/metrics_snapshot", "GET")
    try:
        run(metrics(make_request("/admin/metrics_snapshot", forwarded_for="203.0.113.10")))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("expected local-only rejection")


def test_console_command_accepts_local_status_and_invalid_command(tmp_path):
    router, _ = make_router(tmp_path)
    console = endpoint(router, "/admin/console_command", "POST")

    async def json_status():
        return {"command": "status"}
    req = make_request("/admin/console_command", "POST")
    req.json = json_status
    payload = run(console(req))
    assert payload["ok"] is True
    assert payload["command"] == "status"
    assert "room_status=BLOCKED" in payload["result"]

    async def json_invalid():
        return {"command": "does_not_exist"}
    req2 = make_request("/admin/console_command", "POST")
    req2.json = json_invalid
    assert run(console(req2))["result"] == "Unknown command. Use: help"


def test_console_command_rejects_non_local_request(tmp_path):
    router, _ = make_router(tmp_path)
    console = endpoint(router, "/admin/console_command", "POST")
    req = make_request("/admin/console_command", "POST", forwarded_for="198.51.100.7")
    try:
        run(console(req))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("expected local-only rejection")


def test_console_command_applies_room_status_without_restart(tmp_path):
    router, state_service = make_router(tmp_path)
    console = endpoint(router, "/admin/console_command", "POST")
    for status in ("OPENED", "CLOSED", "BLOCKED"):
        async def json_body(status=status):
            return {"command": f"set_room_status {status}"}
        req = make_request("/admin/console_command", "POST")
        req.json = json_body
        payload = run(console(req))
        assert status in payload["result"]
        assert state_service.runtime.room_status == status


def test_import_json_invalid_input_returns_ok_false(tmp_path):
    router, _ = make_router(tmp_path)
    importer = endpoint(router, "/admin/import_json", "POST")

    class Upload:
        async def read(self):
            return b'{"bad": true}'

    payload = run(importer(make_request("/admin/import_json", "POST"), Upload()))
    assert payload["ok"] is False
    assert payload["errors"]
