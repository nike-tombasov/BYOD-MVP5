# Stage X — Ubuntu 22.04 Single-VPS Pilot Snapshot

## Status

Stage X is completed. The MVP10 pilot was deployed to and manually verified on
a clean Ubuntu Server 22.04 LTS VPS with one public IPv4 address, no domain, and
no TLS.

Verified results:

- nginx serves the Listener and proxies Listener and Publisher WebSockets to a
  backend bound privately to `127.0.0.1:8000`;
- the backend runs under systemd and issues LiveKit tokens;
- the self-hosted LiveKit 1.9.11 server runs under systemd;
- Publisher connects through nginx at
  `ws://<VPS_PUBLIC_IP>/ws/publisher`;
- Listener connects through nginx at `http://<VPS_PUBLIC_IP>/`;
- Publisher-to-Listener audio works in the deployed VPS environment;
- Listener request IDs do not require `crypto.randomUUID` on an HTTP/IP origin;
- deployment validates the required pinned Listener SDK file
  `vendor/livekit-client.umd.1.15.13.js`;
- operator diagnostics and troubleshooting procedures are included.

## Preserved artifacts

- `deploy_package/` is the completed Stage X deploy package snapshot: manifest,
  Ubuntu installation scripts, nginx config, systemd units, configuration
  template, operator deploy/smoke/incident/environment docs, and the VPS
  diagnostics collector.
- `backend_logging_contract.md` preserves the Stage X backend diagnostics and
  logging contract used by the pilot.

The application source remains canonical under `src/`; it is not duplicated in
this snapshot. The pinned LiveKit server archive and Listener SDK binary are
not duplicated here.

## Pilot boundary

This snapshot records a single-node pilot, not a production architecture.
Domain configuration, TLS, production monitoring, scaling, load balancing,
and multi-node deployment were not Stage X requirements. Stage XI is planned
to characterize load and capacity on a concrete VPS.

## Sanitization

This snapshot contains templates and placeholders only. It intentionally
contains no VPS-specific IP address, credentials, API secrets, tokens, PINs,
runtime logs, diagnostics output, or operator-local machine paths.
