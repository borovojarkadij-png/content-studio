param([Parameter(Mandatory)][string]$Project, [switch]$CrashRecovery)
. (Join-Path $PSScriptRoot 'unattended-compose-common.ps1')
$stage = 'CONTEXT'
try {
$context = Get-UnattendedContext $Project
$stage = 'OWNERSHIP'
$owner = Assert-UnattendedOwnership $context
# Only retained owned synthetic storage. Never down --volumes, prune, reset or reseed.
$stage = 'DOWN'
Invoke-UnattendedCompose $context @('down')
$stage = 'UP'
Invoke-UnattendedCompose $context @('up', '-d', '--wait', '--wait-timeout', '180')
$stage = 'REDIS_WORKER'
Invoke-UnattendedCompose $context @('restart', 'redis', 'worker')
if ($CrashRecovery) {
    $stage = 'POSTGRES_CRASH'
    Invoke-UnattendedCompose $context @('kill', '-s', 'SIGKILL', 'postgres')
    $stage = 'POSTGRES_RECOVERY'
    Invoke-UnattendedCompose $context @('up', '-d', '--wait', '--wait-timeout', '180')
}
$stage = 'HEALTH'
$health = Invoke-RestMethod "http://127.0.0.1:$($owner.production_port)/healthz"
if ($health.status -ne 'ok') { throw 'Isolated production proxy health failed after restart.' }
Write-Output 'Synthetic full-stack restart completed; original storage and key retained.'
} catch {
    # Fixed stage and numeric source line only; captured output may contain secrets.
    Write-Output "UNATTENDED_FAILURE stage=$stage line=$([int]$_.InvocationInfo.ScriptLineNumber)"
    throw
}
