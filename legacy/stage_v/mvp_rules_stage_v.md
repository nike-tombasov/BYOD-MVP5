# MVP rules for current stage

Goal: working multi-publisher audio engine

Do NOT implement:

- admin web UI
- channel recording
- statistics
- security features
- authentication for listeners
- token expiration logic
- dynamic PIN generation
- multi-room support
- advanced logging
- deployment automation

Use fixed values for MVP:

- PIN = 123456
- room_name = test room
- room_status = OPENED always
- JWT lifetime = 5h

Scope:

- console logging allowed
- no performance optimization yet

Rules:

- sound must work after each step
- no breaking working functionality
- implement minimal viable logic
- avoid abstractions
