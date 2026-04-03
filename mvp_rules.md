# MVP rules for current stage

Goal: working multi-publisher audio engine

Do NOT implement:

- advanced UI design
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
- channels = floor, rus, eng
- room_status = OPENED always
- JWT lifetime = 5h

Scope:

- max 3 channels required for MVP test
- scaling to 32 channels only after logic proven
- minimal UI (functional only)
- console logging allowed
- no performance optimization yet

Rules:

- sound must work after each step
- no breaking working functionality
- implement minimal viable logic
- avoid abstractions
- skip risks of race by time difference (use timestamps as it is) 