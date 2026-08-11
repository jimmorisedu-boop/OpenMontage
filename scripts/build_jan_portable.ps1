[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$DispatchHostedBuild,
    [switch]$InstallArtifact,
    [switch]$ProbePortableBoundary,
    [string]$ProbeExecutable,
    [ValidateRange(1, 60)]
    [int]$ProbeSeconds = 8
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifestPath = Join-Path $repoRoot 'config\runtime\artifacts.json'
$workflowRelative = '.github/workflows/build-portable-jan.yml'
$workflowPath = Join-Path $repoRoot $workflowRelative
$patchPath = Join-Path $repoRoot 'integrations\jan\patches\0001-openmontage-shell.patch'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$jan = $manifest.jan

if ($manifest.runtime_policy -ne 'checksummed-only') {
    throw 'Portable artifacts must use the checksummed-only policy.'
}
if ($jan.source_url -match '/latest(?:/|$)' -or $jan.source_sha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'Jan source URL and SHA-256 are not immutable.'
}
if (-not (Test-Path -LiteralPath $workflowPath)) {
    throw "Hosted Jan workflow is missing: $workflowRelative"
}
if (-not (Test-Path -LiteralPath $patchPath)) {
    throw 'OpenMontage Jan patch is missing.'
}

if ($ValidateOnly) {
    [pscustomobject]@{
        status = 'valid'
        builder = 'github-actions'
        workflow = $workflowRelative
        tag = $jan.tag
        commit = $jan.commit
        source_sha256 = $jan.source_sha256
        output = (Join-Path $repoRoot $jan.output)
    } | ConvertTo-Json
    exit 0
}

if ($DispatchHostedBuild) {
    $branch = (git -C $repoRoot branch --show-current).Trim()
    if (-not $branch) { throw 'The hosted build requires a named Git branch.' }
    gh workflow run 'build-portable-jan.yml' --repo 'jimmorisedu-boop/OpenMontage' --ref $branch
    if ($LASTEXITCODE -ne 0) { throw 'GitHub rejected the portable Jan workflow dispatch.' }
    Write-Output "Dispatched portable Jan build for $branch"
}

$outputPath = Join-Path $repoRoot $jan.output
$runtimeRoot = Join-Path $repoRoot 'runtime'
$downloadDir = Join-Path $runtimeRoot 'downloads'
$janDir = Split-Path $outputPath -Parent

if ($InstallArtifact) {
    if (-not $jan.portable_url -or $jan.portable_sha256 -notmatch '^[0-9a-f]{64}$') {
        throw 'Portable Jan release URL/hash are not pinned in config/runtime/artifacts.json.'
    }
    New-Item -ItemType Directory -Force -Path $downloadDir, $janDir | Out-Null
    $partial = Join-Path $downloadDir 'OpenMontage-Jan.exe.partial'
    Invoke-WebRequest -Uri $jan.portable_url -OutFile $partial
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $partial).Hash.ToLowerInvariant()
    if ($actual -ne $jan.portable_sha256.ToLowerInvariant()) {
        throw "Portable Jan SHA-256 mismatch. Expected $($jan.portable_sha256), got $actual."
    }
    Move-Item -LiteralPath $partial -Destination $outputPath -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot 'integrations\jan\LICENSE.upstream') -Destination (Join-Path $janDir 'LICENSE.jan.txt') -Force
    Write-Output "Installed portable Jan at $outputPath"
}

if ($ProbePortableBoundary) {
    $probePath = if ($ProbeExecutable) { $ProbeExecutable } else { $outputPath }
    if (-not (Test-Path -LiteralPath $probePath)) {
        throw "Portable Jan is missing: $probePath"
    }

    $externalCandidates = @(
        (Join-Path $env:APPDATA 'Jan'),
        (Join-Path $env:APPDATA 'jan.ai.app'),
        (Join-Path $env:LOCALAPPDATA 'Jan'),
        (Join-Path $env:LOCALAPPDATA 'jan.ai.app'),
        (Join-Path $env:USERPROFILE '.jan')
    )
    function Get-BoundarySnapshot {
        $items = foreach ($candidate in $externalCandidates) {
            if (Test-Path -LiteralPath $candidate) {
                Get-ChildItem -LiteralPath $candidate -Recurse -Force -File |
                    ForEach-Object { "$($_.FullName)|$($_.Length)|$($_.LastWriteTimeUtc.Ticks)" }
            }
        }
        return @($items | Sort-Object)
    }

    $before = @(Get-BoundarySnapshot)
    $localAppData = Join-Path $runtimeRoot 'jan-data\appdata'
    $localLocalAppData = Join-Path $runtimeRoot 'jan-data\localappdata'
    $localTemp = Join-Path $runtimeRoot 'temp\jan-probe'
    New-Item -ItemType Directory -Force -Path $localAppData, $localLocalAppData, $localTemp | Out-Null
    $oldAppData = $env:APPDATA
    $oldLocalAppData = $env:LOCALAPPDATA
    $oldTemp = $env:TEMP
    $oldTmp = $env:TMP
    $oldOpenMontageDataRoot = $env:OPENMONTAGE_JAN_DATA_ROOT
    $oldWebViewDataFolder = $env:WEBVIEW2_USER_DATA_FOLDER
    try {
        $env:APPDATA = $localAppData
        $env:LOCALAPPDATA = $localLocalAppData
        $env:TEMP = $localTemp
        $env:TMP = $localTemp
        $env:OPENMONTAGE_JAN_DATA_ROOT = Join-Path $runtimeRoot 'jan-data'
        $env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $runtimeRoot 'jan-data\webview2'
        $process = Start-Process -FilePath $probePath -PassThru
        try {
            if (-not $process.WaitForExit($ProbeSeconds * 1000)) {
                Stop-Process -Id $process.Id -Force
                $process.WaitForExit()
            }
        } finally {
            if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
        }
    } finally {
        $env:APPDATA = $oldAppData
        $env:LOCALAPPDATA = $oldLocalAppData
        $env:TEMP = $oldTemp
        $env:TMP = $oldTmp
        $env:OPENMONTAGE_JAN_DATA_ROOT = $oldOpenMontageDataRoot
        $env:WEBVIEW2_USER_DATA_FOLDER = $oldWebViewDataFolder
    }
    $after = @(Get-BoundarySnapshot)
    $difference = Compare-Object -ReferenceObject $before -DifferenceObject $after
    if ($difference) {
        $details = ($difference | ForEach-Object InputObject) -join [Environment]::NewLine
        throw "Portable Jan wrote persistent state outside the repository:`n$details"
    }
    Write-Output 'Portable Jan boundary probe passed.'
}

if (-not ($DispatchHostedBuild -or $InstallArtifact -or $ProbePortableBoundary)) {
    throw 'Choose -ValidateOnly, -DispatchHostedBuild, -InstallArtifact, or -ProbePortableBoundary.'
}
