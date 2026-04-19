## 15. Open issues

Rules for docs/14_open_issues.md:
- This file is updated only by special request.
- All new ambiguities are discussed in chat first.
- Only unresolved items after discussion are written here.

### 15.1 Resolution log (April 8, 2026)

By decision, previous items 15.1–15.8 are moved out of open unresolved backlog:

1) Minor mismatches (heartbeats / `channel_0 listen=false` / deploy default `room_status=CLOSED` / JWT lifetime consistency)
- moved to active workflow and acceptance checks in `roadmap.md` Stage VII + Stage IX;
- canonical behavior remains pinned in `docs/04_channel_model.md`, `docs/08_backend.md`, `docs/10_scaling.md`.

2) LiveKit versions policy
- resolved by explicit pinned compatibility matrix in `hard_rules.md` and `docs/06_livekit_engine.md`;
- Listener fallback version pin added in `docs/09_listener_ui.md`.

3) Backend lock during WS send
- resolved at specification level in `docs/08_backend.md` (mandatory snapshot-send rule).

4) Thread safety Qt (Publisher)
- resolved at specification level in `docs/07_publisher_ui.md` (UI-thread-only widget access rule).

5) LiveKit API key / secret policy
- resolved at specification level in `docs/08_backend.md` (`LIVEKIT_API_SECRET` length `>32`, deploy-time auto-generation, synced persistence in backend + `livekit.yaml`).

6) i18n payload multi-language model
- already specified; additionally formalized in active workflow and deferred backlog split:
  - active MVP behavior remains in `docs/08_backend.md` + `docs/09_listener_ui.md`;
  - post-Stage XIII non-priority dynamic personalization tracked in `roadmap.md`.

7) Listener race guards
- escalated as mandatory Stage IX hardening item in `roadmap.md`; normative rules remain in `docs/09_listener_ui.md`.

8) Formal strict WS schema
- added to active MVP workflow as Stage VII deliverable in `roadmap.md`;
- temporary strict runtime validation requirement added in `docs/08_backend.md`.

### 15.2 Current unresolved items

1) Deploy artifact manifest is not fully formalized yet (pre-Stage X blocker):
- exact manifest structure for release bundle is not pinned (artifacts list, versions, checksums, signatures, required/optional flags);
- verification/rollback procedure must reference that manifest as single source of truth.

2) Stress program formalization is incomplete (Stage XI preparation gap):
- missing strict metrics set (latency/jitter/reconnect/error budget/CPU-RAM thresholds);
- missing pass/fail numeric thresholds and mandatory report template fields.

3) JSON strict validation rules are still open for final freeze:
- whether to keep strict regex/atomic reject-all policy or simplify for operator UX in first VPS cycle.

4) Persistence schema versioning format is still open:
- whether dedicated `meta_schema.json` is mandatory in MVP or can be postponed to next cycle.

5) Migration rules are still open:
- policy for v1->v2 persistence migration and rollback is not finalized for current stage.

### 15.3 Clarification update (April 8, 2026, follow-up)

По уточнению в чате добавлена явная фиксация:
- immutable `i18n_library` должен отправляться на connect/reconnect не только Listener, но и Publisher;
- реализация этого потока закреплена в ближайших этапах roadmap (Stage VII/IX), а не в дальнем non-priority.
- локальный pinned Listener SDK path фиксируется как `src/listener/vendor/livekit-client.umd.1.15.13.js`, подключение в Listener обязательно в ближайших этапах roadmap.

### 15.4 New TO-DO issues (April 11, 2026)

1) Backend logging gap on publish path when LiveKit Server is unavailable:
- add explicit backend-side logging when publish request cannot be completed due to missing/unreachable LiveKit Server.

2) Logging contracts are not formally fixed:
- define exact logging contract for Publisher UI and backend (minimum required events, severity model, format, retention, and mandatory diagnostics fields).

