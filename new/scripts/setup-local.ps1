$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$webDir = Join-Path $repoRoot 'new\web'
$backendDir = Join-Path $repoRoot 'new\person2-backend'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'

$nodeVersion = (& node --version).Trim()
if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v?(\d+)\.(\d+)\.') {
    throw 'Node.js 20.19 or newer is required.'
}
$nodeMajor = [int]$Matches[1]
$nodeMinor = [int]$Matches[2]
if ($nodeMajor -lt 20 -or ($nodeMajor -eq 20 -and $nodeMinor -lt 19)) {
    throw "Node.js 20.19 or newer is required; found $nodeVersion."
}

& py -3.12 --version
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.12 is required. Install it and make sure the Python launcher (py) is available.'
}

Push-Location $backendDir
try {
    if (-not (Test-Path $python)) {
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the backend virtual environment.' }
    }

    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }

    & $python -m pip install -e ..\person1-retrieval ..\person3-generation-evaluation
    if ($LASTEXITCODE -ne 0) { throw 'Retrieval or generation package installation failed.' }

    if (-not (Test-Path .env) -and (Test-Path .env.example)) {
        Copy-Item .env.example .env
    }
}
finally {
    Pop-Location
}

Push-Location $webDir
try {
    if (Test-Path node_modules) {
        & npm.cmd ls --depth=0
        if ($LASTEXITCODE -ne 0) {
            $modulePath = [System.IO.Path]::GetFullPath((Join-Path $webDir 'node_modules'))
            $webProcesses = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
                Where-Object {
                    $_.CommandLine -and
                    $_.CommandLine.IndexOf($modulePath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
                }
            if ($webProcesses) {
                throw 'Web dependencies need reinstalling, but a web process is using them. Stop the web server and rerun this command.'
            }

            & npm.cmd ci
            if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
        }
    }
    else {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed.' }
    }

    if (-not (Test-Path .env) -and (Test-Path .env.example)) {
        Copy-Item .env.example .env
    }
}
finally {
    Pop-Location
}

Write-Host 'Project dependencies installed. Configure PostgreSQL in new\person2-backend\.env before starting the API.'
