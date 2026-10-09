param(
    [ValidateSet('create', 'verify', 'restart', 'preflight', 'crash')][string]$Mode = 'create',
    [string]$Project = 'newsflow-verification-illustration-win-20261009a',
    [int]$ApiPort = 18237, [int]$WebPort = 15394, [int]$ProductionPort = 18337
)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'illustration_restart_controller.py') $Mode --project $Project --ports $ApiPort $WebPort $ProductionPort
if ($LASTEXITCODE -ne 0) { throw 'Owned illustration verification failed/refused; preserve original fixture.' }
