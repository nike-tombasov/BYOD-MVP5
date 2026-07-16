## 20. Domain HTTPS/WSS mode

This document records the MVP domain-mode deployment model. Domain mode is optional for Stage XII; the existing direct-IP pilot test mode remains available for VPS pilots and fallback diagnostics.

### 20.1 Subdomain roles

- `listen-*` subdomains are guest-facing Listener entry points. They serve the same Listener HTML and WebSocket path under HTTPS/WSS for QR links.
- `lk-*` or `livekit-*` subdomains are LiveKit SFU entry points. They terminate the guest media connection path required by the Listener token flow.
- The backend remains a private service behind nginx. Public guest traffic must not expose backend port `8000/tcp` directly.

### 20.2 DNS A-record model

Each active VPS receives its own pair of A-records that point to that VPS public IPv4 address:

```text
listen-1.k-pls.ru -> VPS 1
lk-1.k-pls.ru     -> VPS 1
listen-2.k-pls.ru -> VPS 2
lk-2.k-pls.ru     -> VPS 2
```

For MVP operations, one simultaneous hall/event equals one VPS. A second simultaneous hall/event uses a second VPS and a second subdomain pair.

### 20.3 Event aliases are URL paths, not DNS rooms

Event aliases are path aliases on the same Listener HTML, for example `/event/main-hall` or `/event/workshop-a`. They do not create separate DNS records, separate LiveKit rooms, or separate simultaneous halls by themselves.

This keeps guest QR links readable while preserving the MVP capacity rule: one simultaneous hall/event is served by one VPS.

### 20.4 Direct-IP pilot mode

Direct-IP pilot mode remains supported for practical testing, diagnostics, and emergency fallback. Domain HTTPS/WSS mode is preferred for guest QR links when configured, but it is not mandatory for every pilot.
