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

Canonical sources:
- `docs/08_backend.md`
- `docs/09_listener_ui.md`
- `docs/15_ws_schema_v1.md`
- `docs/18_stage_vii_ix_acceptance_checklist.md` (verification artifact)

### 15.2 Current unresolved items

1) Deploy artifact manifest formalization (Stage X blocker)
- exact release manifest structure is not pinned yet (artifact list, versions, checksums, signatures, required/optional flags);
- verification and rollback procedure must reference one manifest source of truth.

2) Stress program formalization (Stage XI preparation gap)
- strict metrics set is not finalized (latency/jitter/reconnect/error budget/CPU-RAM thresholds);
- pass/fail numeric thresholds and report template fields are not finalized.

3) JSON strict validation final freeze
- open decision: keep strict regex + reject-all policy or simplify for operator UX in first VPS cycle.

4) Persistence schema versioning format
- open decision: whether dedicated `meta_schema.json` is mandatory in MVP.

5) Migration rules v1->v2
- migration and rollback policy for persistence versions is not finalized.

6) Logging contract formalization
- exact logging contract for backend and Publisher UI is not finalized (required events, severity, format, retention, mandatory diagnostics fields).
