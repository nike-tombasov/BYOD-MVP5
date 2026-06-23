$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$DistRoot = Join-Path $Root "dist"
$PackageName = "BYOD-Loadgen-Portable-Win64"
$PackageDir = Join-Path $DistRoot $PackageName
$ZipPath = Join-Path $DistRoot "$PackageName.zip"

Remove-Item -Recurse -Force $PackageDir -ErrorAction SilentlyContinue
Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $PackageDir | Out-Null

go mod tidy
go test ./...
go build -trimpath -ldflags="-s -w" -o (Join-Path $PackageDir "byod-loadgen.exe") .\cmd\byod-loadgen

Copy-Item (Join-Path $Root "PORTABLE_RU.md") $PackageDir
if (Test-Path (Join-Path $Root "README_RU.md")) {
  Copy-Item (Join-Path $Root "README_RU.md") $PackageDir
}

$Wrappers = @{
  "run_a50_backend_now.bat" = @"
@echo off
set SERVER=http://161.104.18.27
set RUNNER_ID=win1
set LOADGEN_KEY=byod_loadgen_key_01
set START_AT=now
mkdir out\%RUNNER_ID%-a50 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode backend-ws-only ^
  -server %SERVER% ^
  -listeners 50 ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 50 ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-a50 ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%-a50
"@;
  "run_b50_livekit_now.bat" = @"
@echo off
set SERVER=http://161.104.18.27
set RUNNER_ID=win1
set LOADGEN_KEY=byod_loadgen_key_01
set START_AT=now
mkdir out\%RUNNER_ID%-b50 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-connect-only ^
  -server %SERVER% ^
  -listeners 50 ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 50 ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-b50 ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%-b50
"@;
  "run_c30_rtp_selected_now.bat" = @"
@echo off
set SERVER=http://161.104.18.27
set RUNNER_ID=win1
set LOADGEN_KEY=byod_loadgen_key_01
set START_AT=now
mkdir out\%RUNNER_ID%-c30 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-subscribe-discard-rtp ^
  -subscribe-mode selected ^
  -server %SERVER% ^
  -listeners 30 ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 30 ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-c30 ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%-c30
"@;
  "run_b100_livekit_at_time.bat" = @"
@echo off
set SERVER=http://161.104.18.27
set RUNNER_ID=win1
set LOADGEN_KEY=byod_loadgen_key_01
set START_AT=2026-06-22T22:30:00+03:00
mkdir out\%RUNNER_ID%-b100-sync 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-connect-only ^
  -server %SERVER% ^
  -listeners 100 ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 50 ^
  -burst-interval-ms 1000 ^
  -hold-sec 60 ^
  -target-wait-sec 30 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-b100-sync ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%-b100-sync
"@;
}

foreach ($Name in $Wrappers.Keys) {
  Set-Content -Path (Join-Path $PackageDir $Name) -Value $Wrappers[$Name] -Encoding ASCII
}

Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -Force
Write-Host "Created $ZipPath"
