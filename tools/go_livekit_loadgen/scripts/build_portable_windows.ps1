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

Copy-Item (Join-Path $Root "README.md") $PackageDir

$Wrappers = @{
  "run_a50_backend_now.bat" = @"
@echo off
set "SERVER=http://<VPS_IP>"
set "LOADGEN_KEY=byod_loadgen_key_01"
set "RUNNER_ID=PC1"
set "START_AT=now"
set "LISTENERS=50"
set "SETUP=a%LISTENERS%"
mkdir "out\%RUNNER_ID%_%SETUP%" 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode backend-ws-only ^
  -server %SERVER% ^
  -listeners %LISTENERS% ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size %LISTENERS% ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-%SETUP% ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%_%SETUP%
"@;
  "run_b50_livekit_now.bat" = @"
@echo off
set "SERVER=http://<VPS_IP>"
set "LOADGEN_KEY=byod_loadgen_key_01"
set "RUNNER_ID=PC1"
set "START_AT=now"
set "LISTENERS=50"
set "SETUP=b%LISTENERS%"
mkdir "out\%RUNNER_ID%_%SETUP%" 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-connect-only ^
  -server %SERVER% ^
  -listeners %LISTENERS% ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size %LISTENERS% ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-%SETUP% ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%_%SETUP%
"@;
  "run_c30_rtp_selected_now.bat" = @"
@echo off
set "SERVER=http://<VPS_IP>"
set "LOADGEN_KEY=byod_loadgen_key_01"
set "RUNNER_ID=PC1"
set "START_AT=now"
set "LISTENERS=30"
set "SETUP=c%LISTENERS%"
mkdir "out\%RUNNER_ID%_%SETUP%" 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-subscribe-discard-rtp ^
  -subscribe-mode selected ^
  -server %SERVER% ^
  -listeners %LISTENERS% ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size %LISTENERS% ^
  -burst-interval-ms 0 ^
  -hold-sec 45 ^
  -target-wait-sec 20 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-%SETUP% ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%_%SETUP%
"@;
  "run_c100_rtp_selected_slow.bat" = @"
@echo off
set "SERVER=http://<VPS_IP>"
set "LOADGEN_KEY=byod_loadgen_key_01"
set "RUNNER_ID=PC1"
set "START_AT=now"
set "LISTENERS=100"
set "SETUP=c%LISTENERS%"
mkdir "out\%RUNNER_ID%_%SETUP%" 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-subscribe-discard-rtp ^
  -subscribe-mode selected ^
  -server %SERVER% ^
  -listeners %LISTENERS% ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 5 ^
  -burst-interval-ms 5000 ^
  -hold-sec 1000 ^
  -target-wait-sec 30 ^
  -backend-connect-timeout-sec 15 ^
  -runner-id %RUNNER_ID%-%SETUP% ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%_%SETUP%
"@;
  "run_b100_livekit_at_time.bat" = @"
@echo off
set "SERVER=http://<VPS_IP>"
set "LOADGEN_KEY=byod_loadgen_key_01"
set "RUNNER_ID=PC1"
set "START_AT=2026-06-27T22:30:00+03:00"
set "LISTENERS=100"
set "SETUP=b%LISTENERS%_sync"
mkdir "out\%RUNNER_ID%_%SETUP%" 2>nul
byod-loadgen.exe ^
  -profile vps-nginx ^
  -mode livekit-connect-only ^
  -server %SERVER% ^
  -listeners %LISTENERS% ^
  -start-at %START_AT% ^
  -start-mode burst ^
  -burst-size 50 ^
  -burst-interval-ms 1000 ^
  -hold-sec 60 ^
  -target-wait-sec 30 ^
  -backend-connect-timeout-sec 10 ^
  -runner-id %RUNNER_ID%-%SETUP% ^
  -loadgen-key %LOADGEN_KEY% ^
  -out-dir out\%RUNNER_ID%_%SETUP%
"@;
}
foreach ($Name in $Wrappers.Keys) {
  Set-Content -Path (Join-Path $PackageDir $Name) -Value $Wrappers[$Name] -Encoding ASCII
}

Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -Force
Write-Host "Created $ZipPath"
