# MVP rules for current stage (Stage VIII)

## Stage goal
Finalize Listener room status behavior (`OPENED` / `BLOCKED` / `CLOSED`) on top of completed Stage VII backend baseline.

## Strictly IN scope
1) Listener behavior for `BLOCKED` and `CLOSED`.
2) Deterministic return to normal flow after status goes back to `OPENED`.
3) Emergency override text behavior validation for Listener UI.
4) Formal Stage VIII checklist evidence updates.
5) Documentation sync for Stage VII closure and Stage VIII activation.

## Strictly OUT of scope for Stage VIII
- real backend multitrack recording implementation (moved to future features after MVP pilots)
- Admin Web UI implementation
- security stack implementation (rate-limit/CDN/WAF full stack)
- stress-test framework implementation
- large deploy automation changes

## Hard constraints
- Preserve all hard rules from `hard_rules.md`.
- Keep LiveKit version focus: `1.9.11`.
- Do not break completed Stage VII backend behavior.
- Sound must work after each development step.
- Any refactor must include behavior check after step.

## Temporary fixed values (until changed by dedicated stage)
- single-room mode is acceptable for MVP.
- diagnostics console logging remains enabled.
- immutable deploy/import `i18n_library` remains baseline.

## Anti-overdevelopment policy
If task is not required for Stage VIII exit criteria, postpone it to roadmap/future features with a short reason.

## Pinned protocol decisions
- Backend state transport uses separated payloads: `publisher_state` and `listener_state`.
- Backend remains source of truth for channel ownership/interlock.
- Backend sends full immutable `i18n_library` on connect/reconnect.
- Backend does not select language per user.
