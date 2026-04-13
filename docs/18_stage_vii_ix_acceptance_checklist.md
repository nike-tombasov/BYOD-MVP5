## 19. Stage VII-IX acceptance checklist (formal)

Purpose:
- provide transparent go/no-go criteria before moving to Stage X deploy focus.

Result statuses:
- `PASS`
- `FAIL`
- `DEFERRED_WITH_RISK_NOTE`

Date of Stage VII closure record: **April 13, 2026**.

---

### 19.1 Stage VII — Backend hardening

1) WS contract — **PASS**
- `docs/15_ws_schema_v1.md` implemented message-by-message.
- required fields validated.
- deterministic `error.code` behavior for invalid PIN / owner mismatch / schema validation.

2) Snapshot-send lock rule — **PASS**
- confirmed no network send while state lock is held.

3) Persistence — **PASS**
- `docs/16_backend_persistence_json_v1.md` implemented for current backend behavior.
- restart recovery test path documented and used.

4) JSON import — **PASS**
- `docs/17_json_import_schema_v1.md` validation path is active.
- invalid JSON rejected atomically (no partial apply).
- `target_capacity` imported and persisted.
- `i18n_library` imported, persisted, and sent on connect/reconnect to Publisher and Listener.
- restart keeps last imported room metadata.
- new successful JSON import fully replaces old room metadata.

5) Operator commands — **PASS**
- room_status / recording markers / label / listen / override commands work without restart.

6) Recording for Stage VII closure policy — **PASS**
- Stage VII closure decision: real file recording moved to future features after MVP pilots.
- current backend recording state markers/logging are accepted for Stage VII baseline.

---

### 19.2 Stage VIII — Listener BLOCKED/CLOSED behavior

1) BLOCKED
- immediate audio stop.
- buttons remain clickable.
- no audio until OPENED.

2) CLOSED
- immediate audio stop.
- current button unpushed.
- controls locked.

3) OPENED return
- resume without page reload.

4) Emergency override texts
- BLOCKED/CLOSED override applied independently.

---

### 19.3 Stage IX — Listener resilience and compatibility

1) Token reconnect policy
- no unnecessary token request while stable connection.

2) Local SDK wiring
- local pinned SDK `src/listener/vendor/livekit-client.umd.1.15.13.js` is primary path;
- CDN used only as fallback.

3) Race guards
- attach/detach flags and timeout recovery verified by rapid-click tests.

4) Active PLAY heartbeat
- 10 sec heartbeat and 60 sec timeout path verified end-to-end.

5) No-active-PLAY return path
- after background timeout with no active PLAY, return to page triggers auto-reconnect (or auto-reload fallback).

6) Connection recovery state machine
- `CONNECTED` -> `STALE` -> `RECONNECTING` transitions verified for heartbeat timeout / WS disconnect / LiveKit disconnect / token expiry.
- channel button click always works as mandatory reconnect trigger in `STALE`.

7) Mobile system player behavior
- on Android/iOS background pause->play before heartbeat timeout resumes last selected channel.

8) Browser matrix (minimum)
- Chrome latest-1 (Windows, Android)
- Edge latest-1 (Windows)
- Safari latest-1 (iOS/macOS)
- pass criteria: connect, play, channel switch, reconnect, blocked/closed transitions.

---

### 19.4 Mandatory artifacts before Stage X

- filled checklist file with dated results;
- known limitations list with mitigations;
- rollback plan for each failed/deferred item.
