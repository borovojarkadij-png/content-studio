# Test-only guarded targets shared by the create-only launcher and restart hook.
$ErrorActionPreference = 'Stop'
function Get-UnattendedContext([string]$Project) {
    if ($Project.Length -gt 64 -or $Project -notmatch '^newsflow-verification-unattended-[a-z0-9]+(?:-[a-z0-9]+)*$') {
        throw 'Only the dedicated isolated unattended project family is permitted.'
    }
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $fixture = [IO.Path]::GetFullPath((Join-Path $repoRoot ".artifacts/docker-verification/$Project"))
    foreach ($path in @((Join-Path $repoRoot '.artifacts'), (Join-Path $repoRoot '.artifacts/docker-verification'), $fixture)) {
        if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Fixture path must not redirect to other storage.'
        }
    }
    [pscustomobject]@{
        Project = $Project; Root = $repoRoot; Directory = $fixture
        EnvFile = (Join-Path $fixture 'test.env')
        Override = (Join-Path $fixture 'compose.override.yaml')
        Key = (Join-Path $fixture 'synthetic-master-key')
        Media = (Join-Path $fixture 'media')
        Ownership = (Join-Path $fixture 'ownership.json')
        ComposeArgs = @('compose', '-p', $Project, '--env-file', (Join-Path $fixture 'test.env'),
            '-f', (Join-Path $repoRoot 'compose.yaml'), '-f', (Join-Path $repoRoot 'compose.dev.yaml'),
            '-f', (Join-Path $fixture 'compose.override.yaml'), '--profile', 'dev', '--profile', 'production')
    }
}

function Assert-UnattendedOwnership($Context) {
    if (-not (Test-Path -LiteralPath $Context.Media -PathType Container) -or
        ((Get-Item -LiteralPath $Context.Media).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Original persistent media storage is missing or redirected.'
    }
    foreach ($path in @($Context.Ownership, $Context.EnvFile, $Context.Override, $Context.Key)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Original fixture ownership/config/key is missing or redirected; never recreate it.'
        }
    }
    if ((Get-Item -LiteralPath $Context.Ownership).Length -gt 4096) { throw 'Invalid fixture ownership.' }
    $owner = Get-Content -LiteralPath $Context.Ownership -Raw | ConvertFrom-Json
    if (($owner.version -isnot [int] -and $owner.version -isnot [long]) -or
        $owner.version -ne 1 -or $owner.project -cne $Context.Project -or
        $owner.owner -cne 'content-studio-unattended-v1' -or
        $owner.nonce -isnot [string] -or $owner.nonce -notmatch '^[a-f0-9]{32}$') { throw 'Invalid fixture ownership; preserve existing data.' }
    $ports = @($owner.api_port, $owner.web_port, $owner.production_port)
    foreach ($port in $ports) {
        if (($port -isnot [int] -and $port -isnot [long]) -or $port -lt 1024 -or $port -gt 65535 -or $port -eq 5432) {
            throw 'Invalid original fixture ports.'
        }
    }
    if (($ports | Select-Object -Unique).Count -ne 3) { throw 'Invalid original fixture ports.' }
    if ((Get-Content -LiteralPath $Context.Key -Raw).Trim() -cne 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=') {
        throw 'Unexpected key; never replace or mount a real key.'
    }
    $composeArgs = $Context.ComposeArgs
    $raw = & docker @composeArgs config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Could not validate isolated Compose configuration.' }
    $config = ($raw -join "`n") | ConvertFrom-Json
    $serviceNames = @($config.services.PSObject.Properties.Name | Sort-Object)
    if (($serviceNames -join ',') -cne 'api,migrations,postgres,redis,web,web-production,worker') {
        throw 'Refusing unexpected full-stack services.'
    }
    $expectedUrl = 'postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@postgres:5432/newsflow_unattended_ci'
    if ($config.name -cne $Context.Project -or
        $config.services.postgres.environment.POSTGRES_DB -cne 'newsflow_unattended_ci' -or
        $config.services.postgres.environment.POSTGRES_USER -cne 'newsflow_fixture' -or
        $config.services.postgres.environment.POSTGRES_PASSWORD -cne 'synthetic-unattended-ci-only' -or
        $config.services.postgres.image -cne 'postgres:16-alpine' -or
        $config.services.postgres.command -or $config.services.postgres.entrypoint -or
        $config.volumes.postgres_data.name -cne "$($Context.Project)_postgres_data" -or
        $config.volumes.postgres_data.external) { throw 'Refusing a non-synthetic database/volume target.' }
    $pgMount = @($config.services.postgres.volumes)
    if ($pgMount.Count -ne 1 -or $pgMount[0].type -ne 'volume' -or
        $pgMount[0].source -cne 'postgres_data' -or $pgMount[0].target -cne '/var/lib/postgresql/data') {
        throw 'Refusing foreign PostgreSQL storage.'
    }
    foreach ($serviceName in @('api', 'worker', 'migrations')) {
        $environment = $config.services.$serviceName.environment
        if ($environment.DATABASE_URL -cne $expectedUrl) { throw 'Refusing a foreign service database.' }
        foreach ($flag in @('NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED', 'NEWSFLOW_TELEGRAM_INGESTION_ENABLED',
            'NEWSFLOW_REWRITE_ENABLED', 'NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED', 'NEWSFLOW_INTERNET_MEDIA_ENABLED',
            'NEWSFLOW_SOURCE_PHOTO_ENABLED', 'NEWSFLOW_PUBLICATION_ENABLED')) {
            if ([string]$environment.$flag -cne '0') { throw 'Network/provider workers must remain disabled.' }
        }
    }
    $mountedKey = [IO.Path]::GetFullPath($config.secrets.newsflow_master_key.file)
    if ($mountedKey -cne $Context.Key) { throw 'Refusing a foreign master key mount.' }
    foreach ($serviceName in @('api', 'worker')) {
        $mount = @($config.services.$serviceName.volumes | Where-Object { $_.target -eq '/var/lib/newsflow/media' })
        if ($mount.Count -ne 1 -or $mount[0].type -ne 'bind' -or
            [IO.Path]::GetFullPath($mount[0].source) -cne $Context.Media) { throw 'Refusing foreign media storage.' }
    }
    if (-not ($config.services.postgres.ports | Where-Object { $_.host_ip -eq '127.0.0.1' -and $_.published -eq '5432' -and $_.target -eq 5432 })) {
        throw 'Explicit loopback synthetic PostgreSQL port required.'
    }
    return $owner
}

function Invoke-UnattendedCompose($Context, [string[]]$Arguments) {
    $composeArgs = $Context.ComposeArgs
    & docker @composeArgs @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Isolated Compose failed with exit code $LASTEXITCODE; preserve fixture." }
}
