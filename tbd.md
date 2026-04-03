# To be discussed

## 1. WebSocket protocol

What to be included?

## 2.  Errors/retries

Message contract and error/retry behavior are not formalized

## 3. Listener rapid channel button switching

Listener must use selective subscribe only (good), but no debounce/backoff policy for rapid channel button switching. Risk: subscription churn.

## 4. Heartbeats

Real timing for offline Publisher and other 