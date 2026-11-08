param(
    [Parameter(Mandatory=$true)][ValidateSet('demo','persistent-demo','live')][string]$Mode,
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [int]$BoltPort = 7687,
    [int]$Neo4jHttpPort = 7474,
    [switch]$NoUi,
    [switch]$Build
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run scripts/setup.ps1 first.' }
$runtimeArgs = @('scripts/runtime.py','start','--mode',$Mode,'--api-port',$ApiPort,'--ui-port',$UiPort,'--bolt-port',$BoltPort,'--neo4j-http-port',$Neo4jHttpPort)
if ($NoUi) { $runtimeArgs += '--no-ui' }
if ($Build) { $runtimeArgs += '--build' }
& .\.venv\Scripts\python.exe @runtimeArgs
if ($LASTEXITCODE -ne 0) { throw 'Start failed. See reports/runtime/ logs and scripts/doctor.py.' }
