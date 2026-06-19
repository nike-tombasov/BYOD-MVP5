# Stress/load testing architecture — MVP11

This document is the single active guide for BYOD MVP11 stress/load testing architecture. It defines the future Windows-first Go LiveKit SDK load generator, the mandatory validation gates, and the metrics required for trusted capacity characterization.

## 1. Current status

- The previous Windows/Python portable loader has been frozen as **Legacy** under `legacy/stage_xi_failed_python_loader/`.
- The Legacy Python loader is **not valid** for formal capacity characterization, MVP11 acceptance, or VPS scaling decisions.
- It is retained only as a forensic/protocol reference for understanding the listener protocol, old counters, and observed failure modes.
- The active future architecture is a **Windows-first Go LiveKit SDK loadgen**.
- Do not use `python tools/load_test/byod_listener_loader.py` as an active capacity-testing command. The old Python commands are intentionally absent from this active guide.
- This PR documents architecture only: it does not implement the Go loadgen, does not change backend runtime logic, does not change nginx runtime scripts, and does not change LiveKit runtime config.

## 2. Scope and non-goals

Stage XI/Protocol-engine load is not browser UI load. A loadgen worker emulates the backend listener protocol and, in LiveKit modes, the LiveKit participant/media behavior needed for capacity measurement. It does not validate Web Listener UI rendering, browser audio output, browser autoplay behavior, CSS/layout, or human-facing UX.

Browser/Web Listener UI mass testing is out of scope. One or two real browser listeners may be used as monitoring clients during VPS tests, but thousands of browser tabs are not part of this plan.

The loadgen must not require PIN. It must use the normal listener backend protocol and backend admission path that real listeners use after the relevant room/channel has been configured. The loadgen must not use the Publisher endpoint and must not use an admin token endpoint to bypass backend admission.

`/admin/metrics_snapshot` remains local-only and must not be exposed through nginx. It can be read on the VPS host for diagnostics, analyzer inputs, or operator checks, but it is not a public loadgen API.

## 3. Overall MVP11 capacity goal

MVP-level acceptance succeeds when one VPS sustains **500 emulated listeners for 10 minutes** without observed degradation.

An **emulated listener** means:

- backend listener WebSocket connected;
- LiveKit token received;
- LiveKit RTC connection established in LiveKit modes;
- for media mode, audio track subscribed and RTP packets read/discarded;
- heartbeat maintained during HOLD.

Bonus/non-blocking scaling confidence target: up to **2000 active emulated listeners** with 1–2 publishers and 1–2 real browser listeners. The 2000 target is not required to pass MVP on the current small VPS; hitting VPS capacity is acceptable if the bottleneck and metrics are measured. The point of the 2000 target is to verify architectural scalability and expose the next bottleneck after the old 382 WebSocket ceiling.

Raw metrics remain more important than a single pass/fail label. A clean failure with trustworthy metrics is more useful than a green label from an untrusted generator.

## 4. Important capacity distinction

`target_capacity` is room/listener business capacity, not the raw WebSocket file-descriptor ceiling. Do not change the current backend default `DEFAULT_TARGET_CAPACITY = 200` in this documentation/relocation PR.

For stress events, operator/imported room config may raise the room target manually. WebSocket/server limits must have separate headroom for:

- listeners;
- publishers;
- real browser monitoring;
- admin UI;
- metrics/smoke/diagnostic clients;
- reconnect overlap.

Future runtime implementation should support at least:

- required minimum: 500 emulated listeners plus service headroom;
- ideal stress ceiling: 2000 emulated listeners plus service headroom;
- acceptable formula: either explicit 2000+ peer ceiling or `target_capacity * 1.5` with safe lower/upper bounds.

Do not make `target_capacity` the only raw WS ceiling. Future stress override policy should be controlled, explicit, and loadgen-only where appropriate; it must not silently weaken production listener admission semantics.

## 5. Mandatory loadgen gates

The future Go loadgen must implement these gates in order. A later gate is not considered meaningful until the earlier gate is understood for the same endpoint profile and target range.

### Gate A — backend-ws-only

Purpose:

- Tests nginx/backend WebSocket admission, heartbeat, rate limits, stale cleanup, and backend metrics.
- Does not connect to LiveKit.
- Must support local-direct and vps-nginx endpoint profiles.
- Must not stall in a local LAN test without nginx.

Validity:

- connected backend WS count reaches requested target;
- heartbeats continue during HOLD;
- backend reject counters and close codes are summarized;
- HOLD duration completes or failure mode is clearly logged.

### Gate B — livekit-connect-only

Purpose:

- Tests backend WS plus LiveKit token issuance, LiveKit signaling, ICE, and participant connection.
- Does not subscribe to audio tracks.
- Measures LiveKit room/participant scale without media egress.

Validity:

- backend WS connected;
- token received;
- LiveKit room connected;
- transport mode observed;
- stable during HOLD.

### Gate C — livekit-subscribe-discard-rtp

Purpose:

- Tests backend WS plus LiveKit participant plus audio subscription and actual media egress.
- Must subscribe to selected audio track.
- Must read RTP packets and immediately discard payload.
- Must not decode Opus.
- Must not use physical audio output.

Validity:

- backend WS connected;
- LiveKit room connected;
- selected publication seen;
- subscription requested;
- track subscribed;
- RTP packet counter grows during HOLD;
- heartbeat maintained.

Missing audio track is not automatically a VPS failure. In Gate C it may indicate publisher setup, channel selection, LiveKit publication timing, or loadgen subscription behavior. The run classification must explain the observed failure mode.

## 6. Endpoint profiles

```text
local-direct
  backend_base=http://127.0.0.1:8000
  listener_ws=ws://127.0.0.1:8000/ws/listener
  livekit_url normally ws://127.0.0.1:7880 or backend-issued equivalent
  no nginx required

vps-nginx
  backend_base=http://<VPS_PUBLIC_IP>
  listener_ws=ws://<VPS_PUBLIC_IP>/ws/listener
  livekit_url normally ws://<VPS_PUBLIC_IP>:7880 from backend token response
  nginx is part of the test path for backend WS
```

No domain and no HTTPS/WSS are assumed for the MVP11 public-IP pilot.

## 7. Windows-first Go loadgen target

Future implementation target location:

```text
tools/go_livekit_loadgen/
```

Initial operator workflow:

- run from a Windows developer/operator machine;
- first from PyCharm/terminal using PowerShell `.ps1` helpers;
- no Linux-first requirement;
- no requirement for portable packaging in the first implementation;
- portable one-folder package may be added after the tool is trusted;
- keep commands simple and few.

Expected command shape, not implemented in this PR:

```powershell
.\run_loadgen.ps1 -Profile local-direct -Mode backend-ws-only -Server http://127.0.0.1:8000 -Listeners 500 -RampPerSec 50 -HoldSec 600 -RunnerId win-dev-1

.\run_loadgen.ps1 -Profile vps-nginx -Mode livekit-connect-only -Server http://<VPS_PUBLIC_IP> -Listeners 500 -RampPerSec 25 -HoldSec 600 -RunnerId win-home-1

.\run_loadgen.ps1 -Profile vps-nginx -Mode livekit-subscribe-discard-rtp -Server http://<VPS_PUBLIC_IP> -Listeners 500 -RampPerSec 10 -HoldSec 600 -RunnerId win-home-1
```

## 8. Protocol identity and channel invariants

`runner_id` remains mandatory. The operator supplies it explicitly so every run can be separated in metrics, logs, and analyzer output.

`worker_id` remains traceable. A recommended format is `<runner_id>-L<zero_padded_index>`, but the exact format may evolve if it remains stable and searchable.

`client_type: "load_runner"` remains diagnostic metadata, not a general listener protocol change and not a privilege escalation. It helps separate loadgen clients from real browser listeners in logs and metrics.

Fixed channel mode must fail fast if the channel is invalid. Silent fallback from fixed channel to random is forbidden because it makes capacity results impossible to interpret.

## 9. Live and final summaries required from future Go loadgen

Live summary must include at least:

- target listeners;
- workers started;
- backend WS connected;
- backend WS failed/rejected;
- LiveKit connected;
- publication seen;
- subscription requested;
- track subscribed;
- RTP packets per second;
- RTP bytes per second;
- UDP connections;
- TCP connections;
- UDP/TCP ratio;
- reconnects;
- disconnects;
- current HOLD elapsed;
- current error summary.

Final summary must include at least:

- requested mode;
- endpoint profile;
- target listeners;
- ramp settings;
- HOLD duration requested and actual;
- backend connected total;
- LiveKit connected total;
- subscribed total;
- RTP packet/byte totals for media mode;
- UDP/TCP ratio;
- first failure timestamp;
- top error categories;
- pass/partial/invalid classification;
- generated log paths.

TCP is allowed and must be measured. UDP/TCP ratio is diagnostic, not an automatic pass/fail by itself.

Analyzer output remains CSV + JSONL + human-readable log. The future analyzer may consume Go loadgen output, backend metrics snapshots, LiveKit API snapshots, nginx logs, and host observations, but the durable output formats remain machine-readable CSV/JSONL plus an operator-readable log.

## 10. HOLD and run classification

HOLD is the steady-state observation period after ramp-up. During HOLD, workers must maintain heartbeat and the loadgen must report current connected/subscribed/media counters. HOLD is where CPU, RAM, network RX/TX, backend status, LiveKit status, nginx behavior, reconnects, and close/error codes are observed.

```text
VALID_RUN
```

The run reached the gate-specific target and held it for the requested HOLD duration with enough metrics to trust the result.

```text
PARTIAL_RUN
```

Some useful capacity/degradation data was collected, but the run did not fully satisfy the gate.

```text
INVALID_RUN
```

The load generator, local machine, setup, config, or metrics failed in a way that makes capacity interpretation unreliable.

## 11. LiveKit UDP strategy for future implementation

Intended future stress profile:

- Primary stress UDP range: `50000-54000/udp`.
- Reason: about 4001 UDP ports, enough for approximately 2000 peers if two UDP ports per participant are needed.
- Fallback profile: `rtc.udp_port: 7882`, with firewall `7882/udp`, if wide UDP range causes VPS/provider/setup problems.
- Do not switch to `7882/udp` as the first default in this PR.
- Do not change actual config in this PR.

The current stage pilot config may still use a narrower UDP range, and existing smoke/deploy scripts may still print older expectations. Those runtime files are intentionally not changed here; this document records the intended future stress profile.

## 12. VPS/operator observations

`btop` remains expected on the VPS for operator-visible CPU, memory, process, and network observation during stress events. Backend and LiveKit metrics should be captured near the same time as loadgen summaries whenever possible.

Raw metrics remain more important than a single pass/fail label. Operators should preserve terminal output, generated logs, CSV/JSONL files, backend snapshots, and host observations for each run.

## 13. Next implementation tasks

1. Implement `tools/go_livekit_loadgen/`.
2. Add future controlled loadgen-only bypass for per-IP reconnect throttle.
3. Add future nginx full config/template with `worker_connections 65535`.
4. Add future LiveKit config profile for `50000-54000/udp` and fallback `7882/udp`.
5. Add future room config import helper script from `/tmp`.
6. Add future simplified smoke test one-line-per-service output.
7. Add future timestamp field `ts_iso` rounded to tenths of a second with Moscow timezone `+03:00`.
