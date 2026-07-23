param(
    [switch]$SkipManifestGeneration
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeParent = Join-Path $repoRoot "desktop\runtime"
$target = Join-Path $runtimeParent "python"
$policyPath = Join-Path $repoRoot "desktop\runtime-policy.json"
$requirementsPath = Join-Path $repoRoot "desktop\runtime-requirements.txt"
$hostPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$policy = Get-Content -Raw -LiteralPath $policyPath | ConvertFrom-Json
$staging = Join-Path $runtimeParent ("python.build-" + [Guid]::NewGuid().ToString("N"))
$backup = Join-Path $runtimeParent ("python.previous-" + [Guid]::NewGuid().ToString("N"))

function Assert-ChildPath {
    param([string]$Candidate)
    $parentFull = [System.IO.Path]::GetFullPath($runtimeParent).TrimEnd("\") + "\"
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe runtime path: $candidateFull"
    }
}

Assert-ChildPath $target
Assert-ChildPath $staging
Assert-ChildPath $backup

if (-not (Test-Path -LiteralPath $hostPython)) {
    throw "The repository .venv Python is required to install pinned Windows wheels."
}

try {
    New-Item -ItemType Directory -Path $staging | Out-Null
    $archive = Join-Path $staging "python-embed.zip"
    Write-Host "Downloading the official CPython embeddable distribution..."
    Invoke-WebRequest -Uri $policy.source.url -OutFile $archive
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$policy.source.sha256).ToLowerInvariant()) {
        throw "CPython archive SHA-256 does not match desktop/runtime-policy.json."
    }

    Expand-Archive -LiteralPath $archive -DestinationPath $staging
    Remove-Item -LiteralPath $archive

    $pthPath = Join-Path $staging "python312._pth"
    @(
        "python312.zip"
        "."
        "Lib\site-packages"
        "import site"
    ) | Set-Content -LiteralPath $pthPath -Encoding ascii

    $sitePackages = Join-Path $staging "Lib\site-packages"
    New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
    Write-Host "Installing pinned binary runtime dependencies..."
    & $hostPython -m pip install `
        --requirement $requirementsPath `
        --target $sitePackages `
        --only-binary=:all: `
        --no-compile `
        --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned runtime dependency installation failed."
    }

    Write-Host "Warming the pinned runtime imports before hashing..."
    & (Join-Path $staging "python.exe") -c @"
import einops
import fastapi
import huggingface_hub
import joblib
import lightgbm
import numpy
import onnxruntime
import pandas
import psycopg
import pydantic
import requests
import safetensors
import sklearn
import torch
import tqdm
import uvicorn
import websockets
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Private runtime import warmup failed."
    }

    $previousBytecodeSetting = $env:PYTHONDONTWRITEBYTECODE
    $env:PYTHONDONTWRITEBYTECODE = "1"
    try {
        & (Join-Path $staging "python.exe") -c "import platform; assert platform.python_version() == '3.12.10'; assert platform.architecture()[0] == '64bit'"
    } finally {
        $env:PYTHONDONTWRITEBYTECODE = $previousBytecodeSetting
    }
    if ($LASTEXITCODE -ne 0) {
        throw "The staged private runtime failed its version/architecture check."
    }

    if (Test-Path -LiteralPath $target) {
        Move-Item -LiteralPath $target -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $target
    if (Test-Path -LiteralPath $backup) {
        Remove-Item -LiteralPath $backup -Recurse -Force
    }

    if (-not $SkipManifestGeneration) {
        Push-Location $repoRoot
        try {
            npm run runtime:manifests
            if ($LASTEXITCODE -ne 0) {
                throw "Runtime manifest generation failed."
            }
        } finally {
            Pop-Location
        }
    }

    Write-Host "Private Python 3.12.10 x64 runtime staged successfully."
} catch {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    throw
}
