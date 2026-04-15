# MVP rules for current stage (Stage IX)

## Stage goal
Finalize Listener resilience and compatibility baseline on top of completed Stage VIII room-status behavior.

## Strictly IN scope
1) Listener reconnect policy and token refresh only when reconnect is required.
2) Listener local pinned SDK wiring and fallback strategy validation.
3) Listener race hardening and deterministic attach/detach guards.
4) Active PLAY heartbeat and timeout recovery flow.
5) Stage IX checklist evidence updates and documentation sync.

## Strictly OUT of scope for Stage IX
- real backend multitrack recording implementation (moved to future features after MVP pilots)
- Admin Web UI implementation
- security stack implementation (rate-limit/CDN/WAF full stack)
- stress-test framework implementation
- large deploy automation changes

## Hard constraints
- Preserve all hard rules from `hard_rules.md`.
- Keep LiveKit version focus: `1.9.11`.
- Do not break completed Stage VII/VIII behavior.
- Sound must work after each development step.
- Any refactor must include behavior check after step.

## Temporary fixed values (until changed by dedicated stage)
- single-room mode is acceptable for MVP.
- diagnostics console logging remains enabled.
- immutable deploy/import `i18n_library` remains baseline.

## Anti-overdevelopment policy
If task is not required for Stage VIII exit criteria, postpone it to roadmap/future features with a short reason.
If task is not required for Stage IX exit criteria, postpone it to roadmap/future features with a short reason.

## Pinned protocol decisions
- Backend state transport uses separated payloads: `publisher_state` and `listener_state`.
- Backend remains source of truth for channel ownership/interlock.
- Backend sends full immutable `i18n_library` on connect/reconnect.
- Backend does not select language per user.
