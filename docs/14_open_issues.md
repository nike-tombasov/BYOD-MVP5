## 15. Open issues

Rules for docs/14_open_issues.md:
- This file is updated only by special request.
- All new ambiguities are discussed in chat first.
- Only unresolved items after discussion are written here.
- This file is not a second architecture spec.

### 15.1 Resolution log (short)

Resolved and moved to canonical docs/checklists:
- i18n transport behavior on connect/reconnect;
- separated `publisher_state` / `listener_state` protocol behavior;
- Stage VII-IX WS schema hardening and strict handshake cleanup;
- Listener race-hardening baseline rules.
- Stage X clean Ubuntu 22.04 LTS VPS deployment path;
- required deployment and validation of the pinned Listener SDK file
  `vendor/livekit-client.umd.1.15.13.js`;
- backend and VPS connection diagnostics, including the diagnostics collector;
- visible Publisher connection and exception logging in `logs.txt`;
- Listener request-ID fallback when `crypto.randomUUID` is unavailable on an
  HTTP/IP origin.
- Stage XI uses Protocol/engine load only; browser/Web Listener UI load testing
  is postponed to future Web Listener UI hardening.

Canonical sources:
- `docs/08_backend.md`
- `docs/09_listener_ui.md`
- `docs/15_ws_schema_v1.md`
- `docs/18_stage_vii_ix_acceptance_checklist.md` (verification artifact)
- `docs/21_backend_logging_contract_stage_x.md`
- `deploy/stage_x_ubuntu_pilot/`
- `legacy/stage_x_ubuntu_pilot/` (completed-stage snapshot)

### 15.2 Current unresolved items

1) Maximum stable Listener count on the concrete Stage XI VPS
- determine the largest Listener population that remains stable for the
  selected VPS size and network conditions.

2) Stage XI Analyzer metrics implementation
- collect CPU, RAM, network, WebRTC, LiveKit, and backend metrics throughout
  each load step;
- finalize the exact implementation used to sample and correlate client
  failures with VPS and service behavior.

3) LiveKit API versus backend metrics source
- determine whether LiveKit API metrics are sufficient and reliable for the
  required counts, or whether the planned local-only backend
  `/admin/metrics_snapshot` endpoint is needed.

4) Stage XI pass/fail and degradation contract
- define numeric pass/fail thresholds for connection success, audio behavior,
  latency/jitter, reconnects, errors, and resource use;
- define acceptable degradation and the point at which the VPS is considered
  unstable.

5) JSON strict validation final freeze
- open decision: keep strict regex + reject-all policy or simplify for operator UX in first VPS cycle.

6) Persistence schema versioning format
- open decision: whether dedicated `meta_schema.json` is mandatory in MVP.

7) Migration rules v1->v2
- migration and rollback policy for persistence versions is not finalized.

8) Post-pilot logging contract formalization
- exact logging contract for backend and Publisher UI is not finalized (required events, severity, format, retention, mandatory diagnostics fields).
