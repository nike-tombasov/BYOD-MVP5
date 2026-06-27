# BYOD VPS Incident Quick Actions

Simple operator checklist.

## A) Listener page not opening

1. Check nginx:
```bash
systemctl status nginx --no-pager
```
2. Restart nginx:
```bash
sudo systemctl restart nginx
```
3. Read nginx errors:
```bash
tail -n 100 /var/log/nginx/error.log
```

## B) Listener shows reconnecting forever

1. Check backend service:
```bash
systemctl status byod-backend --no-pager
```
2. Check LiveKit service:
```bash
systemctl status byod-livekit --no-pager
```
3. Check backend log for LiveKit errors:
```bash
tail -n 100 /opt/byod/backend_data/events_log_$(date -u +%Y%m%d).jsonl | grep livekit_unreachable || true
```

## C) Backend starts but does not work

1. Validate env file:
```bash
cat /opt/byod/config/backend.env
```
2. Restart backend:
```bash
sudo systemctl restart byod-backend
```
3. Read backend logs:
```bash
tail -n 100 /opt/byod/logs/backend.stderr.log
```

## D) Need clean rollback for pilot

Pilot rule: no in-place upgrade. Use fresh VPS deployment.

1. Save logs and configs.
2. Deploy previous known-good commit on a new VPS.
3. Follow deploy guide from start.
