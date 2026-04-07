# To be discussed

## 1. WebSocket protocol

What to be included?

## 2.  Errors/retries

Message contract and error/retry behavior are not formalized

## 3. Listener rapid channel button switching

Listener must use selective subscribe only (good), but no debounce/backoff policy for rapid channel button switching. Risk: subscription churn.

## 4. Heartbeats

Real timing for offline Publisher and other 

## 5. Listener overflow protection baseline

Decision direction:
- should be implemented in MVP Stage VII-IX (backend admission control + listener active PLAY heartbeat).
- baseline values: 1.05 hard-limit reserve, target/15 conn rate, reconnect interval >2 sec, play heartbeat 10 sec/timeout 60 sec.
## 5. Protection from unwanted room overflow by lots of Listeners

- hard limit [max active listeners = <target capacity> * <1,05 reserve>]
- Rate-limit - frequency of new connections (ex., max [<target capacity>/15] per sec)
- Minimal limit between reconnect (ex., > 2 sec)
- heartbeat active listeners - web page active "play" control (ex., heartbeat every 10 sec, after 60 sec need to reconnect)
