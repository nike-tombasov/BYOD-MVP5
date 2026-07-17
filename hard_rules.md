# HARD RULES (DO NOT VIOLATE)

* Python v3.11
* LiveKit version: 1.9.11
* track.name == channel_id
* Listener subscribes only to track.name == selected channel_id
* publish only between ON AIR and STOP
* publish only when owner == self publisher_id
* backend is single source of truth for owner assignment
* queue full → drop oldest (non-blocking)
* audio sample rate: 48000 Hz only
* audio channels: stereo
* frame size: 960 samples
* codec: Opus
* selective subscribe only
* autoSubscribe = false
* single audio element for listener session
* Interlock logic must prevent multiple publishers for one channel_id
* Audio device must be opened before ON AIR
* Send frames only after ON AIR
* track created only after publish
* track removed after STOP

## Environment assumptions (MVP10)

Target deployment environment:

- Ubuntu Server 22.04 LTS (Jammy)
- Single VPS
- One public IPv4 address
- No domain name
- No HTTPS/TLS yet
- HTTP only for MVP testing
- LiveKit self-hosted on same VPS
- Backend and LiveKit on same VPS
- Listener served by nginx

Operator environment:

- Windows 10/11 workstation
- PuTTY for SSH access
- WinSCP for file upload/download
- GitHub web interface
- No Docker knowledge assumed
- No Linux administration experience assumed

Environment assumptions above describe direct-IP pilot mode. Stage XII may add optional domain HTTPS/WSS mode, but it must not remove or break direct-IP pilot testing.

Documentation and deploy procedures must assume this environment unless explicitly stated otherwise.

## LiveKit pinned compatibility matrix (MVP baseline)

* LiveKit Server target: **1.9.11**
* Python runtime libraries for current codebase:
  * `livekit==1.1.5`
  * `livekit-api==1.1.0`
  * `livekit-protocol==1.1.3` (transitive pin observed in environment scan)
* Listener Web SDK file baseline: **1.15.13**
  * local pinned artifact path: `src/listener/vendor/livekit-client.umd.1.15.13.js`
  * CDN source: `https://unpkg.com/livekit-client@1.15.13/dist/livekit-client.umd.js`

Server patch note:
* LiveKit Server `1.9.12+` is not auto-approved by this spec; it requires compatibility checklist pass before replacing pinned `1.9.11`.

Upgrade rule:
* Any change of any matrix row requires explicit docs update in `docs/07_livekit_engine.md`, `docs/10_listener_ui.md`, `docs/15_open_issues.md` resolution note, and a compatibility re-test checklist.
