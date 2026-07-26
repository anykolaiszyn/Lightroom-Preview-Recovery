param(
    [string]$Python
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist'
$package = Join-Path $dist 'Lightroom Preview Recovery'
$outputDirectory = Join-Path $root 'outputs'
$output = Join-Path $outputDirectory 'Lightroom-Preview-Recovery-Windows.zip'

function Resolve-BuildPython {
    param([string]$Requested)

    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "Requested -Python was not found: $Requested"
        }
        return $Requested
    }
    if ($env:LRPR_PYTHON) {
        if (-not (Test-Path -LiteralPath $env:LRPR_PYTHON -PathType Leaf)) {
            throw "LRPR_PYTHON was set but not found: $env:LRPR_PYTHON"
        }
        return $env:LRPR_PYTHON
    }
    $localVenvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $localVenvPython -PathType Leaf) {
        return $localVenvPython
    }
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }
    throw (
        'Could not resolve a Python interpreter to build with. Pass -Python, ' +
        'set LRPR_PYTHON, create a project .venv, or put python on PATH.'
    )
}

$python = Resolve-BuildPython -Requested $Python

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }

$workPath = Join-Path $root 'build'
& $python -m PyInstaller --clean --noconfirm `
    --distpath $dist --workpath $workPath `
    (Join-Path $root 'packaging\LightroomPreviewRecovery.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$builtOnedir = Join-Path $dist 'LightroomPreviewRecovery'
if (-not (Test-Path -LiteralPath $builtOnedir -PathType Container)) {
    throw "Expected onedir build output was not found: $builtOnedir"
}

if (Test-Path -LiteralPath $package) {
    Remove-Item -LiteralPath $package -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $package | Out-Null
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Copy-Item (Join-Path $builtOnedir '*') $package -Recurse -Force
Copy-Item (Join-Path $root 'assets\README.html') $package -Force
Copy-Item (Join-Path $root 'assets\LICENSES.txt') $package -Force
Copy-Item (Join-Path $root 'assets\licenses') (Join-Path $package 'licenses') -Recurse -Force
if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
Compress-Archive -LiteralPath $package -DestinationPath $output -Force
Write-Host "Created $output"
