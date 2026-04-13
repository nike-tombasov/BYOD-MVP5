# Roadmap for next MVP stages (after successful Stage V)

## Status on April 7, 2026
- Stage V is completed and considered stable for core multi-publisher / multi-listener engine up to risky 32 channels.
- Stage dependency update: Listener room_status behavior validation depends on backend console commands.

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

### Main target
Finish backend baseline MVP develop 
for VPS pilot runs.

### Large-doing steps
1) backend module decomposition and service boundaries
2) JSON persistence for room data / connections / events
   - schema: `docs/16_backend_persistence_json_v1.md`
   - restart must keep last imported room metadata (bootstrap defaults only before first successful import)
3) admin import of initial room data from formalized `.csv`
   - schema: `docs/17_csv_import_schema_v1.md`
   - includes required immutable i18n library headers (`en`/`ru`) for room and status texts
4) manual console commands:
- change `room_status`
- start/stop recording
- change `channel_label`
- change `listen`
5) channel multi-track recording to `recordings/`
6) listener overflow protection (backend side):
- hard limit `max_active_listeners = target_capacity * 1.05`
- connection rate-limit: max `target_capacity / 15` new connections per second
- minimal reconnect interval per listener: > 2 sec
7) compatibility checks for separated WS states:
- backend <-> publisher (`publisher_state`)
- backend <-> listener (`listener_state`)
8) emergency override manual console command
9) websocket broadcast lock policy fix in backend event loop:
- `lock -> copy immutable snapshot -> unlock -> send`
- network sending is forbidden while state lock is held
10) formal WS schema document (v1):
- message types, required fields, validation rules
- compatibility checklist for `publisher_state` and `listener_state`
- canonical file: `docs/15_ws_schema_v1.md`
11) immutable i18n library transport (must be implemented within near stages):
- backend sends `i18n_library` payload to both Publisher and Listener on initial WS connect and reconnect
- base deploy dictionaries are immutable during event runtime
- emergency override remains separate runtime overlay mechanism

### Exit criteria
- operator can change room status and verify effects without code edits/restarts
- compatibility checks for both state channels are passed by formal acceptance checklist document
- checklist artifact: `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VII section)

---

## Stage VIII — Listener room_status rules finalization (Priority 3)

### Main target
Implement strict user behavior for `BLOCKED` and `CLOSED` room states.

### Large-doing steps
1) receiving immutable i18n library on initial WS connect and reconnect

2) **BLOCKED rule:**
- show `custom_status_text_blocked_i18n` banner (white text / red background) using language selection rule
- stop current sound immediately
- keep channel buttons clickable (push/unpush allowed)
- while BLOCKED no sound arrives

3) **CLOSED rule:**
- show `custom_status_text_closed_i18n` banner (white text / red background) using language selection rule
- stop current sound immediately
- unpush current button
- lock all controls until status changes
- while CLOSED no sound arrives

4) **OPENED return rule (required for both BLOCKED and CLOSED paths):**
- after return to `room_status = OPENED`, Listener sound/subscription engine must resume working without page reload
- listener keeps operating with current page session and current websocket/livekit lifecycle

5) emergency override behavior

### Exit criteria
- deterministic behavior for OPENED/BLOCKED/CLOSED transitions without page reload
- checklist artifact: `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VIII section)

---

## Stage IX — Listener resilience & compatibility (Priority 4)

### Main target
Bring Listener web app to stable production-like baseline.

### Large-doing steps
1) listener token policy: request new token only when reconnect is required
2) local pinned LiveKit client file near listener JS
3) race-condition audit and elimination of highest-risk races
4) security protocol plan for landing page and backend interaction
5) active PLAY heartbeat control (`10 sec` heartbeat, `60 sec` timeout -> reconnect required)
   - include return-from-background path: no-active-PLAY timeout must recover via auto-reconnect (or auto page reload fallback)
   - follow Listener connection recovery rules: `docs/09_listener_ui.md` section 10.10.1
   - implement Listener connection-state UX messages: `CONNECTING` / `RETRYING` / `UNAVAILABLE`
6) cross-platform compatibility matrix (desktop/mobile major browsers)
7) strict attach/detach race guards implementation:
- `attachInProgress` / `detachInProgress`
- operation timeout and deterministic state reset to `IDLE`
- rapid-click burst test cases
8) verify reconnect behavior with immutable i18n library:
- Listener restores texts without page reload after reconnect
9) Listener local SDK wiring:
- connect local pinned file `src/listener/vendor/livekit-client.umd.1.15.13.js` in Listener script/html

### Exit criteria
- listener survives token rotation
- critical races are fixed or formally deferred with mitigations
- checklist artifact: `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage IX section)

---

## Stage X — VPS deploy package & operator manuals (Priority 5)

### Main target
Prepare one-action deployment and clear runbook documentation.

### Large-doing steps
1) one-action Ubuntu deploy for livekit + backend + listener (from `legacy/stage_I` lessons)
2) detailed deploy guide for regular scenarios
3) detailed operations guide (console control, recordings, metrics, logs)
4) emergency incident guide with step-by-step actions
5) LiveKit binary delivery policy for Ubuntu VPS:
- preferred: pinned own artifact (exact version) with checksum verification
- fallback: `curl` from official release URL with checksum verification
- document rollback procedure to previous pinned binary

### Exit criteria
- new operator can deploy and operate by docs only

---

## Stage XI — VPS stress test program (Priority 6)

### Main target
Validate realistic and extreme load behavior.

### Large-doing steps
1) stress tool without IP/token limits for synthetic user actions
2) scenario: 50 concurrent page opens + random PLAY actions
3) multi-machine scaling to 500–2000 active users
4) telemetry collection + post-test analysis template

### Exit criteria
- bottlenecks and safe operating envelope measured and documented

---

## Stage XII — Technology discussion and decisions (Priority 7)

Topics:
- full review of `docs/11_security.md`
- adaptiveStream, dynacast, audio packet pacing
- jitter buffer / packet recovery
- reconnection after VPS reset
- noise gate, audio processing, RMS visualizer
- statistics, room dashboard, pre-warm publishing
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

1) dynamic event-time i18n editing from Admin UI (currently only deploy-time dictionaries + emergency override)
2) advanced runtime language personalization (backend-side per-listener selection)
