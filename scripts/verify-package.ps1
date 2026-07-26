$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$archive = Join-Path $root 'outputs\Lightroom-Preview-Recovery-Windows.zip'
$verificationRoot = Join-Path $root 'work\package-verification'
$packageRoot = Join-Path $verificationRoot 'Lightroom Preview Recovery'

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "Package archive was not found: $archive"
}
if (Test-Path -LiteralPath $verificationRoot) {
    Remove-Item -LiteralPath $verificationRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $verificationRoot | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $verificationRoot -Force

if (-not (Test-Path -LiteralPath $packageRoot -PathType Container)) {
    throw 'Archive does not contain the expected Lightroom Preview Recovery folder.'
}

$exe = Join-Path $packageRoot 'LightroomPreviewRecovery.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Package is missing LightroomPreviewRecovery.exe: $exe"
}

$internal = Join-Path $packageRoot '_internal'
if (-not (Test-Path -LiteralPath $internal -PathType Container)) {
    throw "Package is missing the onedir _internal runtime folder: $internal"
}

$expectedTopLevel = @('_internal', 'licenses', 'LICENSES.txt', 'LightroomPreviewRecovery.exe', 'README.html')
$actualTopLevel = Get-ChildItem -LiteralPath $packageRoot |
    ForEach-Object { $_.Name } |
    Sort-Object
if (Compare-Object -ReferenceObject $expectedTopLevel -DifferenceObject $actualTopLevel -CaseSensitive) {
    throw "Unexpected top-level package contents: $($actualTopLevel -join ', ')"
}

$expectedLicenses = @(
    'licenses/OpenSSL-3.0-LICENSE.txt',
    'licenses/PyInstaller-COPYING.txt',
    'licenses/Python-3.12-LICENSE.txt',
    'licenses/TclTk-8.6-license.terms'
)
$actualLicenses = Get-ChildItem -LiteralPath (Join-Path $packageRoot 'licenses') -File |
    ForEach-Object { "licenses/$($_.Name)" } |
    Sort-Object
if (Compare-Object -ReferenceObject $expectedLicenses -DifferenceObject $actualLicenses -CaseSensitive) {
    throw "Unexpected license inventory: $($actualLicenses -join ', ')"
}

$forbidden = Get-ChildItem -LiteralPath $packageRoot -Recurse -Force | Where-Object {
    $_.Name -match '(?i)WD_BACKUP' -or $_.Name -match '(?i)\.(lrcat|lrprev|lrdata|jpg)$'
}
if ($forbidden) {
    throw "Archive contains forbidden source or recovered-data artifact(s): $($forbidden.FullName -join ', ')"
}

$process = $null
try {
    $process = Start-Process -FilePath $exe -PassThru
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $process.Refresh()
        if ($process.HasExited) {
            throw "Packaged application exited unexpectedly with code $($process.ExitCode)."
        }
    } until ($process.MainWindowHandle -ne 0 -or (Get-Date) -ge $deadline)

    if ($process.MainWindowHandle -eq 0) {
        Write-Warning (
            'Packaged application did not report a main window handle within ' +
            '30 seconds in this shell session. This check is known to be ' +
            'unreliable in noninteractive/remote shells even when the app is ' +
            'running correctly (see .superpowers/sdd/task-10-report.md). ' +
            'Confirm window visibility with a manual interactive launch ' +
            'before treating this as a failure.'
        )
    }
    else {
        if (-not $process.CloseMainWindow()) {
            throw 'Packaged application did not accept a clean close request.'
        }
        if (-not $process.WaitForExit(10000)) {
            throw 'Packaged application did not close within 10 seconds.'
        }
    }
}
finally {
    if ($process -and -not $process.HasExited) {
        $process.Kill()
        $process.WaitForExit()
    }
}

Write-Host "Verified $archive"
