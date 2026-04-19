#!/usr/bin/env bash
set -euo pipefail

curl -sf http://127.0.0.1/ >/dev/null && echo "listener_ok"
curl -sf http://127.0.0.1:8000/docs >/dev/null && echo "backend_ok"
ss -tulpen | awk '/7880|7881|8000|:80 / {print}'
