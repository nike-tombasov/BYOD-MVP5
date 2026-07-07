#!/usr/bin/env bash
set -euo pipefail
RED='\033[1;31m'; CYAN='\033[1;36m'; NC='\033[0m'
if [[ $# -lt 1 ]]; then
  echo "Usage: sudo bash $0 '<command>'" >&2
  exit 2
fi
COMMAND="$*"
python3 - "$COMMAND" <<'PY' | curl -sf -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:8000/admin/console_command | python3 -m json.tool
import json, sys
print(json.dumps({'command': sys.argv[1]}))
PY
printf "%b\n" "${CYAN}console-command: completed${NC}"
