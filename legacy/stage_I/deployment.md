# MVP Stage I  MVP - работающая система с backend, html-listener на арендованном VPS + удалённым Publisher

## 1. VPS deployment

mkdir -p ~/deploy
cd ~/deploy
nano install.sh

[
#!/usr/bin/env bash
set -e

echo "=== BYOD Translation | MVP installer ==="
echo


if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: Please run this script with sudo"
  exit 1
fi

if ! command -v lsb_release >/dev/null 2>&1; then
  echo "ERROR: Unable to detect Ubuntu version"
  exit 1
fi

UBUNTU_VERSION=$(lsb_release -rs)
if [[ "$UBUNTU_VERSION" < "22.04" ]]; then
  echo "ERROR: Ubuntu 22.04 or newer is required"
  exit 1
fi

echo "OK: Ubuntu $UBUNTU_VERSION detected"
echo


read -rp "Enter room ID (e.g. hall-1): " ROOM_ID
if [[ -z "$ROOM_ID" ]]; then
  echo "ERROR: Room ID cannot be empty"
  exit 1
fi

read -rp "Enter public server IP: " PUBLIC_IP

if ! [[ "$PUBLIC_IP" =~ ^[0-9.]+$ ]]; then
  echo "ERROR: IP must contain only digits and dots"
  exit 1
fi

if ! [[ "$PUBLIC_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "ERROR: Invalid IPv4 format"
  exit 1
fi

read -rp "Maximum number of languages (1–15): " MAX_LANGS
if ! [[ "$MAX_LANGS" =~ ^[0-9]+$ ]] || [[ "$MAX_LANGS" -lt 1 ]] || [[ "$MAX_LANGS" -gt 15 ]]; then
  echo "ERROR: Please enter a number between 1 and 15"
  exit 1
fi

echo
echo "Installation parameters:"
echo "Room ID:            $ROOM_ID"
echo "Public server IP:   $PUBLIC_IP"
echo "Max languages:      $MAX_LANGS"
echo

read -rp "Proceed with installation? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  echo "Installation aborted by user"
  exit 0
fi

echo
echo "=== Installing Docker ==="

apt update
apt install -y ca-certificates curl gnupg lsb-release

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

systemctl enable docker
systemctl start docker

docker version >/dev/null 2>&1
echo "OK: Docker installed and running"

BASE_DIR="/opt/byod"

mkdir -p "$BASE_DIR/deploy"
mkdir -p "$BASE_DIR/backend"

echo
echo "OK: Project directory created:"
echo "  $BASE_DIR"

echo
echo "=== STAGE 1 COMPLETED ==="
echo "Next step: LiveKit configuration and docker-compose"
]

chmod +x install.sh

sudo ./install.sh

## 2. VPS protection

fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

echo "vm.swappiness=10" >> /etc/sysctl.conf
sysctl -p

## 3. LiveKit config
cd /opt/byod
mkdir -p livekit
cd livekit

nano livekit.yaml

[
port: 7880

bind_addresses:
  - "0.0.0.0"

rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 50100
  use_external_ip: true

keys:
  devkey: "12345678901234567890123456789012345"
]

## 4. Docker
cd /opt/byod
nano docker-compose.yml

## 5. Start server
cd /opt/byod
docker compose up -d

docker ps
docker logs byod-livekit-1
ss -tulpn | grep 7880


## 6. Token generation
curl -sSL https://get.livekit.io/cli | bash

lk token create \ --api-key devkey \ --api-secret 12345678901234567890123456789012345 \ --identity publisher-user \ --room hall-1 \ --join \ --valid-for 1h

lk token create --api-key devkey --api-secret 12345678901234567890123456789012345 --identity browser-user --room hall-1 --join --valid-for 1h

## 7. HTML

/legacy/stage_I/index.html

## 8. Python Publisher (console)

/legacy/stage_I/publisher.py



