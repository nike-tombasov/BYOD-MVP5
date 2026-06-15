param(
  [string]$PythonExe = "python",
  [string]$Backend = "ws://127.0.0.1:8000/ws/publisher",
  [string]$Pin = "123456"
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..\..")

# Проверьте, где реально лежит requirements.txt
$requirements = Join-Path $repoRoot "src\requirements.txt"
$spec = Join-Path $repoRoot "src\publisher\packaging\publisher_onedir.spec"

if (!(Test-Path $spec)) {
  throw "Spec file not found: $spec"
}

Write-Host "[build] Repo root: $repoRoot"
Write-Host "[build] Spec: $spec"

# Если requirements.txt отсутствует, сборка не должна молча продолжаться
if (Test-Path $requirements) {
  Write-Host "[build] Installing runtime + packaging deps"
  & $PythonExe -m pip install -r $requirements pyinstaller==6.13.0
  if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }
} else {
  Write-Host "[build] Requirements file not found: $requirements"
  Write-Host "[build] Skipping pip install step"
}

Write-Host "[build] Cleaning old artifacts"
Remove-Item -Recurse -Force (Join-Path $repoRoot "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $repoRoot "dist") -ErrorAction SilentlyContinue

Write-Host "[build] Building Publisher one-dir executable"
& $PythonExe -m PyInstaller $spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$target = Join-Path $repoRoot "dist\BYODPublisher"
New-Item -ItemType Directory -Force -Path $target | Out-Null

$launcher = @"
@echo off
set BACKEND=$Backend
set PIN=$Pin
start "" BYODPublisher.exe --backend %BACKEND% --pin %PIN%
"@

Set-Content -Path (Join-Path $target "start_publisher.bat") -Value $launcher -Encoding ASCII

Write-Host "[build] Done. Output folder: $target"