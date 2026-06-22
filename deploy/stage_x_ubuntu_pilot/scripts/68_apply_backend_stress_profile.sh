#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then echo "ERROR: must run as root" >&2; exit 1; fi
ENV_SRC="/opt/byod/app-src/deploy/stage_x_ubuntu_pilot/config/backend_stress_test.env"
[[ -f "$ENV_SRC" ]] || ENV_SRC="$(cd "$(dirname "$0")/.." && pwd)/config/backend_stress_test.env"
DROPIN_DIR="/etc/systemd/system/byod-backend.service.d"
DROPIN="$DROPIN_DIR/90-stress-test.conf"
install -d -m 0755 "$DROPIN_DIR"
install -m 0644 "$ENV_SRC" /etc/byod-backend-stress-test.env
cat > "$DROPIN" <<'DROPIN'
[Service]
EnvironmentFile=/etc/byod-backend-stress-test.env
DROPIN
systemctl daemon-reload
systemctl restart byod-backend
systemctl is-active --quiet byod-backend
if curl -fsS http://127.0.0.1:8000/admin/metrics_snapshot >/tmp/byod_metrics_snapshot.json 2>/dev/null; then
  python3 - <<'PY'
import json
p=json.load(open('/tmp/byod_metrics_snapshot.json'))
for k in ('max_active_listeners','max_new_connections_per_sec','loadgen_reconnect_bypass_enabled','listener_min_reconnect_interval_per_ip_seconds'):
    print(f'{k}={p.get(k, "unknown")}')
PY
else
  echo "WARNING: runtime limits unavailable from local metrics. Run: curl -s http://127.0.0.1:8000/admin/metrics_snapshot | python3 -m json.tool" >&2
fi
