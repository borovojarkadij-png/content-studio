param([Parameter(Mandatory)][string]$Project, [switch]$CrashRecovery)
. (Join-Path $PSScriptRoot 'unattended-compose-common.ps1')
$context = Get-UnattendedContext $Project
$owner = Assert-UnattendedOwnership $context
# Only retained owned synthetic storage. Never down --volumes, prune, reset or reseed.
Invoke-UnattendedCompose $context @('down')
Invoke-UnattendedCompose $context @('up', '-d', '--wait', '--wait-timeout', '180')
Invoke-UnattendedCompose $context @('restart', 'redis', 'worker')
if ($CrashRecovery) {
    Invoke-UnattendedCompose $context @('kill', '-s', 'SIGKILL', 'postgres')
    Invoke-UnattendedCompose $context @('up', '-d', '--wait', '--wait-timeout', '180')
}
$health = Invoke-RestMethod "http://127.0.0.1:$($owner.production_port)/healthz"
if ($health.status -ne 'ok') { throw 'Isolated production proxy health failed after restart.' }
Write-Output 'Synthetic full-stack restart completed; original storage and key retained.'
