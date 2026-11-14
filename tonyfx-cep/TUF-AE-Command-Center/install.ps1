$ErrorActionPreference = "Stop"

$source = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$cepRoot = Join-Path $env:APPDATA "Adobe\CEP\extensions"
$target = Join-Path $cepRoot "TUF-AE-Command-Center"
$cacheParent = Join-Path $env:LOCALAPPDATA "Temp\cep_cache"

if (-not (Test-Path -LiteralPath (Join-Path $source "CSXS\manifest.xml"))) {
    throw "The CEP manifest is missing from $source"
}

New-Item -ItemType Directory -Force -Path $cepRoot | Out-Null

# Mirror the package so files removed from newer builds cannot linger in CEP.
if (Test-Path -LiteralPath $target) {
    $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
    $resolvedCepRoot = (Resolve-Path -LiteralPath $cepRoot).Path
    if (-not $resolvedTarget.StartsWith($resolvedCepRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace an extension outside $resolvedCepRoot"
    }
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

# Clear TonyFX web caches for every supported AE host while preserving Local Storage.
if (Test-Path -LiteralPath $cacheParent) {
    $resolvedCacheParent = (Resolve-Path -LiteralPath $cacheParent).Path
    $cacheRoots = Get-ChildItem -LiteralPath $resolvedCacheParent -Directory -Filter "AEFT_*_com.tuf.ae.commandcenter.panel" -ErrorAction SilentlyContinue
    foreach ($cacheRoot in $cacheRoots) {
        $resolvedCache = $cacheRoot.FullName
        if (-not $resolvedCache.StartsWith($resolvedCacheParent + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to clear an unexpected CEP cache path: $resolvedCache"
        }
        foreach ($cacheName in @("Cache", "Code Cache", "GPUCache", "Session Storage")) {
            $cachePath = Join-Path $resolvedCache $cacheName
            if (Test-Path -LiteralPath $cachePath) {
                try {
                    Remove-Item -LiteralPath $cachePath -Recurse -Force -ErrorAction Stop
                }
                catch {
                    Write-Warning "Close the TonyFX panel, then run install.cmd again to clear: $cachePath"
                }
            }
        }
    }
}

# AE 2023 uses CEP 11; current AE 2025/2026 releases use the CEP 12 line.
foreach ($csxsVersion in @("11", "12")) {
    $debugKey = "HKCU:\Software\Adobe\CSXS.$csxsVersion"
    New-Item -Path $debugKey -Force | Out-Null
    New-ItemProperty -Path $debugKey -Name "PlayerDebugMode" -Value "1" -PropertyType String -Force | Out-Null
}

Write-Output "TonyFX installed to: $target"
Write-Output "Close any open TonyFX panel, then reopen Window > Extensions > TonyFX in AE 2023-2026."
