# Publisher Windows packaging (Stage VI)

This folder provides reproducible **onedir** packaging for Publisher UI.

## Build command (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File src/publisher/packaging/build_windows_onedir.ps1
```

Optional parameters:

```powershell
powershell -ExecutionPolicy Bypass -File src/publisher/packaging/build_windows_onedir.ps1 \
  -PythonExe py \
  -Backend ws://10.0.0.12:8000/ws/publisher \
  -Pin 123456
```

## Output

Build output is created in:

- `dist/BYODPublisher/BYODPublisher.exe`
- `dist/BYODPublisher/start_publisher.bat`

Use `start_publisher.bat` on operator PC to run with predefined backend/PIN.

## Local state location

Publisher stores local JSON state in:

- Windows: `%APPDATA%\BYODPublisher\state.json`
- non-Windows fallback: `~/.byod_publisher/state.json`

Stored fields:

- `backend_ws_url`
- `pin`
- `device_map` (`channel_id` -> selected device label)

## Git policy

Do **not** commit `dist/` or `build/` artifacts (already ignored by repository `.gitignore`).
Commit only source and packaging scripts/specs.
