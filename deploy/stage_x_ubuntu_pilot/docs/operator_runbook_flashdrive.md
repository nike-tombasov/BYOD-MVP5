# Stage XII flash-drive operator runbook

This runbook starts with a newly rented VPS and a foreign Windows computer. Use the USB drive and built-in Windows PowerShell/OpenSSH; PuTTY, WinSCP, Google Drive, and a phone transfer are not required.

## A. Prepare the USB flash drive

Store these files on it:

- `vps_config.env`
- `room_input.json`
- `livekit-server-v1.9.11-linux-amd64.tar.gz`
- `livekit-server-v1.9.11-linux-amd64.tar.gz.sha256`
- optional `livekit-client.umd.1.15.13.js`
- a text file containing the prepared VPS-shell bash deploy block

Keep the VPS login/password and other credentials safely outside git. Do not put secrets in a repository.

## B. After renting the VPS

1. Choose **Ubuntu Server 22.04 LTS** and note its public IPv4 address.
2. Create or check these DNS A records, replacing `VPS_IP`:
   - `listen-1.k-pls.ru -> VPS_IP`
   - `lk-1.k-pls.ru -> VPS_IP`
   - `admin-1.k-pls.ru -> VPS_IP` only when the reserved Admin hostname is used.
3. Wait for DNS propagation and confirm the names resolve to the VPS.
4. In the provider firewall allow `80/tcp`, `443/tcp`, `7881/tcp`, and `50000-59999/udp`. **Do not expose `8000/tcp`.**

A `subsite_name` such as `test-conf` is a Listener URL path, not a DNS name. Do not add DNS for it.

## C. Use the foreign Windows computer

Open the USB folder in File Explorer, click its address bar, type `powershell`, and press Enter. Check SSH access:

```powershell
ssh root@<VPS_IP>
```

Accept the host fingerprint only after checking it, log out, then upload the files:

```powershell
scp .\vps_config.env root@<VPS_IP>:/tmp/vps_config.env
scp .\room_input.json root@<VPS_IP>:/tmp/room_input.json
scp .\livekit-server-v1.9.11-linux-amd64.tar.gz root@<VPS_IP>:/tmp/
scp .\livekit-server-v1.9.11-linux-amd64.tar.gz.sha256 root@<VPS_IP>:/tmp/
# Optional:
scp .\livekit-client.umd.1.15.13.js root@<VPS_IP>:/tmp/
```

After the uploads finish, log in again with `ssh root@<VPS_IP>` (or connect with PuTTY). The remaining commands run in the **remote VPS Linux shell**, not in local PowerShell. Protect the config:

```bash
chmod 600 /tmp/vps_config.env
```

Then paste this entire bash block into that remote shell:

```bash
cat >/tmp/byod_run_deploy.sh <<'BYOD_DEPLOY'
#!/usr/bin/env bash
set -euo pipefail

BYOD_VPS_CONFIG=/tmp/vps_config.env

test -r "$BYOD_VPS_CONFIG"
sed -i 's/\r$//' "$BYOD_VPS_CONFIG"

set -a
source "$BYOD_VPS_CONFIG"
set +a

printf 'BYOD_REPO_URL=[%s]\n' "$BYOD_REPO_URL"
printf 'BYOD_REPO_BRANCH=[%s]\n' "$BYOD_REPO_BRANCH"

apt-get update
apt-get install -y git curl ca-certificates

rm -rf /opt/byod/app-src
mkdir -p /opt/byod
GIT_TERMINAL_PROMPT=0 git clone --branch "$BYOD_REPO_BRANCH" --single-branch "$BYOD_REPO_URL" /opt/byod/app-src

bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/01_one_deploy_from_vps_config.sh "$BYOD_VPS_CONFIG"
BYOD_DEPLOY

bash /tmp/byod_run_deploy.sh
```

Do **not** paste a PowerShell here-string (`@' ... '@`) into Linux bash. On the local Windows PC, PowerShell is used only for the `scp` commands above and the normal `ssh` login; the deploy block runs remotely. An invalid `room_input.json` stops deployment; fix it rather than bypassing validation.

## D. Post-deploy checks

Run the packaged smoke test:

```bash
sudo bash /opt/byod/app-src/deploy/stage_x_ubuntu_pilot/scripts/50_smoke_test.sh --label operator_runbook
```

Open `https://listen-1.k-pls.ru/`, the configured subsite path (if any), and `https://listen-1.k-pls.ru/health`. A wrong or old event path must return `404`. A public Admin check such as `/admin/metrics_snapshot` must also return `404`.

The Publisher field is still labelled **Server IP**. For this VPS enter the complete URL:

```text
ws://<VPS_PUBLIC_IP>/ws/publisher
```

## E. Leave no data on the foreign computer

- Delete copied command/config files from Downloads or Desktop, if any.
- Clear PowerShell history only if credentials or secrets were typed there.
- Do not leave the VPS password or API secret in plain text on the computer.
- Eject the USB drive safely.
