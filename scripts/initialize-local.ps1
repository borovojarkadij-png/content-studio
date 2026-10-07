$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envPath = Join-Path $root '.env'
$keyPath = Join-Path $root 'secrets/newsflow_master_key'
# Explicit one-time provisioning only; never invoked by container startup.
if (-not (Test-Path -LiteralPath $keyPath)) {
    if (Test-Path -LiteralPath $envPath) {
        throw 'Existing .env but no master key. Recover the original key; refusing replacement.'
    }
    $existingVolumes = & docker volume ls --filter label=com.docker.compose.project=newsflow --format '{{.Name}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker must be available to check existing state.' }
    if ($existingVolumes) {
        throw 'Existing NewsFlow volumes detected without a key. Recover the original key first.'
    }
    & (Join-Path $PSScriptRoot 'initialize-secrets.ps1')
    if (-not (Test-Path -LiteralPath $keyPath)) { throw 'Master-key provisioning failed.' }
}
try {
    $storedKey = (Get-Content -LiteralPath $keyPath -Raw).Trim().Replace('-', '+').Replace('_', '/')
    if ([Convert]::FromBase64String($storedKey).Length -ne 32) { throw 'Invalid size' }
} catch {
    throw 'Existing master key is unreadable/malformed; refusing to replace it.'
}
if (Test-Path -LiteralPath $envPath) {
    Write-Output 'Existing .env and stable master key retained; no credentials replaced.'
    return
}
$passwordBytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($passwordBytes)
$databasePassword = [Convert]::ToHexString($passwordBytes).ToLowerInvariant()
$envText = @"
POSTGRES_DB=newsflow
POSTGRES_USER=newsflow
POSTGRES_PASSWORD=$databasePassword
DATABASE_URL=postgresql+psycopg://newsflow:$databasePassword@postgres:5432/newsflow
REDIS_URL=redis://redis:6379/0
"@
[IO.File]::WriteAllText($envPath, $envText, [Text.UTF8Encoding]::new($false))
Write-Output 'Local .env provisioned once. Neither it nor the master key belongs in Git.'
Write-Output 'Back up the key separately and securely before storing Telegram sessions/provider keys.'
