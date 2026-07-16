# Stage VI legacy snapshot

This folder stores Stage VI completed Publisher artifacts and summary before Stage VII active backend hardening.

Included:
- `publisherv0.4/main.py` — Publisher UI v0.4 source snapshot
- `publisherv0.4/constants.py` — constants/theme/timing snapshot
- `publisherv0.4/models.py` — runtime dataclasses snapshot
- `publisherv0.4/state_store.py` — local persistence snapshot
- `packaging/publisher_onedir.spec` — Stage VI Windows onedir packaging spec
- `packaging/build_windows_onedir.ps1` — Stage VI packaging build script
- `packaging/README.md` — Stage VI packaging/runtime notes

Stage VI completed highlights:
1) module decomposition of Publisher UI
2) JSON memory for IP/PIN/device mapping
3) token refresh/reconnect path and missing LiveKit diagnostics in Publisher logs
4) immutable `i18n_library` receive path on connect/reconnect (Publisher renders `en`)
5) reproducible Windows onedir packaging baseline

Known unresolved items moved to docs:
- see `docs/21_unresolved_bugs.md`
- see `docs/15_open_issues.md`
