# MVP rules for current stage (Stage VI)

## Stage goal
Publisher UI hardening for VPS pilot test, without uncontrolled feature expansion.

## Strictly IN scope
1) Publisher module decomposition (behaviour-preserving refactor only)
2) JSON memory:
- last backend IP
- last PIN
- channel_id -> device mapping
3) seamless publisher token refresh without audio interruption
4) reproducible Windows `.exe` packaging
5) documentation updates for new workflow

## Strictly OUT of scope for Stage VI
- Listener BLOCKED/CLOSED advanced behaviour changes
- Listener CDN fallback and race overhaul
- backend recording implementation
- admin web UI implementation
- security stack implementation (rate-limit, Cloudflare, etc.)
- stress-test framework implementation
- large-scale performance optimization beyond blocking bugs

## Hard constraints
- Preserve all hard rules from `hard_rules.md`
- Keep LiveKit version focus: `1.9.11`
- Do not break working Stage V engine behaviour
- Sound must work after each development step
- Any refactor must include behaviour check after step

## Temporary fixed values (until changed by dedicated stage)
- PIN may remain fixed for MVP runtime tests
- single room mode remains acceptable
- console logging remains enabled for diagnostics

## Anti-overdevelopment policy
If a task is not required for Stage VI exit criteria, postpone it to next stage and document it in roadmap/open issues.


## Pinned protocol decisions
- Backend state transport uses separated payloads: `publisher_state` and `listener_state`.
- Publisher packaging mode: MVP = folder build, production target = one-file build.
