## 19. Stage VII-IX acceptance checklist (formal)

Purpose:
- verification artifact for go/no-go before Stage X;
- this file verifies canon, it does not define primary architecture behavior.

Result statuses:
- `PASS`
- `FAIL`
- `DEFERRED_WITH_RISK_NOTE`

Canonical behavior sources:
- backend: `docs/09_backend.md`
- listener UX/state: `docs/10_listener_ui.md`
- WS wire protocol: `docs/16_ws_schema_v1.md`

Date of Stage VII closure record: **April 13, 2026**.
Date of Stage VIII closure record: **April 14, 2026**.
Date of Stage IX closure record: **April 19, 2026**.

---

### 19.1 Stage VII — Backend hardening (verification)

1) WS contract — **PASS**
- schema v1 implemented and validated against canonical WS doc.

2) Snapshot-send lock rule — **PASS**
- verified no network send while state lock is held.

3) Persistence — **PASS**
- persistence schema + restart recovery verified.

4) JSON import — **PASS**
- atomic validation/apply behavior verified;
- successful import fully replaces previous metadata snapshot;
- i18n library persisted and sent on connect/reconnect.

5) Operator commands — **PASS**
- room status / recording markers / labels / listen switches work without restart.

6) Recording policy for Stage VII closure — **PASS**
- real backend file recording deferred to future features after MVP pilots;
- current baseline keeps only recording markers/placeholders.

---

### 19.2 Stage VIII — Listener room_status behavior (verification)

1) BLOCKED path — **PASS**
2) CLOSED path — **PASS**
3) OPENED return without reload — **PASS**
4) Immutable i18n status text rendering — **PASS**
5) WS schema v1 cleanup + legacy removal — **PASS**

All checks verified against canonical listener/WS docs.

---

### 19.3 Stage IX — Listener resilience/compatibility (verification)

1) Token reconnect policy — **PASS**
2) Local pinned SDK wiring — **PASS**
3) Attach/detach race guards — **PASS**
4) Active PLAY heartbeat timeout flow — **PASS**
5) No-active-PLAY return path — **PASS**
6) Recovery state machine and reconnect triggers — **PASS**
7) Mobile system player behavior baseline — **PASS**
8) Browser matrix baseline — **PASS**

All checks verified against canonical listener/WS docs.

---

### 19.4 Mandatory artifacts before Stage X

- filled checklist file with dated results;
- known limitations list with mitigations;
- rollback plan for each failed/deferred item.
