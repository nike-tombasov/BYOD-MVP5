param(
  [string]$PythonExe = "python",
  [string]$Backend = "ws://127.0.0.1:8000/ws/publisher",
  [string]$Pin = "123456"
)

$ErrorActionPreference = "Stop"

Write-Host "[build] Installing runtime + packaging deps"
& $PythonExe -m pip install -r src/requirements.txt pyinstaller==6.13.0

Write-Host "[build] Cleaning old artifacts"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "[build] Building Publisher one-dir executable"
& $PythonExe -m PyInstaller src/publisher/packaging/publisher_onedir.spec --noconfirm --clean

$launcher = @"
@echo off
set BACKEND=$Backend
set PIN=$Pin
start "" BYODPublisher.exe --backend %BACKEND% --pin %PIN%
"@

$target = "dist/BYODPublisher"
Set-Content -Path "$target/start_publisher.bat" -Value $launcher -Encoding ASCII

Write-Host "[build] Done. Output folder: dist/BYODPublisher"
