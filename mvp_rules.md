# MVP rules for current stage (Stage X)

## Stage goal
Finish deployment package and operator manuals for VPS.

## Strictly IN scope
1) Deploy package structure and one-action flow for Ubuntu VPS.
2) Operator manuals (normal operations, incidents, rollback).
3) Artifact manifest and version/checksum discipline.
4) Documentation alignment for Stage X deliverables.

## Strictly OUT of scope for Stage X
- real backend multitrack recording implementation (future feature after MVP pilots)
- Admin Web UI implementation
- stress framework implementation (Stage XI)
- major architecture redesign of backend/listener/publisher behavior

## Hard constraints
- Preserve all hard rules from `hard_rules.md`.
- Keep Python `3.11` baseline.
- Keep LiveKit baseline `1.9.11`.
- Keep `track.name == channel_id`.
- selective subscribe only.
- publish only between ON AIR and STOP.
- queue overflow must drop oldest.
- audio format stays 48000 Hz stereo.
- interlock logic must be preserved.
- sound must work after each development step.

## Temporary current-stage constraints
- single-room mode remains acceptable for MVP.
- diagnostics console logging remains enabled.
- no new scope from future stages without explicit approval.

## MVP10 Deployment Topology
Single-node deployment.

All components run on one VPS:
- nginx
- Backend
- LiveKit

No load balancing.
No clustering.
No Kubernetes.
No Docker orchestration.
No external database.

Optimization for scale is out of scope for MVP10.

## Anti-overdevelopment policy
If work is not required for Stage X exit criteria, postpone it to roadmap/future features with a short reason.

## Canonical protocol and architecture note
Stage-specific file (`mvp_rules.md`) must not duplicate permanent protocol canon.
For stable behavior rules use:
- `docs/08_backend.md`
- `docs/09_listener_ui.md`
- `docs/15_ws_schema_v1.md`
