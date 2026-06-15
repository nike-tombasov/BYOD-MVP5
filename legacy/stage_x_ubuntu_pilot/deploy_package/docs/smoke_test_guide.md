# Stage X Smoke Test Guide

Run after deployment.

## Service checks

```bash
sudo nginx -t
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
- backend on loopback `127.0.0.1:8000` (not publicly open)
- LiveKit on `:7880` and `:7881`

## Import, permissions, and HTTP checks

```bash
cd /opt/byod/app
sudo -u byod /opt/byod/app/.venv/bin/python -c 'import backend.main'
sudo -u www-data test -r /opt/byod/listener/index.html
curl -i http://127.0.0.1/
curl -i http://127.0.0.1/health
```

## Basic functional check (manual)

1. Open listener page in browser: `http://<VPS_IP>/`
2. Listener should auto-connect through nginx to `ws://<VPS_IP>/ws/listener`
3. Confirm room appears and no permanent reconnect banner.

Debug fallback only:
- You can still override backend with `?backend=ws://...` when troubleshooting.

## Provider firewall

Allow inbound `80/tcp`, `7880/tcp`, `7881/tcp`, and `50000-50100/udp`.
Do not open `8000/tcp`; nginx reaches that loopback-only backend locally.

## Log checks

```bash
tail -n 50 /opt/byod/logs/livekit.stderr.log
tail -n 50 /opt/byod/logs/backend.stderr.log
tail -n 50 /opt/byod/backend_data/events_log_$(date -u +%Y%m%d).jsonl
```

Look for `livekit_unreachable` events (must be empty in healthy state).
