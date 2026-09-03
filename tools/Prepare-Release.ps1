[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '6.2.3'
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $repoRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$Program,
        [Parameter(ValueFromRemainingArguments)] [string[]]$Arguments
    )

    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program exited with code $LASTEXITCODE"
    }
}

function Remove-SafeChild {
    param([Parameter(Mandatory)] [string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

function Copy-FilteredTree {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Destination
    )

    $sourcePath = [System.IO.Path]::GetFullPath($Source)
    foreach ($file in Get-ChildItem -LiteralPath $sourcePath -Recurse -File) {
        $relative = [System.IO.Path]::GetRelativePath($sourcePath, $file.FullName)
        $segments = $relative -split '[\\/]'
        if ($segments -contains '__pycache__' -or
            $segments -contains '.pytest_cache' -or
            $segments -contains 'bin' -or
            $segments -contains 'obj' -or
            $segments -contains 'out' -or
            $segments -contains 'test' -or
            $segments -contains 'tests') {
            continue
        }
        if ($file.Name -in @('NUTTYMOD_TERMS.md', '_nuttymod_account_state.json', 'nuttymod_restart.flag', '.theme_state.json', '.cpe_channel.json')) {
            continue
        }
        if ($file.Name -like '*.bak' -or $file.Name -like '*.backup-*') {
            continue
        }

        $destinationFile = Join-Path $Destination $relative
        $destinationDirectory = Split-Path -Parent $destinationFile
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destinationFile -Force
    }
}

$distPath = Join-Path $repoRoot 'dist'
$installerOutputPath = Join-Path $repoRoot 'installer-output'
$stagingPath = Join-Path $repoRoot 'package-staging'
$releasePath = Join-Path $repoRoot 'release-download'

Remove-SafeChild $distPath
Remove-SafeChild $installerOutputPath
Remove-SafeChild $stagingPath
Remove-SafeChild $releasePath
New-Item -ItemType Directory -Path $distPath, $installerOutputPath, $stagingPath, $releasePath -Force | Out-Null

& (Join-Path $PSScriptRoot 'Get-FallMusic.ps1')
Invoke-Checked -Program 'python' -Arguments @('-m', 'PyInstaller', '--noconfirm', '--clean', 'summer_build.spec')

Push-Location -LiteralPath (Join-Path $repoRoot 'cpe\go-cache')
try {
    Invoke-Checked -Program 'go' -Arguments @('test', './...')
    $goOutput = Join-Path $distPath 'cpe\go-cache\bin\cpe-go-cache.exe'
    New-Item -ItemType Directory -Path (Split-Path -Parent $goOutput) -Force | Out-Null
    Invoke-Checked -Program 'go' -Arguments @('build', '-trimpath', '-o', $goOutput, '.')
}
finally {
    Pop-Location
}

Invoke-Checked -Program 'npm' -Arguments @('test', '--prefix', 'cpe\node-bridge')
Invoke-Checked -Program 'dotnet' -Arguments @('restore', 'cpe\CPE.AppHost\CPE.AppHost.csproj', '--nologo')
Invoke-Checked -Program 'dotnet' -Arguments @('build', 'cpe\CPE.AppHost\CPE.AppHost.csproj', '-c', 'Release', '--no-restore', '--nologo')

$javaOut = Join-Path $distPath 'cpe\java-client\out'
New-Item -ItemType Directory -Path $javaOut -Force | Out-Null
Invoke-Checked -Program 'javac' -Arguments @('-encoding', 'UTF-8', '-d', $javaOut, 'cpe\java-client\src\main\java\com\nuttyinc\cpe\CpeClient.java')

$authOutput = Join-Path $stagingPath 'nuttymod_auth.exe'
Invoke-Checked -Program 'go' -Arguments @('build', '-trimpath', '-o', $authOutput, 'addons\nuttymod_bootstrap\nuttymod_auth.go')

Copy-Item -LiteralPath 'README.md' -Destination (Join-Path $distPath 'README.md') -Force
Copy-Item -LiteralPath 'Run The Cube Beta CPE.cmd', 'Run CPE Aspire.cmd', 'Run CPE Java Client.cmd' -Destination $distPath -Force
Copy-FilteredTree (Join-Path $repoRoot 'addons') (Join-Path $distPath 'addons')
Copy-FilteredTree (Join-Path $repoRoot 'themes') (Join-Path $distPath 'themes')
Copy-Item -LiteralPath $authOutput -Destination (Join-Path $distPath 'addons\nuttymod_bootstrap\nuttymod_auth.exe') -Force
Copy-FilteredTree (Join-Path $repoRoot 'cpe') (Join-Path $distPath 'cpe')

$isccCandidates = @(
    $env:ISCC_PATH,
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
) | Where-Object { $_ }
$iscc = $isccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $iscc) {
    throw 'Inno Setup 6 was not found. Install it or set ISCC_PATH.'
}
Invoke-Checked -Program $iscc -Arguments @('installer\TheCubeBetaFall.iss')

$portableName = "The-Cube-Beta-Fall-$Version-Portable"
$portablePath = Join-Path $stagingPath $portableName
New-Item -ItemType Directory -Path $portablePath -Force | Out-Null
Copy-Item -Path (Join-Path $distPath '*') -Destination $portablePath -Recurse -Force
Copy-Item -LiteralPath 'LICENCE.txt', 'THIRD_PARTY_NOTICES.txt' -Destination $portablePath -Force

$portableZip = Join-Path $releasePath "$portableName.zip"
Compress-Archive -Path (Join-Path $portablePath '*') -DestinationPath $portableZip -CompressionLevel Optimal

$setupName = "The-Cube-Beta-Fall-$Version-Setup.exe"
$compiledSetup = Join-Path $installerOutputPath $setupName
if (-not (Test-Path -LiteralPath $compiledSetup)) {
    throw "Expected installer was not created: $compiledSetup"
}
Copy-Item -LiteralPath $compiledSetup -Destination (Join-Path $releasePath $setupName) -Force

$hashLines = Get-ChildItem -LiteralPath $releasePath -File |
    Sort-Object Name |
    ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $($_.Name)"
    }
[System.IO.File]::WriteAllLines((Join-Path $releasePath 'SHA256SUMS.txt'), $hashLines, [System.Text.Encoding]::ASCII)

Write-Host "Release files prepared in $releasePath"
Get-ChildItem -LiteralPath $releasePath -File | Select-Object Name, Length
