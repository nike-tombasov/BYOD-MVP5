# MVP rules for MVP after Stage XI

## Current status
Stage X is completed: the Ubuntu 22.04 LTS single-VPS deploy package and
operator manuals were verified in a real VPS pilot. Stage XI is completed for
current MVP pilot risk: protocol/engine load characterization produced useful
single-VPS capacity signals, not a browser mass-load certificate.

## Completed Stage X scope
1) Deploy package structure and one-action flow for Ubuntu VPS.
2) Operator manuals (normal operations, incidents, rollback).
3) Artifact manifest and version/checksum discipline.
4) Documentation alignment for Stage X deliverables.

## Strictly OUT of scope for the completed Stage XI baseline
- real backend multitrack recording implementation (future feature after MVP pilots)
- Admin Web UI implementation
- browser/Web Listener mass-load certificate claims
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

## MVP deployment topology
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

Optimization for scale is out of scope for the current MVP.

## Anti-overdevelopment policy
If work is not required for the current stage exit criteria, postpone it to roadmap/future features with a short reason.

## Stage XII scope note
Stage XII documents optional domain HTTPS/WSS mode while preserving direct-IP
pilot mode. Event aliases are URL path aliases only, not separate rooms. For
MVP operations, one simultaneous hall/event equals one VPS. Future technology
topics remain future unless required by practical domain-mode testing.

## Canonical protocol and architecture note
Stage-specific file (`mvp_rules.md`) must not duplicate permanent protocol canon.
For stable behavior rules use:
- `docs/09_backend.md`
- `docs/10_listener_ui.md`
- `docs/16_ws_schema_v1.md`
