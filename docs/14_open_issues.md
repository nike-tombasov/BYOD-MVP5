## 15. Open issues

Rules for docs/14_open_issues.md:
- This file is updated only by special request.
- All new ambiguities are discussed in chat first.
- Only unresolved items after discussion are written here.
- This file is not a second architecture spec.

### 15.2 Current unresolved items

1) JSON strict validation final freeze
- open decision: keep strict regex + reject-all policy or simplify for operator UX in first VPS cycle.

2) Persistence schema versioning format
- open decision: whether dedicated `meta_schema.json` is mandatory in MVP.

3) Migration rules v1->v2
- migration and rollback policy for persistence versions is not finalized.

4) Deploy rollback hardening for nginx config replacement
- current deploy flow backs up `/etc/nginx/nginx.conf` before replacement and validates with `nginx -t`, but if validation fails after installing the BYOD site config, files on disk may remain in a non-working state even though the running nginx process was not restarted;
- define and implement rollback behavior so failed validation restores the previous known-good nginx main/site config before exit.

### 15.3 Stress-test and metrics limitations

1) `71_collect_test_tails.sh` reliability verification
- potentially useful, but has not yet been proven in a real stress incident to collect all expected files correctly;
- requires repeat verification on the VPS before it is treated as a trusted incident bundle source.

2) `73_live_stress_watch.sh` transport counters are approximate
- current UDP/TCP detection may be rough if regex counts `udp`/`tcp` inside ICE candidates instead of only stable `connectionType` fields;
- acceptable for live operator view, but not final forensic transport accounting.

3) `72_metrics_snapshot.sh` unavailable-endpoint behavior
- the helper may return non-zero when `/admin/metrics_snapshot` is unavailable;
- acceptable for standalone diagnostics, but bundle behavior should remain tolerant and must be verified.

4) Go loadgen selected-mode media accounting
- historical stress data showed possible multiple selected audio tracks per worker;
- keep this as a known measurement risk unless current code guarantees at most one selected track per worker and tests prove it.

5) Compact per-worker final state artifact
- current `VALID_RUN` summaries can be trusted at summary level, but when detailed events are deleted it is hard to re-check every worker;
- future improvement: add compact `workers_final_state.csv` or equivalent.
