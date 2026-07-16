## 21. Unresolved bugs

### 21.1 Publisher/Backend behavior when LiveKit Server is absent

Status: **postponed until VPS pilots end** (was unresolved, reproducible).

#### Reproduction path
1) LiveKit Server is not started.
2) Backend starts, Publisher starts.
3) Publisher connects to backend successfully; backend registers publisher; CONNECT button become unavailable.
4) Publisher presses `ON AIR`; backend registers owner.
5) Publisher later falls into connection error flow in IP/PIN block; channel row can remain stuck at `Connecting...`; CONNECT button become available.
6) Backend eventually drops publisher by timeout.
7) If Publisher reconnects by pressing `CONNECT`, backend registers a new publisher identity and previously owned channel may remain frozen as `ENGAGED` on Publisher UIs.
8) as expected by interlock logic now one can ON AIR this ENGAGED channel. 

#### Current impact
- operator receives confusing UX with mixed connection/channel statuses;
- channel can remain blocked by stale ownership until manual recovery;
- backend lacks explicit diagnostics for missing LiveKit in this path.

#### Temporary mitigation
- restart Publisher and clear ownership manually from backend-side state management procedures.

#### Required follow-up (not implemented here)
- formalize error/ownership recovery contract between Publisher and backend for missing LiveKit path;
- implement backend command `OFF AIR channel` to clear stale ownership;
- formalize Publisher/backend logging contract for this scenario.
