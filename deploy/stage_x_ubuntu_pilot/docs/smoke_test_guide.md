# BYOD VPS Smoke Test Guide

Run smoke test after deploy, config changes, service restarts, or incident recovery:

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label manual_check
```

Expected successful ending:

```text
SUCCESS: BYOD smoke checks completed.
```

The script writes a timestamped report under `/opt/byod/diagnostics/` and prints `smoke_test_output_file=<path>`.

A failure means at least one critical service or local health check is not ready. First checks:

1. `sudo systemctl status byod-backend byod-livekit nginx --no-pager -l`
2. `sudo journalctl -u byod-backend -u byod-livekit -u nginx --no-pager -n 200`
3. `sudo nginx -t`
4. `sudo ss -lntup | grep -E ':(80|8000|7880|7881)\b'`
5. `curl -i http://127.0.0.1:8000/health && curl -i http://127.0.0.1/health`

For deeper diagnostics, metrics, logs, firewall checks, stress helpers, and emergency commands, see `testing_diagnostics_metrics.md`.
