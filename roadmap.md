# Roadmap for next MVP stages (after successful Stage V)

## Status on April 6, 2026
- Stage V is completed and considered stable for core multi-publisher / multi-listener engine up to risky 32 channels.
- Next work is focused on controlled completion and VPS field readiness.

---

## Stage VI — Publisher UI hardening for VPS test (Priority 1)

### Main target
Finish Publisher UI as practical room-technician tool for VPS pilot runs.

### Large-doing steps
1) **Module decomposition (without changing behaviour):**
- split UI widgets/layout from transport logic
- split audio capture/RMS from LiveKit send loop
- split backend protocol client from domain state
- keep existing interlock behaviour unchanged

2) **JSON memory for operator comfort:**
- store/reload last backend IP
- store/reload last PIN
- store/reload channel_id -> selected device mapping
- define safe reset path if JSON is broken

3) **Silent seamless token refresh:**
- refresh publisher token before expiry
- no ON AIR interruption during refresh
- reconnect fallback only if strict refresh fails

4) **Windows .exe packaging:**
- stable build script (single command)
- documented dependencies and artifacts
- smoke-test checklist for clean Windows machine

### Exit criteria
- no manual re-entry of IP/PIN/devices after restart
- token renewal does not stop active audio
- .exe starts and works on target test PCs

---

## Stage VII — Listener room-status rules finalization (Priority 2)

### Main target
Implement strict user behaviour for `BLOCKED` and `CLOSED` room states.

### Large-doing steps
1) **BLOCKED rule:**
- show `custom_text_blocked` banner (white text / red background)
- immediately stop currently playing sound
- keep channel buttons clickable (push/unpush allowed)
- while BLOCKED no sound arrives
- if same button remained pushed, OPENED restores sound automatically

2) **CLOSED rule:**
- show `custom_text_closed` banner (white text / red background)
- stop current sound immediately
- unpush current button
- lock all controls until status changes

3) **Regression verification:**
- existing OPENED behaviour unchanged
- no random autoplay from background events

### Exit criteria
- deterministic status-state-machine behaviour in all transitions

---

## Stage VIII — Listener resilience & safety baseline (Priority 3)

### Main target
Bring Listener web app to stable production-like baseline.

### Large-doing steps
1) seamless listener token refresh without sound cuts
2) local fallback to pinned LiveKit client file near listener JS (CDN backup strategy)
3) race-condition audit and elimination of highest-risk races
4) practical security protocol plan for landing page + backend interaction
5) cross-platform compatibility matrix (desktop/mobile major browsers)

### Exit criteria
- listener survives token rotation and CDN issues
- critical races are documented and either fixed or explicitly deferred with mitigations

---

## Stage IX — Backend operational feature completion (Priority 4)

### Main target
Move backend from test-state to operator-ready state.

### Large-doing steps
1) module decomposition and clearer service boundaries
2) JSON persistence for room data, connections, and events
3) bootstrap room config import from prepared formalized `.csv`
4) multi-track per-channel recording into `recordings/`
5) manual console control commands:
- change `room_status`
- start/stop recording
- change `channel_label`
- change `listen`

### Exit criteria
- restart-safe backend state and operator command workflow documented

---

## Stage X — VPS deployment package & operator manuals (Priority 5)

### Main target
Prepare one-action deployment and clear runbook-level documentation.

### Large-doing steps
1) one-action Ubuntu deploy for livekit + backend + listener (using Stage I successful patterns from `legacy/stage_I`)
2) detailed deploy guide for regular scenarios
3) detailed operations guide:
- console room control
- download recordings
- monitor CPU/RAM/LAN/SSD
- monitor/download logs
4) emergency incident guide with fast step-by-step responses

### Exit criteria
- new operator can deploy and run by following docs only

---

## Stage XI — VPS stress testing program (Priority 6)

### Main target
Validate realistic and extreme load behaviour.

### Large-doing steps
1) stress tool without IP/token limits for synthetic user actions
2) scenario examples: 50 concurrent openings + random PLAY actions
3) multi-machine scaling campaigns to 500–2000 active users
4) VPS telemetry collection, storage, and post-test analysis template

### Exit criteria
- bottlenecks and safe operating envelope measured and documented

---

## Stage XII — Technology discussion and adoption decisions (Priority 7)

### Main target
Run focused engineering discussion before implementation of advanced media features.

### Topics
- full review of `docs/11_security.md`
- adaptiveStream
- dynacast
- audio packet pacing
- jitter buffer / packet recovery
- reconnection and continuation after VPS reset
- noise gate
- audio processing
- RMS visualizer
- statistics
- room dashboard
- pre-warm publishing

### Exit criteria
- for each topic: decision = adopt now / postpone / reject, with reason and risk

---

## Stage XIII — Admin Web UI architecture start (Priority 8)

### Main target
Define and start implementation architecture of Admin Web UI.

### Large-doing steps
1) define MVP Admin UI scope (must-have only)
2) define auth model and role boundaries
3) define backend API/WebSocket contracts
4) define first operator workflows and pages
5) implement thin vertical slice (login -> room status control -> audit log)

### Exit criteria
- first usable Admin UI slice works end-to-end on VPS test environment
