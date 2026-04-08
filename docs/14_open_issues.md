## 15. Open issues

Rules for docs/14_open_issues.md:
- This file is updated only by special request.
- All new ambiguities are discussed in chat first.
- Only unresolved items after discussion are written here.

### 15.1. Drift mismatchs between new documentation, mvp rules and current code.

Add to roadmap as uncoming fixes:
- Heartbeats mismatch;
- channel_0 must be listen false;
- deploying room status - CLOSED - change before VPS test with ready console commands;
- JWT token lifetime mismatch.

### 15.2. LiveKit version policy of LiveKit 1.9.11.
Current Python deps are livekit==1.1.5 and livekit-api==1.1.0, and listener HTML loads CDN client 1.15.13.
Check for compatibility again. Make real terminal/console scan of environment versions and pin this matrix in hard rules
Also choose to download fallback livekit client for Listener, then realize fallback protocol. Mark in docs this file version, which must be used as standalone in production Listener.

### 15.3. Backend lock during websocket send.
Need to be corrected as:
```
lock -> copy state
unlock
send to clients
```

### 15.4. Thread safety Qt (Publisher).
async tasks read UI widget state (currentData()) from non-UI thread path, which can cause intermittent undefined behavior in Qt apps under load or rapid interaction.

### 15.5. LiveKit API key / secret.
Must be marked in specification:
- secret lenght for VPS deploy is >32 character;
- auto generation with VPS deploy and save to backend, livekit.yaml for each new deploy.

### 15.6. i18n payload model.
Feature must be in current roadmap.md.

### 15.7. Listener attach/detach race guards from spec are not implemented.
No attachInProgress/detachInProgress flags and no operation timeout logic despite being specified, so rapid clicks + event bursts can produce inconsistent state transitions.

### 15.8. Formalize a strict WS schema doc (message types, required fields, error codes, retry behavior)
