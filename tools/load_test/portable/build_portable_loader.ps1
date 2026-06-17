[CmdletBinding()]
param(
    [string]$PythonEmbedZip,
    [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$DistRoot = Join-Path $RepoRoot "dist"
$OutDir = Join-Path $DistRoot "BYOD-Loader-Portable-Win64"
$ZipPath = Join-Path $DistRoot "BYOD-Loader-Portable-Win64.zip"
$PythonDir = Join-Path $OutDir "python"
$SitePackages = Join-Path $PythonDir "Lib\site-packages"
$AppDir = Join-Path $OutDir "app"
$LogsDir = Join-Path $OutDir "logs"
$Requirements = Join-Path $RepoRoot "tools\load_test\requirements.txt"
$Loader = Join-Path $RepoRoot "tools\load_test\byod_listener_loader.py"
$PortableDir = Join-Path $RepoRoot "tools\load_test\portable"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    Write-Host "==> $Name"
    & $Script
}

function Get-PythonEmbedZip {
    param([string]$DestinationDir)

    if ($PythonEmbedZip) {
        $resolved = (Resolve-Path $PythonEmbedZip).Path
        Write-Host "Using local embedded Python zip: $resolved"
        return $resolved
    }

    $zipName = "python-$PythonVersion-embed-amd64.zip"
    $downloadUrl = "https://www.python.org/ftp/python/$PythonVersion/$zipName"
    $downloadPath = Join-Path $DestinationDir $zipName
    Write-Host "Downloading official Python embeddable package: $downloadUrl"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadPath
    return $downloadPath
}

Invoke-Step "Prepare clean output folder" {
    if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    New-Item -ItemType Directory -Force -Path $DistRoot, $PythonDir, $SitePackages, $AppDir, $LogsDir | Out-Null
}

Invoke-Step "Install embedded CPython runtime" {
    $embedZip = Get-PythonEmbedZip -DestinationDir $DistRoot
    Expand-Archive -Path $embedZip -DestinationPath $PythonDir -Force
}

Invoke-Step "Install Loader dependencies into portable site-packages" {
    py -3.11 -m pip install -r $Requirements --target $SitePackages --upgrade
}

Invoke-Step "Copy Loader app and launcher templates" {
    Copy-Item $Loader (Join-Path $AppDir "byod_listener_loader.py") -Force
    Copy-Item (Join-Path $PortableDir "run_loader.bat.template") (Join-Path $OutDir "run_loader.bat") -Force
    Copy-Item (Join-Path $PortableDir "run_loader_args.bat.template") (Join-Path $OutDir "run_loader_args.bat") -Force
    Copy-Item (Join-Path $PortableDir "README_RU.md.template") (Join-Path $OutDir "README_RU.md") -Force
}

Invoke-Step "Configure embedded Python import paths" {
    $pthFiles = @(Get-ChildItem -Path $PythonDir -Filter "python*._pth" -File)
    if ($pthFiles.Count -gt 0) {
        $pthPath = $pthFiles[0].FullName
    } else {
        $pthPath = Join-Path $PythonDir "python311._pth"
    }

    $expectedPthLines = @(
        ".",
        "python311.zip",
        "Lib\site-packages",
        "..\app",
        "import site"
    )

    $expectedPthLines | Set-Content -Path $pthPath -Encoding ASCII

    $actualPthLines = @(Get-Content -Path $pthPath)
    foreach ($requiredLine in $expectedPthLines) {
        if ($actualPthLines -notcontains $requiredLine) {
            throw "Embedded Python ._pth validation failed: missing '$requiredLine' in $pthPath"
        }
    }

    Write-Host "Wrote and validated $pthPath"
}

Invoke-Step "Validate Loader --help with portable Python" {
    & (Join-Path $PythonDir "python.exe") (Join-Path $AppDir "byod_listener_loader.py") --help
    if ($LASTEXITCODE -ne 0) { throw "Portable Loader --help validation failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Validate generated direct BAT launcher" {
    cmd /c "`"$OutDir\run_loader_args.bat`" --help"
    if ($LASTEXITCODE -ne 0) { throw "Generated run_loader_args.bat validation failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Print portable Python sys.path" {
    & (Join-Path $PythonDir "python.exe") -c "import sys; print('\n'.join(sys.path))"
    if ($LASTEXITCODE -ne 0) { throw "Portable sys.path diagnostic failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Validate portable dependency imports" {
    & (Join-Path $PythonDir "python.exe") -c "import websockets; from livekit import rtc; import livekit.api; print('OK')"
    if ($LASTEXITCODE -ne 0) { throw "Portable dependency import validation failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Validate LiveKit runtime basics" {
    & (Join-Path $PythonDir "python.exe") -c "from livekit import rtc; room = rtc.Room(); print('ROOM_OK')"
    if ($LASTEXITCODE -ne 0) { throw "Portable LiveKit runtime validation failed with exit code $LASTEXITCODE" }
}

Invoke-Step "Create output zip" {
    Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -Force
}

Write-Host ""
Write-Host "Portable Loader folder: $OutDir"
Write-Host "Portable Loader zip:    $ZipPath"
