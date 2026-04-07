# Roadmap for next MVP stages (after successful Stage V)

## Status on April 7, 2026
- Stage V is completed and considered stable for core multi-publisher / multi-listener engine up to risky 32 channels.
- Stage dependency update: Listener room_status behavior validation depends on backend console commands.

---

## Stage VI — Publisher UI hardening for VPS test (Priority 1)

### Main target
Finish Publisher UI as practical room-technician tool for VPS pilot runs.

### Large-doing steps
1) module decomposition (without changing behavior)
2) JSON memory for last IP/PIN/device mapping
3) silent seamless token refresh
4) stable Windows `.exe` packaging (MVP: folder build; production target: one-file build)

### Exit criteria
- no manual re-entry of IP/PIN/devices after restart
- token renewal does not stop active audio
- `.exe` starts and works on target test PCs

---

## Stage VII — Backend hardening before Listener status tests (Priority 2)

### Main target
Deliver backend operator controls required to run real Listener `BLOCKED/CLOSED` tests.

### Large-doing steps
1) backend module decomposition and service boundaries
2) JSON persistence for room data / connections / events
3) admin import of initial room data from formalized `.csv`
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

### Exit criteria
- operator can change room status and verify effects without code edits/restarts
- compatibility checks for both state channels are passed by formal acceptance checklist document

---

## Stage VIII — Listener room_status rules finalization (Priority 3)

### Main target
Implement strict user behavior for `BLOCKED` and `CLOSED` room states.

### Large-doing steps
1) **BLOCKED rule:**
- show `custom_text_blocked` banner (white text / red background)
- stop current sound immediately
- keep channel buttons clickable (push/unpush allowed)
- while BLOCKED no sound arrives

2) **CLOSED rule:**
- show `custom_text_closed` banner (white text / red background)
- stop current sound immediately
- unpush current button
- lock all controls until status changes

3) **OPENED return rule (required for both BLOCKED and CLOSED paths):**
- after return to `room_status = OPENED`, Listener sound/subscription engine must resume working without page reload
- listener keeps operating with current page session and current websocket/livekit lifecycle

4) emergency override behavior

### Exit criteria
- deterministic behavior for OPENED/BLOCKED/CLOSED transitions without page reload

---

## Stage IX — Listener resilience & compatibility (Priority 4)

### Main target
Bring Listener web app to stable production-like baseline.

### Large-doing steps
1) listener token policy: request new token only when reconnect is required
2) local fallback to pinned LiveKit client file near listener JS (CDN backup)
3) race-condition audit and elimination of highest-risk races
4) security protocol plan for landing page and backend interaction
5) active PLAY heartbeat control (`10 sec` heartbeat, `60 sec` timeout -> reconnect required)
6) cross-platform compatibility matrix (desktop/mobile major browsers)

### Exit criteria
- listener survives token rotation and CDN issues
- critical races are fixed or formally deferred with mitigations

---

## Stage X — VPS deploy package & operator manuals (Priority 5)

### Main target
Prepare one-action deployment and clear runbook documentation.

### Large-doing steps
1) one-action Ubuntu deploy for livekit + backend + listener (from `legacy/stage_I` lessons)
2) detailed deploy guide for regular scenarios
3) detailed operations guide (console control, recordings, metrics, logs)
4) emergency incident guide with step-by-step actions

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

### Exit criteria
- each topic has decision: adopt now / postpone / reject (with reason)

---

## Stage XIII — Admin Web UI architecture start (Priority 8)

### Main target
Define and start Admin Web UI architecture and first vertical slice.

### Exit criteria
- first usable Admin UI slice works end-to-end on VPS test environment
