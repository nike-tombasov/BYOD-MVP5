# 24. Stress-test specification and latest useful result

## 1. Purpose and scope

BYOD stress/load testing measures how the backend listener admission path, LiveKit connection path, media subscription path, and VPS host resources behave under many emulated listener participants. The goal is to find usable MVP risk signals and bottlenecks from correlated loadgen output, backend/nginx/LiveKit logs, and VPS metrics.

Protocol/engine loadgen is not browser UI load testing. It does not prove browser rendering, autoplay behavior, audio output device behavior, CSS/layout stability, or human-facing Listener UX under mass browser load.

One or several real Web Listeners may be kept open during a stress run as monitoring clients. That is useful for operator observation, but it is separate from mass browser/Web Listener testing.

Infrastructure ports, nginx capacity settings, and Ubuntu deploy contract are documented in deploy docs and will be canonicalized separately.

## 2. Current canonical loadgen

The current canonical load generator is the Go loadgen under `tools/go_livekit_loadgen/`.

The Python loader is legacy and is not canonical for current capacity conclusions. Historical Python outputs may be useful as forensic context only; they should not be used as the source for current MVP capacity claims.

The Go loadgen goes through the normal backend listener admission path. It connects as a listener worker, receives the backend-issued LiveKit data when the selected gate needs it, and does not bypass the normal listener admission flow for capacity conclusions.

## 3. Gates

### Gate A: `backend-ws-only`

Gate A proves that the backend WebSocket listener path can admit workers, keep the listener protocol alive, and hold backend connections for the requested HOLD window. When run with the `vps-nginx` profile, nginx is part of the backend WebSocket path.

Gate A does not prove LiveKit signaling, WebRTC ICE, audio publication discovery, subscription, RTP receive, browser audio, or media egress capacity.

### Gate B: `livekit-connect-only`

Gate B proves that workers can pass backend admission, obtain backend-issued LiveKit connection data, and connect to LiveKit as participants. It measures the backend + LiveKit signaling/participant connection path without media subscription.

Gate B does not prove audio subscription, RTP packet flow, Opus decode, browser audio output, or real browser UI behavior.

### Gate C: `livekit-subscribe-discard-rtp`

Gate C proves that workers can pass backend admission, connect to LiveKit, subscribe to audio according to the configured subscribe mode, receive RTP packets, and discard RTP payloads without decoding or playing audio.

Gate C is media-engine load, not browser playback. It does not prove that hundreds of real browser tabs render and play audio correctly.

## 4. Run classification

`VALID_RUN` means the run reached the gate-specific required target, completed HOLD, and produced enough terminal worker and metric data to trust the result at summary level.

`PARTIAL_RUN` means the run collected useful capacity or degradation data, but did not fully satisfy the requested gate target or HOLD contract.

`INVALID_RUN` means setup, generator, local machine, configuration, or missing metrics made the run unreliable for capacity interpretation.

Shortfall stages identify where the first target gap appeared:

- `backend` — workers did not all reach the backend WebSocket/listener path;
- `livekit` — backend admission happened, but LiveKit participant connection did not reach target;
- `audio` — LiveKit connection happened, but workers did not all subscribe to an expected audio track;
- `rtp` — audio subscription happened, but workers did not all receive RTP packets.

Terminal worker events matter because a run can look successful in aggregate while some workers are still pending, cancelled, or missing final state. `workers_without_terminal_event=0` means every started worker produced a terminal event, making the final summary much easier to trust.

## 5. Required artifacts for useful stress analysis

A useful stress run should preserve:

- loadgen `summary_*.json`;
- loadgen `events_*.jsonl` when available;
- VPS metrics from `/opt/byod/metrics`;
- diagnostics from `/opt/byod/diagnostics`;
- metrics snapshot, especially `/admin/metrics_snapshot` output when available from the VPS-local diagnostic path;
- nginx, backend, and LiveKit tails when a run is partial, failed, suspicious, or close to a capacity boundary;
- optional `btop` screenshot or equivalent operator-visible CPU/RAM/network observation.

## 6. Metrics principle

Raw metrics are more important than a single green label. A `VALID_RUN` label is useful only when the raw counters and logs support it.

Timestamps must be preserved. Stress analysis should correlate loadgen timestamps, backend events, nginx logs, LiveKit logs, VPS metrics, diagnostics snapshots, and operator observations. Do not strip timing data from bundles.

## 7. Latest useful stress-test result — 23.06.2026

The latest useful stress-test result for current MVP risk was observed on a `cloud.reg.ru` VPS.

VPS configuration:

- 3 vCPU × 2.2 GHz;
- NVMe;
- 3 GB RAM;
- 10 GB SSD.

Available metrics show that the stress test reached approximately 695 listener participants. This was an emulated listener stress test, not a test of 695 real browser Web Listeners.

One real Web Listener was kept open separately during the load. Audio did not disappear in that Web Listener during the observed load.

Observed host/network metrics:

- peak CPU: approximately `22.33%`;
- RAM: approximately `2.073 / 2.898 GB`;
- TX: approximately `54.937 Mbps`.

This result is considered sufficient for current MVP pilot risk. It is not a capacity certificate for 2000 listeners, not proof that extreme burst joins are safe, and not proof that 695 real browser clients were tested.

## 8. Current conclusion

VPS stress testing is sufficient for current MVP pilot risk.

Further scaling characterization is deferred. The future target remains 2000 listeners, but this is not required for MVP. The project should keep moving toward 2000 by finding and removing blockers step by step.

## 9. Known limitations

- `71_collect_test_tails.sh` still needs real incident verification before it is treated as a trusted complete incident bundle collector.
- Live stress watch UDP/TCP counters are approximate and may need log-level correlation for final forensic transport accounting.
- Browser/Web Listener mass testing was not performed.
- A compact per-worker final state artifact, such as `workers_final_state.csv`, is still desirable for later re-checks when detailed events are removed.
- The 2000 listener goal remains future work, not an MVP requirement.
