# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [Parameter(Mandatory=$true)][string]$Manifest,
    [string]$Cache,
    [switch]$SkipFFmpeg,
    [switch]$ForceFFmpeg
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.IO.Compression.FileSystem
$taskRoot = [IO.Path]::GetFullPath($Destination)
$taskManifest = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
if (-not $Cache) { $Cache = Join-Path $taskRoot 'downloads' }
$taskCache = [IO.Path]::GetFullPath($Cache)
New-Item -ItemType Directory -Path $taskRoot,$taskCache -Force | Out-Null

function Get-PackageHash($File) {
    $taskAlgorithm = [Security.Cryptography.SHA256]::Create()
    $taskStream = [IO.File]::OpenRead($File)
    try { return [BitConverter]::ToString($taskAlgorithm.ComputeHash($taskStream)).Replace('-','').ToLowerInvariant() }
    finally { $taskStream.Dispose(); $taskAlgorithm.Dispose() }
}

function Get-VerifiedPackage($Package) {
    $taskUri = [Uri]$Package.url
    if ($taskUri.Scheme -ne 'https' -or $taskUri.Host -notin @('www.python.org','files.pythonhosted.org','www.gyan.dev')) {
        throw 'Dependency URL is outside the publisher allowlist.'
    }
    if ($Package.filename -ne [IO.Path]::GetFileName($Package.filename) -or $Package.sha256 -notmatch '^[0-9a-f]{64}$') {
        throw 'Invalid dependency manifest.'
    }
    $taskFile = Join-Path $taskCache $Package.filename
    if (Test-Path -LiteralPath $taskFile) {
        if ((Get-PackageHash $taskFile) -eq $Package.sha256) { return $taskFile }
        Remove-Item -LiteralPath $taskFile
    }
    Write-Output "Downloading $($Package.name)..." | Out-Host
    $taskClient = New-Object Net.WebClient
    try { $taskClient.DownloadFile($Package.url,$taskFile) } finally { $taskClient.Dispose() }
    if ((Get-PackageHash $taskFile) -ne $Package.sha256) {
        Remove-Item -LiteralPath $taskFile
        throw "Publisher SHA-256 check failed for $($Package.name)."
    }
    return $taskFile
}

function Expand-VerifiedArchive($Archive, $Target) {
    # Check all paths before extracting any content, including wheel archives.
    $taskTarget = [IO.Path]::GetFullPath($Target).TrimEnd('\') + '\'
    $taskZip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $taskZip.Entries) {
            $taskEntry = [IO.Path]::GetFullPath((Join-Path $taskTarget $entry.FullName))
            if (-not $taskEntry.StartsWith($taskTarget,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe archive path.' }
        }
        foreach ($entry in $taskZip.Entries) {
            $taskEntry = Join-Path $taskTarget $entry.FullName
            if ($entry.FullName.EndsWith('/')) { New-Item -ItemType Directory -Path $taskEntry -Force | Out-Null; continue }
            New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($taskEntry)) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$taskEntry,$true)
        }
    } finally { $taskZip.Dispose() }
}

try {
    $taskRuntime = Join-Path $taskRoot 'runtime'
    $taskSite = Join-Path $taskRuntime 'Lib\site-packages'
    foreach ($package in $taskManifest.packages) {
        if ($package.kind -eq 'ffmpeg') {
            $taskExistingFFmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
            $taskExistingProbe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
            if ($SkipFFmpeg -or (-not $ForceFFmpeg -and $taskExistingFFmpeg -and $taskExistingProbe)) { continue }
            $taskArchive = Get-VerifiedPackage $package
            $taskFFmpeg = Join-Path $taskRoot 'ffmpeg-package'
            Expand-VerifiedArchive $taskArchive $taskFFmpeg
            $taskPackageRoot = Get-ChildItem -LiteralPath $taskFFmpeg -Directory | Select-Object -First 1
            if (-not $taskPackageRoot -or -not (Test-Path -LiteralPath (Join-Path $taskPackageRoot.FullName 'bin\ffprobe.exe'))) { throw 'Incomplete FFmpeg package.' }
            New-Item -ItemType Directory -Path (Join-Path $taskRoot 'bin') -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $taskPackageRoot.FullName 'bin\ffmpeg.exe'),(Join-Path $taskPackageRoot.FullName 'bin\ffprobe.exe') -Destination (Join-Path $taskRoot 'bin')
            # Keep the publisher's notices next to its installed dependency.
            $taskNotices = Join-Path $taskRoot 'dependency-notices\ffmpeg'
            New-Item -ItemType Directory -Path $taskNotices -Force | Out-Null
            foreach ($notice in Get-ChildItem -LiteralPath $taskPackageRoot.FullName) {
                if ($notice.Name -ne 'bin') { Copy-Item -LiteralPath $notice.FullName -Destination $taskNotices -Recurse }
            }
        } else {
            $taskArchive = Get-VerifiedPackage $package
            $taskTarget = if ($package.kind -eq 'python') { $taskRuntime } else { $taskSite }
            Expand-VerifiedArchive $taskArchive $taskTarget
        }
    }
    $taskPth = Get-ChildItem -LiteralPath $taskRuntime -Filter 'python*._pth' | Select-Object -First 1
    if (-not $taskPth) { throw 'Embedded Python runtime is incomplete.' }
    $taskPythonZip = (Get-ChildItem -LiteralPath $taskRuntime -Filter 'python*.zip' | Select-Object -First 1).Name
    [IO.File]::WriteAllText($taskPth.FullName, "$taskPythonZip`n.`nLib/site-packages`n..`nimport site`n", [Text.Encoding]::ASCII)
    & (Join-Path $taskRuntime 'python.exe') -B -c 'from PySide6.QtWidgets import QApplication; from PySide6.QtMultimedia import QMediaPlayer; from PySide6.QtOpenGL import QOpenGLShaderProgram; import ssl'
    if ($LASTEXITCODE -ne 0) { throw 'Runtime dependency import check failed.' }
    $taskStamp = Join-Path $taskRoot 'runtime-installed.json'
    $taskManifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $taskStamp -Encoding UTF8
    Write-Output 'Runtime verified. No system Python or PATH changes were made.'
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
