# Shared implementation only. No command executes when this file is loaded.
Set-StrictMode -Version Latest

function Assert-PostgresName([string]$Name) {
    if ($Name -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,62}$') { throw 'name' }
}

function Assert-BackupInputs([string]$ContainerId, [string]$ProjectName, [string]$User,
    [int]$TimeoutSeconds) {
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 required' }
    if ($ContainerId -cnotmatch '^[a-f0-9]{64}$') { throw 'id' }
    if ($ProjectName -cnotmatch '^[a-z0-9][a-z0-9_-]{0,62}$') { throw 'project' }
    Assert-PostgresName $User
    if ($TimeoutSeconds -lt 1 -or $TimeoutSeconds -gt 1800) { throw 'timeout' }
}

function Get-BackupPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'path' }
    $absolute = [IO.Path]::GetFullPath($Path)
    # Refuse UNC/device paths and alternate data streams on Windows.
    if ($IsWindows -and ($absolute.StartsWith('\\') -or $absolute.Substring(2).Contains(':'))) {
        throw 'path type'
    }
    $current = $absolute
    while ($current) {
        try {
            $attributes = [IO.File]::GetAttributes($current)
            if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'reparse' }
        } catch [IO.FileNotFoundException] { } catch [IO.DirectoryNotFoundException] { }
        $current = [IO.Path]::GetDirectoryName($current)
    }
    return $absolute
}

function Invoke-BackupNative([string[]]$Arguments, [int]$TimeoutSeconds,
    [IO.Stream]$InputStream, [IO.Stream]$OutputStream = [IO.Stream]::Null,
    [switch]$AllowEarlyInputClose) {
    $processInfo = [Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = (Get-Command docker -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $processInfo.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    $deadline = [Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds($TimeoutSeconds))
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $started = $false
    try {
        if (-not $process.Start()) { throw 'start' }
        $started = $true
        # Drain concurrently; native diagnostics never become public errors.
        $outTask = $process.StandardOutput.BaseStream.CopyToAsync($OutputStream, 81920, $deadline.Token)
        $errTask = $process.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null, 81920, $deadline.Token)
        $inputFailure = $null
        if ($null -ne $InputStream) {
            $inTask = $InputStream.CopyToAsync($process.StandardInput.BaseStream, 81920, $deadline.Token)
            try { [void]$inTask.GetAwaiter().GetResult() }
            catch { $inputFailure = $_.Exception.GetBaseException() }
        }
        try { $process.StandardInput.Close() }
        catch {
            if ($null -eq $inputFailure) { $inputFailure = $_.Exception.GetBaseException() }
        }
        $remaining = [Math]::Max(0, $TimeoutSeconds * 1000 - [int]$clock.ElapsedMilliseconds)
        if (-not $process.WaitForExit($remaining)) { throw 'timeout' }
        $nativeExit = $process.ExitCode
        $tasks = [Threading.Tasks.Task[]]@($outTask, $errTask)
        [void][Threading.Tasks.Task]::WhenAll($tasks).GetAwaiter().GetResult()
        if ($nativeExit -ne 0) { throw 'native exit' }
        if ($null -ne $inputFailure) {
            # pg_restore --list reads only header/TOC. Accept only Windows closed-pipe
            # errors after its native success, never cancellation or a source read error.
            $closedPipe = $inputFailure -is [IO.IOException] -and
                $inputFailure.HResult -in @(-2147024787, -2147024664, -2147024663) # 109/232/233
            if (-not $AllowEarlyInputClose -or -not $closedPipe -or $deadline.IsCancellationRequested) {
                throw 'input failed'
            }
        }
    } catch {
        if ($started -and -not $process.HasExited) {
            $process.Kill() # This handle only, never a process tree or container.
            $null = $process.WaitForExit(1000)
        }
        throw 'native command failed'
    } finally {
        $deadline.Cancel()
        $deadline.Dispose()
        $process.Dispose()
    }
}

function Get-BackupSha256([IO.Stream]$Archive) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($Archive)).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-BackupNativeText([string[]]$Arguments, [int]$TimeoutSeconds) {
    $buffer = [IO.MemoryStream]::new([byte[]]::new(1048576), 0, 1048576, $true, $true)
    $buffer.SetLength(0)
    try {
        Invoke-BackupNative $Arguments $TimeoutSeconds -OutputStream $buffer
        if ($buffer.Length -gt 1048576) { throw 'output size' }
        return [Text.UTF8Encoding]::new($false, $true).GetString($buffer.ToArray())
    } finally { $buffer.Dispose() }
}

function Assert-PostgresContainer([string]$ContainerId, [string]$ProjectName,
    [string]$Database, [string]$User, [int]$TimeoutSeconds) {
    $text = Get-BackupNativeText @('inspect', $ContainerId) $TimeoutSeconds
    $items = $text | ConvertFrom-Json -NoEnumerate
    if ($items -isnot [array] -or $items.Count -ne 1) { throw 'inspect' }
    $item = $items[0]
    if ($item.Id -cne $ContainerId -or $item.State.Running -isnot [bool] -or -not $item.State.Running `
        -or $item.Config.Labels.'com.docker.compose.project' -cne $ProjectName `
        -or $item.Config.Labels.'com.docker.compose.service' -cne 'postgres') { throw 'identity' }
    $dbValues = @($item.Config.Env | Where-Object { $_ -clike 'POSTGRES_DB=*' })
    $userValues = @($item.Config.Env | Where-Object { $_ -clike 'POSTGRES_USER=*' })
    if ($dbValues.Count -ne 1 -or $userValues.Count -ne 1 `
        -or $dbValues[0] -cne "POSTGRES_DB=$Database" `
        -or $userValues[0] -cne "POSTGRES_USER=$User") { throw 'configuration' }
}

function Get-PostgresVersion([string]$ContainerId, [string]$Database, [string]$User,
    [int]$TimeoutSeconds) {
    $version = (Get-BackupNativeText @('exec', $ContainerId, 'psql', '--no-psqlrc',
        '--tuples-only', '--no-align', '--set=ON_ERROR_STOP=1', "--username=$User",
        "--dbname=$Database", '--command', 'SHOW server_version;') $TimeoutSeconds).Trim()
    if ($version -cnotmatch '^[1-9][0-9]{0,2}\.[0-9]{1,3}(\.[0-9]{1,3})?([ ][A-Za-z0-9().+~ _-]{1,160})?$') {
        throw 'version'
    }
    return $version
}

function Assert-PostgresArchive([string]$ContainerId, [IO.Stream]$Archive, [int]$TimeoutSeconds) {
    $Archive.Position = 0
    $signature = [byte[]]::new(5)
    if ($Archive.Read($signature, 0, 5) -ne 5 -or [Text.Encoding]::ASCII.GetString($signature) -cne 'PGDMP') {
        throw 'custom archive required'
    }
    $Archive.Position = 0
    Invoke-BackupNative @('exec', '-i', $ContainerId, 'pg_restore', '--list') `
        $TimeoutSeconds -InputStream $Archive -AllowEarlyInputClose
}

function Read-BackupManifest([string]$SourcePath) {
    if (-not [IO.Directory]::Exists($SourcePath)) { throw 'bundle' }
    $files = @(Get-ChildItem -LiteralPath $SourcePath -Force)
    if ($files.Count -ne 2 -or (($files.Name | Sort-Object) -join ',') -cne 'database.dump,manifest.json') {
        throw 'bundle structure'
    }
    foreach ($file in $files) {
        $null = Get-BackupPath $file.FullName
        if ($file.PSIsContainer) { throw 'bundle file' }
    }
    $manifestPath = [IO.Path]::Combine($SourcePath, 'manifest.json')
    if ([IO.FileInfo]::new($manifestPath).Length -gt 65536) { throw 'manifest size' }
    $json = [Text.UTF8Encoding]::new($false, $true).GetString([IO.File]::ReadAllBytes($manifestPath))
    $document = [Text.Json.JsonDocument]::Parse($json)
    try {
        $root = $document.RootElement
        if ($root.ValueKind -ne [Text.Json.JsonValueKind]::Object) { throw 'manifest object' }
        $expected = @('version', 'format', 'archive', 'sourceContainerId', 'sourceProject',
            'sourceDatabase', 'sourceUser', 'postgresVersion', 'sha256', 'byteLength')
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($property in $root.EnumerateObject()) {
            if (-not $seen.Add($property.Name) -or $property.Name -cnotin $expected) { throw 'manifest keys' }
            $kind = if ($property.Name -cin @('version', 'byteLength')) { 'Number' } else { 'String' }
            if ($property.Value.ValueKind.ToString() -cne $kind) { throw 'manifest type' }
        }
        if ($seen.Count -ne $expected.Count) { throw 'missing fields' }
        $manifest = $json | ConvertFrom-Json
        if ($root.GetProperty('version').GetInt32() -ne 1 `
            -or $root.GetProperty('byteLength').GetInt64() -le 0 `
            -or $manifest.format -cne 'postgresql-custom' -or $manifest.archive -cne 'database.dump' `
            -or $manifest.sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'manifest values' }
        Assert-BackupInputs $manifest.sourceContainerId $manifest.sourceProject $manifest.sourceUser 120
        Assert-PostgresName $manifest.sourceDatabase
        if ($manifest.postgresVersion -cnotmatch '^[1-9][0-9]{0,2}\.[0-9]{1,3}(\.[0-9]{1,3})?([ ][A-Za-z0-9().+~ _-]{1,160})?$') {
            throw 'manifest version'
        }
        return $manifest
    } finally { $document.Dispose() }
}
