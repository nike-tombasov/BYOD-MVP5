# Stage VIII legacy snapshot

Date: April 15, 2026

This snapshot stores Stage VIII completion baseline after protocol cleanup add-on.

Included:
- `legacy/stage_viii/backend/main.py`
- `legacy/stage_viii/backend/config.py`
- `legacy/stage_viii/backend/models.py`
- `legacy/stage_viii/backend/room_config_json.py`
- `legacy/stage_viii/backend/storage.py`
- `legacy/stage_viii/backend/state_service.py`
- `legacy/stage_viii/backend/room_service.py`
- `legacy/stage_viii/backend/ws_handlers.py`
- `legacy/stage_viii/backend/admin_api.py`
- `legacy/stage_viii/backend/commands.py`
- `legacy/stage_viii/publisher/main.py`
- `legacy/stage_viii/publisher/constants.py`
- `legacy/stage_viii/publisher/models.py`
- `legacy/stage_viii/publisher/state_store.py`
- `legacy/stage_viii/listener/index.html`
- `legacy/stage_viii/listener/listener.js`

Notes:
- Stage VIII core BLOCKED/CLOSED/OPENED behavior and language autodetection are included.
- Stage VIII protocol add-on is included: strict WS schema v1 cleanup across backend/publisher/listener.
