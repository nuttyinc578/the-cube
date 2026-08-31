[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $PSScriptRoot '..\fall_music.mp3')
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$repoPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $destinationPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination must remain inside the repository: $destinationPath"
}

$sourceUrl = 'https://raw.githubusercontent.com/nuttyinc578/the-cube/e358db6992f456be8a19e8368dfc5ba21ce1e108/fall_music.mp3'
$expectedSha256 = '17b93051af84d00443ce32588bdf422e22f63306c7afd43712d4756e61baafe4'

if (Test-Path -LiteralPath $destinationPath) {
    $existingHash = (Get-FileHash -LiteralPath $destinationPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($existingHash -eq $expectedSha256) {
        Write-Host 'Verified Fall Edition music is already present.'
        return
    }
}

$temporaryPath = "$destinationPath.download"
try {
    Invoke-WebRequest -Uri $sourceUrl -OutFile $temporaryPath -Headers @{ 'User-Agent' = 'The-Cube-Beta-Release' }
    $downloadHash = (Get-FileHash -LiteralPath $temporaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($downloadHash -ne $expectedSha256) {
        throw "Fall Edition music checksum mismatch. Expected $expectedSha256, received $downloadHash."
    }
    Move-Item -LiteralPath $temporaryPath -Destination $destinationPath -Force
    Write-Host "Downloaded and verified Fall Edition music: $destinationPath"
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}
