# About folder /legacy

Folder /legacy contains legacy experimental implementations.

## Rules:
- Do not reuse directly
- Use only as reference
- Current architecture is defined in architecture.md
- Legacy code may violate current rules
- Do not make any changes in past Stages

## Stage I

First and only try with real VPS. 

In the end of this Stage I no errors/bugs were occurred during tests with python console Publisher and Listener UI (VPS based)

Include:
* legacy/stage_I/deployment.md
* legacy/stage_I/index.html
* legacy/stage_I/publisher.py

## Stage IV

Well done working Publisher UI v0.2 and Listener UI without backend (only LiveKit Server), without multi-publisher room

In the end of this Stage IV no errors/bugs were occurred during tests with Publisher UI and Listener UI (localhost)

Include:
* legacy/stage_IV/index.html
* legacy/stage_IV/ui_test_livekit.py
* legacy/stage_IV/audio_steam.py
* legacy/stage_IV/rms_detector.py

## Stage V

Stage V delivered the first stable multi-publisher + multi-listener baseline with interlock ownership and risky up-to-32 channels operation.

Stage V result analysis (short):
- core owner/interlock model worked and backend remained source of truth;
- Publisher v0.3 was practical baseline before hardening;
- unresolved risks were mostly around token lifecycle, race hardening, and formal WS contracts, then moved to next-stage work and docs.

Include:
* legacy/stage_v/README.md
* legacy/stage_v/publisherv0.3/main.py
* legacy/stage_v/backend/main.py
* legacy/stage_v/listener/index.html
* legacy/stage_v/listener/listener.js
* legacy/stage_v/roadmap_stage_v_completed.md
* legacy/stage_v/mvp_rules_stage_v.md
* legacy/stage_v/13_mvp_status_stage_v.md
* legacy/stage_v/14_open_issues_stage_v.md

## Stage VI

Stage VI completed Publisher UI hardening baseline (v0.4) with module decomposition, local JSON memory, token/i18n handling path, and Windows packaging baseline.

Include:
* legacy/stage_vi/README.md
* legacy/stage_vi/publisherv0.4/main.py
* legacy/stage_vi/publisherv0.4/constants.py
* legacy/stage_vi/publisherv0.4/models.py
* legacy/stage_vi/publisherv0.4/state_store.py
* legacy/stage_vi/packaging/publisher_onedir.spec
* legacy/stage_vi/packaging/build_windows_onedir.ps1
* legacy/stage_vi/packaging/README.md

## Stage VII

Stage VII completed backend hardening baseline with decomposition, JSON import/persistence, WS baseline hardening, listener protections, and operator command set.

Include:
* legacy/stage_vii/README.md
* legacy/stage_vii/backend/main.py
* legacy/stage_vii/backend/config.py
* legacy/stage_vii/backend/domain/models.py
* legacy/stage_vii/backend/importers/room_config_json.py
* legacy/stage_vii/backend/persistence/storage.py
* legacy/stage_vii/backend/services/state_service.py
* legacy/stage_vii/backend/services/room_service.py
* legacy/stage_vii/backend/transport/admin_api.py
* legacy/stage_vii/backend/transport/ws_handlers.py
* legacy/stage_vii/backend/console/commands.py

## Stage VIII

Stage VIII completed Listener room-status behavior baseline (`OPENED`/`BLOCKED`/`CLOSED`), language autodetection path, and final WS schema v1 protocol cleanup add-on across backend/publisher/listener.

Include:
* legacy/stage_viii/README.md
* legacy/stage_viii/backend/main.py
* legacy/stage_viii/backend/config.py
* legacy/stage_viii/backend/models.py
* legacy/stage_viii/backend/room_config_json.py
* legacy/stage_viii/backend/storage.py
* legacy/stage_viii/backend/state_service.py
* legacy/stage_viii/backend/room_service.py
* legacy/stage_viii/backend/ws_handlers.py
* legacy/stage_viii/backend/admin_api.py
* legacy/stage_viii/backend/commands.py
* legacy/stage_viii/publisher/main.py
* legacy/stage_viii/publisher/constants.py
* legacy/stage_viii/publisher/models.py
* legacy/stage_viii/publisher/state_store.py
* legacy/stage_viii/listener/index.html
* legacy/stage_viii/listener/listener.js

## Stage IX

Stage IX completed Listener resilience & compatibility baseline with backend-authoritative stale-session handling and deterministic reconnect behavior.

Include:
* legacy/stage_ix/README.md
* legacy/stage_ix/backend/main.py
* legacy/stage_ix/backend/config.py
* legacy/stage_ix/backend/domain/models.py
* legacy/stage_ix/backend/services/state_service.py
* legacy/stage_ix/backend/services/room_service.py
* legacy/stage_ix/backend/transport/ws_handlers.py
* legacy/stage_ix/backend/transport/admin_api.py
* legacy/stage_ix/listener/index.html
* legacy/stage_ix/listener/listener.js
