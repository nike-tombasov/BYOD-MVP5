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

### 14.2 Current active stage

- **Active:** Stage IX (Listener resilience & compatibility).
- **Why now:** Stage VIII core behavior is closed; next blocking scope is reconnect resilience, SDK wiring, race guards, and browser matrix validation.

### 14.3 Stage VII completion snapshot

Delivered in Stage VII:
1) backend decomposition and clear module boundaries
2) JSON import flow with validation and full replacement apply model
3) JSON persistence + atomic write for non-log files
4) websocket envelope/schema hardening baseline and separated state channels
5) listener protection limits (capacity/rate/reconnect interval)
6) operator console commands for runtime control

Known limitation moved to future features:
- real backend multi-track recording is not implemented yet; current backend only keeps recording state markers.

### 14.4 Current postponements

- Unresolved bug **20.1** is marked as **POSTPONED until VPS pilots end**.
- Real backend recording implementation is moved from Stage VII closure scope to future features.

### 14.5 Confirmed architecture pins

1) Backend remains source of truth for owner/interlock.
2) Backend sends immutable `i18n_library` on connect/reconnect.
3) Backend does not select language per listener.
4) Separated payloads are kept: `publisher_state` and `listener_state`.
5) LiveKit baseline stays pinned to `1.9.11` policy.
