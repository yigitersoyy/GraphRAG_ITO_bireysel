param([switch]$SkipSync, [switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Python 3.12 is required. Install it with the Windows Python launcher (py).'
}
& py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is not installed.' }
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) { $uvPath = $uvCommand.Source }
else {
    $uvPath = Join-Path (Get-Location) '.tools\Scripts\uv.exe'
    if (-not (Test-Path -LiteralPath $uvPath)) {
        & py -3.12 -m venv .tools
        if ($LASTEXITCODE -ne 0) { throw 'Cannot create the local tool environment.' }
        & .\.tools\Scripts\python.exe -m pip install 'uv==0.13.7'
        if ($LASTEXITCODE -ne 0) { throw 'Cannot install uv. Check network access.' }
    }
}
if (-not $SkipSync) {
    & $uvPath sync --frozen --python 3.12 --group dev
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
    Write-Host 'Created .env. Set NEO4J_PASSWORD and exact model IDs before persistent/live mode.'
} else { Write-Host 'Existing .env preserved.' }
if (-not $SkipFrontend) {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Node.js 24 with npm is required for the workspace UI. Install Node.js, or use -SkipFrontend for backend-only setup.' }
    & .\.venv\Scripts\python.exe -c "from scripts.runtime import build_frontend; build_frontend()"
    if ($LASTEXITCODE -ne 0) { throw 'Workspace UI build failed.' }
}
Write-Host 'Ready. Start demo: .\scripts\start.ps1 -Mode demo'
