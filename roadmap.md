# Roadmap for next MVP stages (after successful Stage V)

## Status on June 15, 2026
- Stage V is completed and stable for core multi-publisher / multi-listener baseline.
- Stage VI is completed (Publisher UI hardening).
- Stage VII is completed (backend architecture hardening baseline).
- Stage VIII is completed (Listener room status behavior baseline).
- Stage IX is completed (Listener resilience baseline).
- Stage X is completed (Ubuntu 22.04 LTS single-VPS pilot).
- Next planned stage is Stage XI: load and capacity characterization on a
  concrete VPS.

---

## Stage VI — Publisher UI hardening for VPS test (Priority 1)

### Result (completed)
- Publisher UI module decomposition completed (v0.4 baseline artifacts saved to legacy).
- JSON memory for IP/PIN/device mapping completed.
- token refresh/reconnect path completed.
- immutable `i18n_library` receive path completed (Publisher renders `en`).
- Windows `.exe` packaging baseline completed (MVP onedir).

---

## Stage VII — Backend hardening before Listener status tests (Priority 2)

### Result (completed)
Delivered:
1) backend decomposition completed;
2) JSON import + JSON persistence flow delivered;
3) WS schema hardening baseline delivered;
4) operator console commands delivered.

Deferred by decision:
- real backend multi-track recording moved to future features after MVP pilots.

Verification artifact:
- `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VII marked PASS).

Canonical behavior now lives in permanent docs (`docs/08_backend.md`, `docs/15_ws_schema_v1.md`, `docs/16_backend_persistence_json_v1.md`, `docs/17_json_import_schema_v1.md`).

---

## Stage VIII — Listener room_status rules finalization (Priority 3)

### Result (completed on April 14, 2026)
Delivered:
1) Listener BLOCKED/CLOSED/OPENED behavior baseline finalized for no-reload transitions;
2) language autodetection and i18n rendering baseline finalized for room/status texts;
3) strict schema v1 protocol cleanup completed (April 15, 2026).

Verification artifact:
- `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VIII marked PASS).

Canonical behavior now lives in permanent docs (`docs/09_listener_ui.md`, `docs/15_ws_schema_v1.md`).

---

## Stage IX — Listener resilience & compatibility (Priority 4)

### Result (completed on April 19, 2026)
Delivered:
1) backend-authoritative stale listener session handling finalized;
2) `reconnect_required` protocol path and deterministic reconnect triggers finalized;
3) listener resilience hardening baseline finalized.

Verification artifact:
- `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage IX marked PASS).

Canonical behavior now lives in permanent docs (`docs/09_listener_ui.md`, `docs/15_ws_schema_v1.md`).

---

## Stage X — VPS deploy package & operator manuals (Priority 5)

### Result (completed)

The Ubuntu Server 22.04 LTS single-VPS pilot was deployed and manually
verified on a clean VPS.

Delivered and verified:

1) a clean Ubuntu 22.04 LTS VPS deploy path exists;
2) nginx serves the Listener and proxies backend WebSockets;
3) the backend stays private on `127.0.0.1:8000` and runs as a systemd service;
4) self-hosted LiveKit runs as a systemd service;
5) Publisher and Listener connect successfully through the public nginx path;
6) the backend issues LiveKit tokens;
7) the audio engine works in the deployed VPS environment;
8) the pinned Listener vendor SDK is validated during deployment;
9) VPS diagnostics and connection troubleshooting procedures were added.

Historical snapshot:
- `legacy/stage_x_ubuntu_pilot/`

Canonical deploy package:
- `deploy/stage_x_ubuntu_pilot/`

---

## Stage XI — Load and Capacity Characterization on a Concrete VPS (Priority 6)

### Status
Planned only; not implemented.

### Main target
Measure the stable operating envelope and degradation behavior of the concrete
single-VPS pilot environment.

### Planned work
1) determine the maximum stable Listener count on the selected VPS;
2) define realistic browser-based and protocol-level load-test roles;
3) collect CPU, RAM, network, WebRTC, LiveKit, and backend metrics under load;
4) define numeric pass/fail thresholds and expected degradation behavior;
5) produce a reproducible test procedure and results report for that VPS.

### Exit criteria
- bottlenecks, pass/fail thresholds, degradation behavior, and a safe operating
  envelope are measured and documented for the tested VPS

---

## Stage XII — Technology discussion and decisions (Priority 7)

Topics:
- full review of `docs/11_security.md`
- adaptiveStream, dynacast, audio packet pacing
- jitter buffer / packet recovery
- reconnection after VPS reset
- noise gate, audio processing, RMS visualizer
- statistics, room dashboard, pre-warm publishing
- backend real multi-track recording and recording file management policy
- LiveKit version policy matrix and upgrade rules:
  - server version policy
  - Python SDK/API compatibility matrix
  - Listener JS SDK pinned local artifact version

### Exit criteria
- each topic has decision: adopt now / postpone / reject (with reason)

---

## Stage XIII — Admin Web UI architecture start (Priority 8)

### Main target
Define and start Admin Web UI architecture and first vertical slice.

### Exit criteria
- first usable Admin UI slice works end-to-end on VPS test environment

---

## Post-MVP deferred items (after Stage XIII, non-priority unless risk escalates)

1) dynamic event-time i18n editing from Admin UI (currently only deploy-time dictionaries)
2) advanced runtime language personalization (backend-side per-listener selection)
