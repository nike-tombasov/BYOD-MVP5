# To be discussed

## 1.  Errors/retries

Message contract and error/retry behavior are not formalized

## 2. Listener rapid channel button switching

Listener must use selective subscribe only (good), but no debounce/backoff policy for rapid channel button switching. Risk: subscription churn.

## 3. Heartbeats

Real timing for offline Publisher and other 

## 4. Listener overflow protection baseline

Decision direction:
- should be implemented in MVP Stage VII-IX (backend admission control + listener active PLAY heartbeat).
- baseline values: 1.05 hard-limit reserve, target/15 conn rate, reconnect interval >2 sec, play heartbeat 10 sec/timeout 60 sec.

Unresolved question: Listener UX note to reload page or autoreload/reconnect after timeout?

## 5. Owner return after reconnect 
