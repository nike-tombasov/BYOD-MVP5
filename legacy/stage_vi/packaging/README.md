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


## Why previous package could fail to connect LiveKit

LiveKit Python SDK loads a native FFI library from `livekit.rtc.resources` (`livekit_ffi.dll` on Windows).
If PyInstaller spec does not collect `livekit.rtc` data/binaries, WS connect can still work, but LiveKit media connection fails.

Current spec explicitly collects:
- `collect_data_files("livekit.rtc")`
- `collect_dynamic_libs("livekit.rtc")`
- `collect_submodules("livekit.rtc")`

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

## Runtime logs file

Publisher appends timestamped important events into `logs.txt`:

- packaged (`.exe`) run: `dist/BYODPublisher/logs.txt` (near `BYODPublisher.exe`)
- source run: `src/publisher/logs.txt`

## Git policy

Do **not** commit `dist/` or `build/` artifacts (already ignored by repository `.gitignore`).
Commit only source and packaging scripts/specs.
