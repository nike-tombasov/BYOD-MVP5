## 14. MVP status (updated)

### 14.1 Stage summary

- **Stage I** — VPS first successful chain (legacy baseline) — **DONE**.
- **Stage II** — expanded redesign attempt — **FAILED** (version/architecture mismatch).
- **Stage III** — simplified publisher recovery stage — **DONE**.
- **Stage IV** — gradual Publisher UI v0.2 stabilization — **DONE**.
- **Stage V** — multi-publisher + multi-listener + up to risky 32 channels with interlock logic — **DONE**.

### 14.2 Current active stage

- **Active:** Stage VI (Publisher UI hardening for VPS pilot).
- **Why now:** this is the highest priority before broader Listener/Backend/VPS scaling tasks.

### 14.3 Stage V completion snapshot

Stage V achieved:
1) stable publish/listen flow for multi-publisher multi-channel scenarios
2) backend state remains source of truth for owner/interlock logic
3) practical scaling path up to 32 channels in MVP conditions
4) Publisher UI baseline version is **v0.3**

### 14.4 Stage VI target snapshot

Must deliver:
1) safer module decomposition in Publisher UI
2) JSON memory for IP/PIN/device mapping
3) silent seamless token refreshing
4) reproducible `.exe` packaging process

### 14.5 What is intentionally postponed

Moved to next stages (not Stage VI):
- Listener BLOCKED/CLOSED final rules
- Listener CDN fallback + race hardening
- backend persistence/recording/operator console
- one-action Ubuntu VPS deployment package
- high-load stress framework
- advanced media/security technologies discussion implementation
- Admin Web UI realization
