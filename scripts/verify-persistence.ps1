param(
    [string]$Project = 'newsflow-verification-local',
    [int]$ApiPort = 18000,
    [int]$WebPort = 15173,
    [int]$ProductionPort = 18080,
    [switch]$CrashRecovery
)

$ErrorActionPreference = 'Stop'
if ($Project -notmatch '^newsflow-verification-[a-z0-9-]+$') {
    throw 'Only an isolated newsflow-verification-* project is permitted.'
}
foreach ($port in @($ApiPort, $WebPort, $ProductionPort)) {
    if ($port -lt 1024 -or $port -gt 65535) { throw 'Invalid verification port.' }
}
if ((@($ApiPort, $WebPort, $ProductionPort) | Select-Object -Unique).Count -ne 3) {
    throw 'Verification ports must be different.'
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fixtureDirectory = Join-Path $root ".artifacts/docker-verification/$Project"
New-Item -ItemType Directory -Force -Path $fixtureDirectory | Out-Null
$keyPath = Join-Path $fixtureDirectory 'synthetic-master-key'
$envPath = Join-Path $fixtureDirectory 'test.env'
# This public, deterministic fixture key is NEVER a production/session key.
$syntheticKey = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
if (Test-Path -LiteralPath $keyPath) {
    if ((Get-Content -LiteralPath $keyPath -Raw).Trim() -ne $syntheticKey) {
        throw 'Unexpected fixture key; refusing to replace any existing key.'
    }
} else {
    [IO.File]::WriteAllText($keyPath, $syntheticKey, [Text.UTF8Encoding]::new($false))
}
$envText = @"
POSTGRES_DB=newsflow_verification
POSTGRES_USER=newsflow_verification
POSTGRES_PASSWORD=synthetic_docker_verification_password
DATABASE_URL=postgresql+psycopg://newsflow_verification:synthetic_docker_verification_password@postgres:5432/newsflow_verification
REDIS_URL=redis://redis:6379/0
NEWSFLOW_ENV_FILE=$($envPath.Replace('\', '/'))
NEWSFLOW_MASTER_KEY_SOURCE=$($keyPath.Replace('\', '/'))
NEWSFLOW_API_PORT=$ApiPort
NEWSFLOW_WEB_PORT=$WebPort
NEWSFLOW_PROD_WEB_PORT=$ProductionPort
NEWSFLOW_VERIFICATION_PROBE=1
"@
[IO.File]::WriteAllText($envPath, $envText, [Text.UTF8Encoding]::new($false))
$composeArgs = @('compose', '-p', $Project, '--env-file', $envPath,
    '-f', (Join-Path $root 'compose.yaml'), '-f', (Join-Path $root 'compose.dev.yaml'),
    '--profile', 'dev', '--profile', 'production')
function Invoke-VerificationCompose {
    & docker @composeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "Compose failed with exit code $LASTEXITCODE" }
}
function Invoke-Probe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_persistence_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Persistence probe failed: $Mode" }
}

Invoke-VerificationCompose config --quiet
Invoke-VerificationCompose up -d --build --wait --wait-timeout 180
Invoke-Probe 'seed'
Invoke-VerificationCompose exec -T redis redis-cli set synthetic-persistence-marker retained
Invoke-VerificationCompose restart redis worker
Invoke-Probe 'verify'
Invoke-VerificationCompose down
# Deliberately no --volumes: named persistent storage must survive container removal.
Invoke-VerificationCompose up -d --wait --wait-timeout 180
Invoke-Probe 'verify'
$marker = & docker @composeArgs exec -T redis redis-cli get synthetic-persistence-marker
if ($LASTEXITCODE -ne 0 -or $marker.Trim() -ne 'retained') {
    throw 'Redis AOF marker did not survive restart/down-up.'
}
if ($CrashRecovery) {
    # Only the explicitly named synthetic stack is affected. Never run on real data.
    Invoke-VerificationCompose kill -s SIGKILL postgres
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-Probe 'verify'
    Invoke-VerificationCompose exec -T redis redis-cli FLUSHDB
    Invoke-Probe 'verify'
}
$health = Invoke-RestMethod "http://127.0.0.1:$ProductionPort/healthz"
if ($health.status -ne 'ok') { throw 'Production proxy health check failed.' }
Write-Output "Synthetic persistence checks passed. Stack retained: $Project"
Write-Output 'No Telegram authorization, AI calls or publications; job persistence is not execution recovery.'
