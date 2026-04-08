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

No unresolved items remain after this documentation update.

### 15.3 Clarification update (April 8, 2026, follow-up)

По уточнению в чате добавлена явная фиксация:
- immutable `i18n_library` должен отправляться на connect/reconnect не только Listener, но и Publisher;
- реализация этого потока закреплена в ближайших этапах roadmap (Stage VII/IX), а не в дальнем non-priority.
