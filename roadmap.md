# Roadmap for next MVP stages (after successful Stage V)

## Status on June 23, 2026
- Stage V is completed and stable for core multi-publisher / multi-listener baseline.
- Stage VI is completed (Publisher UI hardening).
- Stage VII is completed (backend architecture hardening baseline).
- Stage VIII is completed (Listener room status behavior baseline).
- Stage IX is completed (Listener resilience baseline).
- Stage X is completed (Ubuntu 22.04 LTS single-VPS pilot).
- Stage XI is completed (protocol/engine load and capacity characterization).
- Current active/next stage is Stage XII: Domain HTTPS/WSS mode and MVP launch hardening.

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
- `docs/19_stage_vii_ix_acceptance_checklist_legacy.md` (Stage VII marked PASS).

Canonical behavior now lives in permanent docs (`docs/09_backend.md`, `docs/16_ws_schema_v1.md`, `docs/17_backend_persistence_json_v1.md`, `docs/18_json_import_schema_v1.md`).

---

## Stage VIII — Listener room_status rules finalization (Priority 3)

### Result (completed on April 14, 2026)
Delivered:
1) Listener BLOCKED/CLOSED/OPENED behavior baseline finalized for no-reload transitions;
2) language autodetection and i18n rendering baseline finalized for room/status texts;
3) strict schema v1 protocol cleanup completed (April 15, 2026).

Verification artifact:
- `docs/19_stage_vii_ix_acceptance_checklist_legacy.md` (Stage VIII marked PASS).

Canonical behavior now lives in permanent docs (`docs/10_listener_ui.md`, `docs/16_ws_schema_v1.md`).

---

## Stage IX — Listener resilience & compatibility (Priority 4)

### Result (completed on April 19, 2026)
Delivered:
1) backend-authoritative stale listener session handling finalized;
2) `reconnect_required` protocol path and deterministic reconnect triggers finalized;
3) listener resilience hardening baseline finalized.

Verification artifact:
- `docs/19_stage_vii_ix_acceptance_checklist_legacy.md` (Stage IX marked PASS).

Canonical behavior now lives in permanent docs (`docs/10_listener_ui.md`, `docs/16_ws_schema_v1.md`).

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

### Result (completed)

Stage XI is completed for current MVP pilot risk.

Delivered:
1) Go LiveKit protocol/engine loadgen baseline;
2) VPS metrics analyzer and local backend metrics endpoint baseline;
3) gate-based stress-test specification in `docs/24_stress_tests.md`;
4) useful VPS stress result on cloud.reg.ru VPS, reaching approximately 695 emulated listener participants;
5) conclusion that the tested single-VPS setup is sufficient for current MVP pilot risk.

Observed latest useful result (23.06.2026):
- VPS: cloud.reg.ru, 3 vCPU × 2.2 GHz, NVMe, 3 GB RAM, 10 GB SSD;
- one real Web Listener was open separately and audio did not disappear during observed load;
- peak CPU approximately 22.33%, RAM approximately 2.073 / 2.898 GB, TX approximately 54.937 Mbps.

Limitations:
- not browser/Web Listener mass-load testing;
- not a 2000-listener certificate;
- further scaling characterization is deferred.

Canonical result:
- `docs/24_stress_tests.md`

---

## Stage XII — Domain HTTPS/WSS mode and MVP launch hardening (Priority 7)

### Current tasks
1) Adapt Listener/backend/LiveKit deployment documentation for subdomain work.
2) Preserve two modes: direct-IP pilot test mode and optional domain HTTPS/WSS mode.
3) Document event aliases as same-HTML URL path aliases, not separate rooms.
4) Document one simultaneous hall/event = one VPS for MVP.
5) Add minimal MVP cybersecurity measures.
6) Prepare deploy documentation requirements for later implementation.

### Active domain-mode document
- `docs/20_domain_https_wss_mode.md`

### Exit criteria
- domain-mode documentation is clear enough to guide later deploy implementation;
- direct-IP pilot mode remains explicitly supported;
- minimum security requirements are documented.

---

## Stage XIII — Admin Web UI architecture start (Priority 8)

### Main target
Define and start Admin Web UI architecture and first vertical slice.

### Exit criteria
- first usable Admin UI slice works end-to-end on VPS test environment

---

## Stage XIV — Non-MVP technology review and later hardening (Priority 9)

Broad technology discussions are deferred here unless required by Stage XII domain-mode testing:
- adaptiveStream and dynacast;
- audio packet pacing;
- jitter buffer and packet recovery;
- VPS reset reconnection hardening;
- noise gate and audio processing;
- RMS visualizer improvements;
- statistics/dashboard;
- pre-warm publishing;
- backend real multitrack recording;
- LiveKit version upgrade policy deep review.

---

## Post-MVP deferred items (after Stage XIII/Stage XIV planning, non-priority unless risk escalates)

1) dynamic event-time i18n editing from Admin UI (currently only deploy-time dictionaries)
2) advanced runtime language personalization (backend-side per-listener selection)
