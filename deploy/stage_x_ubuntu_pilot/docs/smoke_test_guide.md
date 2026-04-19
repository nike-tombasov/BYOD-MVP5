# Stage X Smoke Test Guide

Run after deployment.

## Service checks

```bash
systemctl status byod-livekit --no-pager
systemctl status byod-backend --no-pager
systemctl status nginx --no-pager
```

## Port checks

```bash
ss -tulpen | awk '/7880|7881|8000|:80 / {print}'
```

Expected:
- nginx on `:80`
- backend on `:8000`
- LiveKit on `:7880` and `:7881`

## HTTP checks

```bash
curl -i http://127.0.0.1/
curl -i http://127.0.0.1:8000/docs
```

## Basic functional check (manual)

1. Open listener page in browser.
2. Add query parameter `?backend=ws://<VPS_IP>:8000/ws/listener` if needed.
3. Confirm room appears and no permanent reconnect banner.

## Log checks

```bash
tail -n 50 /opt/byod/logs/livekit.stderr.log
tail -n 50 /opt/byod/logs/backend.stderr.log
tail -n 50 /opt/byod/backend_data/events_log_$(date -u +%Y%m%d).jsonl
```

Look for `livekit_unreachable` events (must be empty in healthy state).
