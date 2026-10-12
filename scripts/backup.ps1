param(
    [string]$Destination,
    [string]$ContainerId,
    [string]$ProjectName,
    [string]$Database,
    [string]$User,
    [int]$TimeoutSeconds = 120
)

# Loading an entrypoint as a helper must not execute work or prompt for values.
if ($MyInvocation.InvocationName -eq '.') { return }
$ErrorActionPreference = 'Stop'
try {
    . "$PSScriptRoot/postgres-backup-common.ps1"
    Assert-BackupInputs $ContainerId $ProjectName $User $TimeoutSeconds
    Assert-PostgresName $Database
    $destinationPath = Get-BackupPath $Destination
    if ([IO.File]::Exists($destinationPath) -or [IO.Directory]::Exists($destinationPath)) { throw 'existing' }
    $parent = [IO.Path]::GetDirectoryName($destinationPath)
    if (-not [IO.Directory]::Exists($parent)) { throw 'parent' }
    Assert-PostgresContainer $ContainerId $ProjectName $Database $User $TimeoutSeconds
    $version = Get-PostgresVersion $ContainerId $Database $User $TimeoutSeconds
    # New-Item without Force refuses an existing directory (including a racing creator).
    $null = New-Item -ItemType Directory -Path $destinationPath
    $archivePath = [IO.Path]::Combine($destinationPath, 'database.dump')
    $output = [IO.File]::Open($archivePath, [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        Invoke-BackupNative @('exec', $ContainerId, 'pg_dump', '--format=custom',
            '--no-owner', '--no-privileges', "--username=$User", "--dbname=$Database") `
            $TimeoutSeconds -OutputStream $output
    } finally { $output.Dispose() }
    $archive = [IO.File]::Open($archivePath, [IO.FileMode]::Open,
        [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($archive.Length -le 0) { throw 'empty' }
        Assert-PostgresArchive $ContainerId $archive $TimeoutSeconds
        $archive.Position = 0
        $hash = Get-BackupSha256 $archive
        $manifest = [ordered]@{
            version = 1; format = 'postgresql-custom'; archive = 'database.dump'
            sourceContainerId = $ContainerId; sourceProject = $ProjectName
            sourceDatabase = $Database; sourceUser = $User; postgresVersion = $version
            sha256 = $hash; byteLength = $archive.Length
        }
        $manifestBytes = [Text.UTF8Encoding]::new($false).GetBytes(($manifest | ConvertTo-Json))
        $manifestFile = [IO.File]::Open([IO.Path]::Combine($destinationPath, 'manifest.json'),
            [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $manifestFile.Write($manifestBytes) } finally { $manifestFile.Dispose() }
    } finally { $archive.Dispose() }
    [Console]::Out.WriteLine('BACKUP_OK')
    exit 0
} catch {
    [Console]::Error.WriteLine('BACKUP_FAILED: validation or native command failed; retain partial evidence.')
    exit 1
}
