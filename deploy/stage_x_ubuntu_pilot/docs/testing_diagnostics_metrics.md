# BYOD VPS Testing, Diagnostics, Metrics, and Logs

## Smoke test purpose and limits

`50_smoke_test.sh` checks systemd services, local backend health, nginx config, key ports, LiveKit process state, optional vendor presence, room config presence, local metrics access, and firewall reminders. It is a readiness check, not a capacity guarantee or long-running stability test.

## Quick service checks

```bash
sudo nginx -t
sudo systemctl status nginx byod-backend byod-livekit --no-pager -l
sudo journalctl -u nginx -u byod-backend -u byod-livekit --no-pager -n 200
```

## Ports and firewall checks

```bash
sudo ss -lntup | grep -E ':(80|8000|7880|7881)\b'
sudo ss -lunp | grep livekit || true
```

Expected: nginx on `80/tcp`, backend on loopback `127.0.0.1:8000`, LiveKit on `7880/tcp` and `7881/tcp`. Provider firewall must allow `80/tcp`, `7880/tcp`, `7881/tcp`, `50000-59999/udp`; it must not expose `8000/tcp`.

## nginx and systemd limits

```bash
sudo nginx -T | grep -E 'worker_processes|worker_connections|worker_rlimit_nofile'
systemctl show nginx -p LimitNOFILE
systemctl show byod-backend -p LimitNOFILE
sudo ss -tanp | grep nginx | wc -l
sudo ss -tanp | grep ':8000' | wc -l
```

These checks help diagnose connection ceilings and file descriptor limits.

## Backend health and local admin endpoints

```bash
curl -i http://127.0.0.1:8000/health
curl -sf http://127.0.0.1:8000/admin/metrics_snapshot | python3 -m json.tool
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/67_backend_console_command.sh status
```

Admin endpoints are local-only and are not intended as public operator APIs.

## Listener checks

```bash
sudo -u www-data test -r /opt/byod/listener/index.html && echo OK
sudo -u www-data test -r /opt/byod/listener/listener.js && echo OK
sudo -u www-data test -r /opt/byod/listener/vendor/livekit-client.umd.1.15.13.js && echo OK || echo CDN_FALLBACK
```

Open `http://<VPS_PUBLIC_IP>/` in a browser and confirm Listener WebSocket connection, channel state, and playback when a Publisher is active.

## Publisher checks

Use the Windows Publisher with the VPS public origin/backend settings. Confirm backend WebSocket connection, LiveKit connection, correct channel publication, Listener playback, and normal stop behavior. Do not put PINs or tokens into logs or screenshots.

## LiveKit checks

```bash
grep -E 'port_range_start|port_range_end|tcp_port|use_external_ip' /opt/byod/config/livekit.yaml
sudo tcpdump -ni any 'udp portrange 50000-59999 or tcp port 7881'
```

The primary UDP profile uses `50000-59999/udp`. `ss -lunp` may not show all UDP ports until media traffic is active.

## Logs

```bash
sudo journalctl -u byod-backend --no-pager -n 200
sudo journalctl -u byod-livekit --no-pager -n 200
sudo journalctl -u nginx --no-pager -n 200
sudo tail -n 200 /opt/byod/logs/backend.stdout.log
sudo tail -n 200 /opt/byod/logs/backend.stderr.log
```

## Diagnostic bundle

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/90_collect_diagnostics.sh
```

The bundle path is printed by the script, typically under `/tmp/byod-diagnostics-<timestamp>/`.

## Metrics analyzer

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh start
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh status
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/95_metrics_analyzer.sh stop
```

## Stress/emergency helper scripts

| Script | Purpose |
|---|---|
| `50_smoke_test.sh` | Readiness smoke check and concise service summary. |
| `68_apply_backend_stress_profile.sh` | Apply backend stress profile for controlled tests. |
| `69_remove_backend_stress_profile.sh` | Remove backend stress profile and restore normal config. |
| `71_collect_test_tails.sh` | Collect recent service tails around a test window. |
| `72_metrics_snapshot.sh` | Save one local metrics snapshot with a label. |
| `73_live_stress_watch.sh` | Repeated live metrics/watch output during a test. |
| `90_collect_diagnostics.sh` | General diagnostics bundle. |
| `95_metrics_analyzer.sh` | Start/status/stop metrics analyzer helper. |

## UDP profile checks

Primary profile:

```text
tcp_port: 7881
port_range_start: 50000
port_range_end: 59999
use_external_ip: true
```

Fallback `7882/udp` config is only for provider/VPS UDP-range problems:

```bash
sudo cp /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/config/livekit_udp_mux_7882.yaml /opt/byod/config/livekit.yaml
sudo systemctl restart byod-livekit
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label udp_mux_fallback
```

## Dangerous commands

These are not smoke-test commands. Use them only with an incident plan, current backups, and provider console access. Run the smallest necessary command and record what was changed.

### Service restart

Restart disconnects active sessions and forces clients to reconnect:

```bash
sudo systemctl restart byod-backend byod-livekit nginx
```

### Service stop

Stop makes the service unavailable until it is started again:

```bash
sudo systemctl stop byod-backend byod-livekit nginx
```

### Disable autostart

Disable removes autostart after reboot. A later reboot can leave the VPS without the public web server, backend, or LiveKit service:

```bash
sudo systemctl disable nginx
sudo systemctl disable byod-backend
sudo systemctl disable byod-livekit
```

### Delete deploy checkout or state

Deleting `app-src` removes deploy scripts and the package checkout. Deleting `backend_data` removes persisted room config, runtime state, and recording state:

```bash
sudo rm -rf /opt/byod/app-src
sudo rm -rf /opt/byod/backend_data
```

Deleting `/opt/byod` removes the application, configs, state, logs, releases, diagnostics, and deploy checkout:

```bash
sudo rm -rf /opt/byod
```

### Destroy config files

Truncate destroys config files and can prevent services from starting:

```bash
sudo truncate -s 0 /opt/byod/config/backend.env
sudo truncate -s 0 /opt/byod/config/livekit.yaml
```

### Firewall reset

`ufw reset` can lock out SSH or expose/close the wrong ports depending on provider defaults and later rules:

```bash
sudo ufw reset
```

### VPS power operations

Reboot terminates sessions and restarts the VPS. Poweroff shuts down the VPS and may require provider panel access to start it again:

```bash
sudo reboot
sudo poweroff
```
