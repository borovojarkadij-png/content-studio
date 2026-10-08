param(
    [string]$Project = 'newsflow-verification-local',
    [int]$ApiPort = 18000,
    [int]$WebPort = 15173,
    [int]$ProductionPort = 18080,
    [switch]$CrashRecovery,
    [switch]$RewriteRecovery,
    [switch]$SourceGuard,
    [switch]$SemanticGuard,
    [switch]$MediaGuard,
    [switch]$IngestionGuard,
    [switch]$PeerGuard,
    [switch]$MappingGuard,
    [switch]$ResolutionGuard,
    [switch]$SourcePhotoGuard,
    [switch]$PublicationGuard,
    [switch]$ChannelSyncGuard,
    [switch]$AdmissionGuard,
    [ValidateSet('OPENAI', 'OPENROUTER')]
    [string]$RewriteProvider = 'OPENAI'
)

$ErrorActionPreference = 'Stop'
if ($AdmissionGuard -and ($ChannelSyncGuard -or $RewriteRecovery -or $SourceGuard -or
    $SemanticGuard -or $MediaGuard -or $IngestionGuard -or $PeerGuard -or $MappingGuard -or
    $ResolutionGuard -or $SourcePhotoGuard -or $PublicationGuard)) {
    throw 'AdmissionGuard requires a separate fresh fixture; never mix retained recovery families.'
}
function Invoke-AdmissionProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_admission_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic admission probe failed: $Mode" }
}
if ($ChannelSyncGuard -and ($RewriteRecovery -or $SourceGuard -or $SemanticGuard -or
    $MediaGuard -or $IngestionGuard -or $PeerGuard -or $MappingGuard -or
    $ResolutionGuard -or $SourcePhotoGuard -or $PublicationGuard)) {
    throw 'ChannelSyncGuard requires a separate fresh fixture; durable global enforcement cannot be undone.'
}
function Invoke-ChannelSyncProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_channel_sync_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic channel sync probe failed: $Mode" }
}
function Invoke-RewriteSyncWaitProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_rewrite_sync_wait_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic rewrite sync wait probe failed: $Mode" }
}
if ($MediaGuard -and -not $SemanticGuard) {
    throw 'MediaGuard requires a fresh synthetic SemanticGuard run.'
}
function Invoke-MediaProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_media_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic media probe failed: $Mode" }
}
function Invoke-SourcePhotoProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_source_photo_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic source photo probe failed: $Mode" }
}
function Invoke-PublicationProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_publication_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic publication probe failed: $Mode" }
}
function Invoke-IngestionProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_ingestion_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic ingestion probe failed: $Mode" }
}
function Invoke-PeerProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_telegram_peer_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic encrypted peer probe failed: $Mode" }
}
function Invoke-MappingProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_mapping_filter_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic mapping filter probe failed: $Mode" }
}
function Invoke-ResolutionProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_donor_resolution_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic donor resolution probe failed: $Mode" }
}
if ($SourceGuard -and -not $RewriteRecovery) {
    throw 'SourceGuard requires a fresh synthetic RewriteRecovery run.'
}
function Invoke-SemanticProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_semantic_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic semantic probe failed: $Mode" }
}
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
NEWSFLOW_VERIFICATION_REWRITE_PROVIDER=$RewriteProvider
NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED=0
NEWSFLOW_TELEGRAM_INGESTION_ENABLED=0
NEWSFLOW_REWRITE_ENABLED=0
NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED=0
NEWSFLOW_INTERNET_MEDIA_ENABLED=0
NEWSFLOW_SOURCE_PHOTO_ENABLED=0
NEWSFLOW_PUBLICATION_ENABLED=0
"@
[IO.File]::WriteAllText($envPath, $envText, [Text.UTF8Encoding]::new($false))
$networkPath = Join-Path $fixtureDirectory 'network.yaml'
if (-not (Test-Path -LiteralPath $networkPath)) {
    # Linux Engine permits the exact-IP holder only on explicitly configured IPAM.
    # This override belongs to the isolated fixture, never the operational stack.
    $subnet = "10.$(Get-Random -Minimum 16 -Maximum 240).$(Get-Random -Minimum 0 -Maximum 256).0/24"
    $networkText = "networks:`n  default:`n    ipam:`n      config:`n        - subnet: $subnet`n"
    [IO.File]::WriteAllText($networkPath, $networkText, [Text.UTF8Encoding]::new($false))
}
$composeArgs = @('compose', '-p', $Project, '--env-file', $envPath,
    '-f', (Join-Path $root 'compose.yaml'), '-f', (Join-Path $root 'compose.dev.yaml'),
    '-f', $networkPath,
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
function Invoke-RewriteRecoveryProbe([string]$Mode) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_rewrite_recovery_probe.py') -Raw |
        & docker @composeArgs exec -T worker python - $Mode
    if ($LASTEXITCODE -ne 0) { throw "Synthetic rewrite recovery probe failed: $Mode" }
}

Invoke-VerificationCompose config --quiet
Invoke-VerificationCompose up -d --build --wait --wait-timeout 180
Invoke-Probe 'seed'
if ($PeerGuard) { Invoke-PeerProbe 'seed' }
$priorApi = & docker @composeArgs ps -q api
$priorProxy = & docker @composeArgs ps -q web-production
$priorIp = & docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $priorApi
if ($LASTEXITCODE -ne 0 -or $priorIp -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw 'Could not resolve isolated API address.'
}
# Force an actual upstream address change, not merely a new container at the same IP.
Invoke-VerificationCompose stop api
Invoke-VerificationCompose rm -f api
$holderName = "$Project-dns-holder-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
$holder = & docker run -d --name $holderName --network "${Project}_default" --ip $priorIp redis:7-alpine sleep 300
if ($LASTEXITCODE -ne 0 -or $holder -notmatch '^[a-f0-9]{64}$') { throw 'Could not reserve test IP.' }
try {
    Invoke-VerificationCompose up -d --no-deps --wait --wait-timeout 180 api
    $newApi = & docker @composeArgs ps -q api
    $newIp = & docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $newApi
    if ($LASTEXITCODE -ne 0 -or $newIp -eq $priorIp) { throw 'Test did not change API address.' }
    if ((& docker @composeArgs ps -q web-production) -ne $priorProxy) {
        throw 'Proxy was unexpectedly recreated during DNS recovery verification.'
    }
    $recreatedHealth = Invoke-RestMethod "http://127.0.0.1:$ProductionPort/healthz"
    if ($recreatedHealth.status -ne 'ok') { throw 'Proxy lost its recreated API upstream.' }
    $recreatedInbox = Invoke-RestMethod "http://127.0.0.1:$ProductionPort/api/telegram/incoming-posts"
    if ($recreatedInbox.items.Count -ne 1) { throw 'Recreated API inbox read lost fixture data.' }
    Write-Output 'Proxy followed changed API IP without proxy restart.'
} finally {
    # Only the exact disposable holder created above; no volume/user data attached.
    & docker rm -f $holder | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not remove the disposable DNS test holder.' }
}
Invoke-VerificationCompose exec -T redis redis-cli set synthetic-persistence-marker retained
Invoke-VerificationCompose restart redis worker
Invoke-Probe 'verify'
Invoke-VerificationCompose down
# Deliberately no --volumes: named persistent storage must survive container removal.
Invoke-VerificationCompose up -d --wait --wait-timeout 180
Invoke-Probe 'verify'
if ($PeerGuard) { Invoke-PeerProbe 'verify' }
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
    if ($PeerGuard) { Invoke-PeerProbe 'verify' }
}
$health = Invoke-RestMethod "http://127.0.0.1:$ProductionPort/healthz"
if ($health.status -ne 'ok') { throw 'Production proxy health check failed.' }
if ($RewriteRecovery) {
    # This terminal acceptance intentionally completes the fixture's pending job.
    # Use a fresh isolated project for each full recovery run, never a real stack.
    Invoke-RewriteRecoveryProbe 'claim'
    Invoke-VerificationCompose restart worker
    Write-Output 'Waiting for the persisted 60-second claim to expire (synthetic provider only).'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-RewriteRecoveryProbe 'recover'
    Invoke-VerificationCompose restart worker
    Invoke-RewriteRecoveryProbe 'verify'
    if ($SourceGuard) {
        Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_source_guard_probe.py') -Raw |
            & docker @composeArgs exec -T worker python -
        if ($LASTEXITCODE -ne 0) { throw 'Synthetic source-edit guard failed.' }
    }
}
if ($SemanticGuard) {
    Invoke-SemanticProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Write-Output 'Waiting for the synthetic semantic verification lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-SemanticProbe 'recover'
    Invoke-VerificationCompose restart worker
    Invoke-SemanticProbe 'verify'
    if ($MediaGuard) {
        Invoke-MediaProbe 'seed'
        Invoke-VerificationCompose down
        Invoke-VerificationCompose up -d --wait --wait-timeout 180
        Write-Output 'Waiting for the synthetic media acquisition lease to expire.'
        for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
        Invoke-MediaProbe 'recover'
        Invoke-VerificationCompose restart worker
        Invoke-MediaProbe 'verify'
    }
    Invoke-SemanticProbe 'revoke'
    if ($MediaGuard) { Invoke-MediaProbe 'blocked' }
}
if ($ResolutionGuard) { Invoke-ResolutionProbe 'seed' }
if ($IngestionGuard) {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'docker_telegram_health_probe.py') -Raw |
        & docker @composeArgs exec -T worker python -
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic PostgreSQL Telegram health lock probe failed.' }
    Invoke-IngestionProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Write-Output 'Waiting for the synthetic donor polling lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-IngestionProbe 'recover'
    if ($ResolutionGuard) { Invoke-ResolutionProbe 'recover' }
    Invoke-VerificationCompose restart worker
    Invoke-IngestionProbe 'verify'
    Invoke-IngestionProbe 'edit'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-IngestionProbe 'verify-edit'
    if ($ResolutionGuard) { Invoke-ResolutionProbe 'verify' }
} elseif ($ResolutionGuard) {
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Write-Output 'Waiting for the synthetic import resolution lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-ResolutionProbe 'recover'
    Invoke-VerificationCompose restart worker
    Invoke-ResolutionProbe 'verify'
}
if ($MappingGuard) {
    Invoke-MappingProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-MappingProbe 'verify'
}
if ($SourcePhotoGuard) {
    Invoke-SourcePhotoProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Write-Output 'Waiting for the synthetic source-photo lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-SourcePhotoProbe 'recover'
    Invoke-VerificationCompose restart worker
    Invoke-SourcePhotoProbe 'verify'
    Invoke-SourcePhotoProbe 'blocked'
}
if ($PublicationGuard) {
    Invoke-PublicationProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Write-Output 'Waiting for the synthetic publication lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-PublicationProbe 'recover'
    Invoke-PublicationProbe 'quota'
    Invoke-VerificationCompose restart worker
    Invoke-PublicationProbe 'verify-pending'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-PublicationProbe 'verify'
    Invoke-VerificationCompose restart worker
    Invoke-PublicationProbe 'verify'
}
if ($ChannelSyncGuard) {
    Invoke-ChannelSyncProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-ChannelSyncProbe 'verify-pending'
    Write-Output 'Waiting for the retained synthetic channel difference lease to expire.'
    for ($tick = 0; $tick -lt 13; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-ChannelSyncProbe 'recover'
    Invoke-VerificationCompose restart redis worker
    Invoke-ChannelSyncProbe 'verify'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-ChannelSyncProbe 'verify'
    if ($CrashRecovery) {
        Invoke-VerificationCompose kill -s SIGKILL postgres
        Invoke-VerificationCompose up -d --wait --wait-timeout 180
        Invoke-ChannelSyncProbe 'verify'
    }
    Invoke-ChannelSyncProbe 'concurrency'
    Invoke-RewriteSyncWaitProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-RewriteSyncWaitProbe 'verify-pending'
    Write-Output 'Waiting for the original synthetic sync/rewrite retry to become due.'
    for ($tick = 0; $tick -lt 7; $tick++) { Start-Sleep -Seconds 5 }
    Invoke-RewriteSyncWaitProbe 'recover'
    Invoke-VerificationCompose restart worker
    Invoke-RewriteSyncWaitProbe 'verify'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-RewriteSyncWaitProbe 'verify'
}
if ($AdmissionGuard) {
    Invoke-AdmissionProbe 'seed'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-AdmissionProbe 'verify-pending'
    Invoke-AdmissionProbe 'admit'
    Invoke-VerificationCompose restart redis worker
    Invoke-AdmissionProbe 'verify'
    Invoke-VerificationCompose down
    Invoke-VerificationCompose up -d --wait --wait-timeout 180
    Invoke-AdmissionProbe 'verify'
    if ($CrashRecovery) {
        Invoke-VerificationCompose kill -s SIGKILL postgres
        Invoke-VerificationCompose up -d --wait --wait-timeout 180
        Invoke-AdmissionProbe 'verify'
    }
}
Write-Output "Synthetic persistence checks passed. Stack retained: $Project"
Write-Output 'No real Telegram authorization, network AI calls or publications.'
