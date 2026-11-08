param([Parameter(Mandatory=$true)][ValidateSet('demo','persistent-demo','live')][string]$Mode)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe scripts/runtime.py stop --mode $Mode
if ($LASTEXITCODE -ne 0) { throw 'Stop failed. No data volumes were removed.' }
