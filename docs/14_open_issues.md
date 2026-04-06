## 15. Open issues for next stages

### 15.1 Publisher UI (Stage VI)
- define final module boundaries without behaviour regression
- design robust JSON config schema and corruption recovery strategy
- seamless token refresh mechanism and fallback reconnect policy
- stable `.exe` packaging script and dependency freeze strategy

### 15.2 Listener UI (Stage VII-VIII)
- strict BLOCKED/CLOSED behaviour in state machine
- fallback to local LiveKit client bundle if CDN unavailable
- race-condition audit with reproducible test scenarios
- cross-platform compatibility validation matrix

### 15.3 Backend (Stage IX)
- persistent JSON state model for room/connections/events
- formalized `.csv` bootstrap format and validator
- recording pipeline for per-channel tracks in `recordings/`
- safe manual operator console commands and audit logs

### 15.4 Deployment/Operations (Stage X)
- one-action Ubuntu deployment flow aligned with Stage I lessons
- complete runbooks for deploy/operate/emergency scenarios
- telemetry and log retrieval standards

### 15.5 Stress testing (Stage XI)
- synthetic traffic generator architecture
- distributed load coordination across multiple machines
- test telemetry aggregation and bottleneck analysis templates

### 15.6 Architecture decisions (Stage XII-XIII)
- security model decisions before deep implementation
- media optimization features adoption sequence
- Admin Web UI first vertical slice architecture
