param(
    [string]$Project = 'newsflow-verification-unattended-local',
    [int]$ApiPort = 18032, [int]$WebPort = 15199, [int]$ProductionPort = 18132
)
. (Join-Path $PSScriptRoot 'unattended-compose-common.ps1')
$context = Get-UnattendedContext $Project
foreach ($port in @($ApiPort, $WebPort, $ProductionPort)) {
    if ($port -lt 1024 -or $port -gt 65535 -or $port -eq 5432) { throw 'Invalid isolated verification port.' }
}
if ((@($ApiPort, $WebPort, $ProductionPort) | Select-Object -Unique).Count -ne 3) { throw 'Verification ports must differ.' }
if (Test-Path -LiteralPath $context.Directory) { throw 'Create-only fixture already exists; preserve it, never reseed.' }
# Refuse pre-existing containers/volumes in this exact family before writing files.
$containers = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon unavailable; no fixture data created.' }
$volumes = & docker volume ls -q --filter "label=com.docker.compose.project=$Project"
if ($LASTEXITCODE -ne 0 -or $containers -or $volumes) { throw 'Refusing pre-existing isolated project storage.' }
foreach ($name in @('postgres_data', 'redis_data', 'frontend_node_modules', 'media_data')) {
    $named = & docker volume ls -q --filter "name=$($Project)_$name"
    if ($LASTEXITCODE -ne 0 -or $named) { throw 'Refusing any pre-existing fixture-named volume, even without labels.' }
}
New-Item -ItemType Directory -Path $context.Directory | Out-Null
New-Item -ItemType Directory -Path $context.Media | Out-Null
$encoding = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($context.Key, 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=', $encoding)
$environment = @"
POSTGRES_DB=newsflow_unattended_ci
POSTGRES_USER=newsflow_fixture
POSTGRES_PASSWORD=synthetic-unattended-ci-only
DATABASE_URL=postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@postgres:5432/newsflow_unattended_ci
REDIS_URL=redis://redis:6379/0
NEWSFLOW_ENV_FILE=$($context.EnvFile.Replace('\', '/'))
NEWSFLOW_MASTER_KEY_SOURCE=$($context.Key.Replace('\', '/'))
NEWSFLOW_API_PORT=$ApiPort
NEWSFLOW_WEB_PORT=$WebPort
NEWSFLOW_PROD_WEB_PORT=$ProductionPort
NEWSFLOW_BIND_HOST=127.0.0.1
NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED=0
NEWSFLOW_TELEGRAM_INGESTION_ENABLED=0
NEWSFLOW_REWRITE_ENABLED=0
NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED=0
NEWSFLOW_INTERNET_MEDIA_ENABLED=0
NEWSFLOW_SOURCE_PHOTO_ENABLED=0
NEWSFLOW_PUBLICATION_ENABLED=0
"@
[IO.File]::WriteAllText($context.EnvFile, $environment, $encoding)
$mediaJson = ConvertTo-Json $context.Media.Replace('\', '/') -Compress
$override = @"
services:
  postgres:
    ports: ["127.0.0.1:5432:5432"]
  api:
    volumes:
      - type: bind
        source: $mediaJson
        target: /var/lib/newsflow/media
        read_only: true
  worker:
    volumes:
      - type: bind
        source: $mediaJson
        target: /var/lib/newsflow/media
"@
[IO.File]::WriteAllText($context.Override, $override, $encoding)
$ownership = @{ version = 1; owner = 'content-studio-unattended-v1'; project = $Project;
    nonce = [Guid]::NewGuid().ToString('N'); api_port = $ApiPort; web_port = $WebPort; production_port = $ProductionPort }
[IO.File]::WriteAllText($context.Ownership, ($ownership | ConvertTo-Json -Compress), $encoding)
$null = Assert-UnattendedOwnership $context
Invoke-UnattendedCompose $context @('up', '-d', '--build', '--wait', '--wait-timeout', '180')
# Host pytest controls actual durable services in a new schema. Packaged API/worker
# use the same isolated DB but its empty public foundation, with all network flags 0.
# Persistent test media lives inside the exact host directory bind-mounted above.
$priorTarget = $env:NEWSFLOW_UNATTENDED_POSTGRES_URL
$priorProject = $env:NEWSFLOW_UNATTENDED_RESTART_PROJECT
try {
    $env:NEWSFLOW_UNATTENDED_POSTGRES_URL = 'postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@127.0.0.1:5432/newsflow_unattended_ci'
    $env:NEWSFLOW_UNATTENDED_RESTART_PROJECT = $Project
    Push-Location (Join-Path $context.Root 'backend')
    try {
        $testTemp = [IO.Path]::GetFullPath((Join-Path $context.Media 'pytest'))
        & python -m pytest tests/test_unattended_vertical_slice.py -k floodwait -q -s --basetemp $testTemp
        if ($LASTEXITCODE -ne 0) { throw 'Combined unattended Compose acceptance failed; retain original fixture.' }
    } finally { Pop-Location }
} finally {
    $env:NEWSFLOW_UNATTENDED_POSTGRES_URL = $priorTarget
    $env:NEWSFLOW_UNATTENDED_RESTART_PROJECT = $priorProject
}
Invoke-UnattendedCompose $context @('exec', '-T', 'worker', 'python', '-m', 'alembic', 'check')
Write-Output "Synthetic combined unattended acceptance passed; stack/storage retained: $Project"
Write-Output 'No live Telegram authorization, AI calls or actual publications. Linux is not Windows proof.'
