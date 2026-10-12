param(
    [string]$Source,
    [string]$ContainerId,
    [string]$ProjectName,
    [string]$User,
    [string]$TargetDatabase,
    [int]$TimeoutSeconds = 120
)

if ($MyInvocation.InvocationName -eq '.') { return }
$ErrorActionPreference = 'Stop'
try {
    . "$PSScriptRoot/postgres-backup-common.ps1"
    Assert-BackupInputs $ContainerId $ProjectName $User $TimeoutSeconds
    Assert-PostgresName $TargetDatabase
    $sourcePath = Get-BackupPath $Source
    $manifest = Read-BackupManifest $sourcePath
    if ($TargetDatabase -ceq $manifest.sourceDatabase -or $User -cne $manifest.sourceUser) {
        throw 'source binding'
    }
    $archivePath = Get-BackupPath ([IO.Path]::Combine($sourcePath, 'database.dump'))
    # Keep one read-only handle from hash verification through restore. On Windows,
    # writers/deleters cannot replace these validated bytes while it is held.
    $archive = [IO.File]::Open($archivePath, [IO.FileMode]::Open,
        [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($archive.Length -ne $manifest.byteLength) { throw 'length' }
        $hash = Get-BackupSha256 $archive
        if ($hash -cne $manifest.sha256) { throw 'digest' }
        Assert-PostgresContainer $ContainerId $ProjectName $manifest.sourceDatabase $User $TimeoutSeconds
        $version = Get-PostgresVersion $ContainerId $manifest.sourceDatabase $User $TimeoutSeconds
        if ($version.Split('.')[0] -cne $manifest.postgresVersion.Split('.')[0]) { throw 'major version' }
        Assert-PostgresArchive $ContainerId $archive $TimeoutSeconds
        # Target is restricted to ASCII SQL identifiers, and is still a literal here.
        $sql = "SELECT count(*) FROM pg_database WHERE datname = '$TargetDatabase';"
        $exists = Get-BackupNativeText @('exec', $ContainerId, 'psql', '--no-psqlrc',
            '--tuples-only', '--no-align', '--set=ON_ERROR_STOP=1', "--username=$User",
            '--dbname=postgres', '--command', $sql) $TimeoutSeconds
        if ($exists.Trim() -cne '0') { throw 'target exists or invalid result' }
        Invoke-BackupNative @('exec', $ContainerId, 'createdb', "--username=$User",
            '--maintenance-db=postgres', '--template=template0', '--', $TargetDatabase) $TimeoutSeconds
        $archive.Position = 0
        Invoke-BackupNative @('exec', '-i', $ContainerId, 'pg_restore', '--exit-on-error',
            '--no-owner', '--no-privileges', "--username=$User", "--dbname=$TargetDatabase") `
            $TimeoutSeconds -InputStream $archive
    } finally { $archive.Dispose() }
    [Console]::Out.WriteLine('RESTORE_OK: new database copy created.')
    exit 0
} catch {
    [Console]::Error.WriteLine('RESTORE_FAILED: validation or native command failed; retain any partial copy.')
    exit 1
}
