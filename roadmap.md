# Roadmap for next MVP stages (after successful Stage V)

## Status on April 14, 2026
- Stage V is completed and stable for core multi-publisher / multi-listener baseline.
- Stage VI is completed (Publisher UI hardening).
- Stage VII is completed (backend decomposition, JSON import/persistence, WS hardening baseline, operator commands, listener protection).
- Stage VIII is completed with one deferred nonprofit item (Listener override restore).
- Active stage is Stage IX.

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
Short conclusion:
1) backend monolith decomposition completed;
2) JSON persistence + JSON import flow completed;
3) WS envelope/state compatibility checks and listener protection completed;
4) operator console commands completed.

Note:
- real backend multi-track recording was intentionally moved to future features after MVP pilot cycle.

Checklist artifact:
- `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VII marked PASS).

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
- if in BLOCKED button channel pushed (highlighted) and status changes to OPENED sound of the channel must starts immidietly.

5) override behavior
- override blocked listener behaviour works as well as main blocked but using overrided text;
- override closed listener behaviour works as well as main closed but using overrided text;
- override do not stops/starts recording.  

6) autodetection users system language
- autodetection must take from i18n library only corresponding language set for room_name and statuses or fallback to default language (en);
- add to current page logging of autodetected users system language name;
- if users system language unknown and language going to be default (en) log the fact;
- if users system language absent in i18n library and language going to be default (en) log the fact.

### Exit criteria
- deterministic behavior for OPENED/BLOCKED/CLOSED transitions without page reload
- correct override behavior
- corresponding language set from i18n library by language autodetection
- checklist artifact: `docs/18_stage_vii_ix_acceptance_checklist.md` (Stage VIII section)

### Result (completed on April 14, 2026)
Delivered:
1) Listener BLOCKED/CLOSED/OPENED behavior baseline finalized for no-reload transitions;
2) language autodetection and i18n rendering baseline finalized for room/status texts;
3) checklist updated with Stage VIII pass marks.

Deferred nonprofit item:
- Listener runtime override text restoration is deferred with risk note and moved to open issues.

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

1) dynamic event-time i18n editing from Admin UI (currently only deploy-time dictionaries + override)
2) advanced runtime language personalization (backend-side per-listener selection)
