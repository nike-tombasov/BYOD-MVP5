## 14. MVP status (updated)

### 14.1 Stage summary

- **Stage I** — VPS first successful chain (legacy baseline) — **DONE**.
- **Stage II** — expanded redesign attempt — **FAILED** (version/architecture mismatch).
- **Stage III** — simplified publisher recovery stage — **DONE**.
- **Stage IV** — gradual Publisher UI v0.2 stabilization — **DONE**.
- **Stage V** — multi-publisher + multi-listener + up to risky 32 channels with interlock logic — **DONE**.
- **Stage VI** — Publisher UI hardening for VPS pilot — **DONE**.
- **Stage VII** — Backend hardening baseline — **DONE** (April 13, 2026).
- **Stage VIII** — Listener room_status rules finalization — **DONE** (April 14, 2026).
- **Stage IX** — Listener resilience & compatibility — **DONE** (April 19, 2026).
- **Stage X** — Ubuntu 22.04 LTS single-VPS pilot — **DONE**.
- **Stage XI** — Protocol/engine load and capacity characterization — **DONE** (latest useful result: June 23, 2026).

### 14.2 Current active stage

- **Active/next:** Stage XII (Technology discussion and decisions).
- **Why now:** Stage X deploy packaging and Stage XI MVP-risk load characterization are closed; next scope is architecture/technology decisions and hardening discussion.

### 14.3 Stage VII completion snapshot

Delivered in Stage VII:
1) backend decomposition and clear module boundaries;
2) JSON import + JSON persistence baseline;
3) WS schema hardening baseline;
4) operator console commands for runtime control.

Deferred decision kept:
- real backend multi-track recording is **not** implemented in current MVP baseline;
- current backend keeps only recording state markers/runtime placeholders.

### 14.4 Stage VIII completion snapshot

Delivered in Stage VIII:
1) Listener BLOCKED/CLOSED/OPENED no-reload behavior baseline;
2) listener language autodetection/fallback for i18n texts;
3) WS schema v1 cleanup and removal of legacy formats.

### 14.5 Stage IX completion snapshot

Delivered in Stage IX:
1) backend-authoritative stale listener session handling;
2) canonical `reconnect_required` backend->listener path;
3) deterministic reconnect triggers and availability UX states;
4) race-hardening baseline for listener attach/detach flow.

### 14.6 Stage X completion snapshot

Delivered in Stage X:
1) Ubuntu 22.04 LTS single-VPS deploy package;
2) nginx/backend/LiveKit systemd deployment path;
3) operator diagnostics and troubleshooting baseline.

### 14.7 Stage XI completion snapshot

Delivered in Stage XI:
1) protocol/engine load and capacity characterization completed for current MVP risk;
2) latest useful result documented in `docs/23_stress_tests.md`;
3) approximately 695 emulated listener participants reached on the tested VPS;
4) one real Web Listener remained usable during observed load;
5) browser/Web Listener mass testing was not performed;
6) the 2000-listener target remains future scaling work, not an MVP requirement.

### 14.8 Current postponements

- Unresolved bug **20.1** is **POSTPONED until VPS pilots end**.
- Real backend recording implementation is moved to future features.

### 14.9 Canonical references

This file is a status/history summary.
Normative behavior is pinned in permanent docs:
- backend architecture/semantics: `docs/09_backend.md`;
- listener behavior: `docs/10_listener_ui.md`;
- WS wire protocol: `docs/16_ws_schema_v1.md`;
- LiveKit version baseline: `docs/07_livekit_engine.md`;
- Ubuntu deploy contract: `docs/14_ubuntu_deploy_contract.md`;
- stress-test specification and latest useful result: `docs/23_stress_tests.md`.
