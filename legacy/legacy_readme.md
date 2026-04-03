# About folder /legacy

Folder /legacy contains legacy experimental implementations.

## Rules:
- Do not reuse directly
- Use only as reference
- Current architecture is defined in ARCHITECTURE.md
- Legacy code may violate current rules

## Stage I

First and only try with real VPS. 

In the end of this Stage I no errors/bugs were occurred during tests with python console Publisher and Listener UI (VPS based)

Include:
* legacy/stage_I/deployment.md
* legacy/stage_I/index.html
* legacy/stage_I/publisher.py

## Stage IV

Well done working Publisher UI v0.2 and Listener UI without backend (only LiveKit Server), without multi-publisher room

In the end of this Stage IV no errors/bugs were occurred during tests with Publisher UI and Listener UI (localhost)

Include:
* legacy/stage_IV/index.html
* legacy/stage_IV/ui_test_livekit.py
* legacy/stage_IV/audio_steam.py
* legacy/stage_IV/rms_detector.py