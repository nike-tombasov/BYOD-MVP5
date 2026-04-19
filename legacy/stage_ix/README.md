# Stage IX legacy snapshot

This folder stores the Stage IX implementation snapshot.

Scope captured:
- backend stale-session authority for Listener
- listener reconnect_required handling
- listener heartbeat/reconnect UX hardening
- Stage IX docs alignment baseline

Included:
- `legacy/stage_ix/backend/` (copied from `src/backend/` at Stage IX close)
- `legacy/stage_ix/listener/` (copied from `src/listener/` at Stage IX close)

Notes:
- snapshot is reference-only
- current development continues in `src/`
