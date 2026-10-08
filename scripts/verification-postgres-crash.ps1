# Test-only crash boundary. A successful kill RPC is not proof of container exit.
function Invoke-VerificationProcess {
    param([string]$FilePath, [string[]]$Arguments,
        [ValidateRange(1, 60000)][int]$TimeoutMilliseconds)
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = [Diagnostics.ProcessStartInfo]::new($FilePath)
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $process.StartInfo.ArgumentList.Add($argument) }
    $started = $false
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        try { $started = $process.Start() }
        catch { throw 'Synthetic verification command failed.' }
        if (-not $started) { throw 'Synthetic verification command failed.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            throw 'Synthetic verification process timed out.'
        }
        $remaining = [int][Math]::Floor($TimeoutMilliseconds - $clock.Elapsed.TotalMilliseconds)
        if ($remaining -lt 1 -or -not [Threading.Tasks.Task]::WaitAll(
            [Threading.Tasks.Task[]]@($stdout, $stderr), $remaining)) {
            throw 'Synthetic verification process timed out.'
        }
        if ($clock.Elapsed.TotalMilliseconds -ge $TimeoutMilliseconds) {
            throw 'Synthetic verification process timed out.'
        }
        if ($process.ExitCode -ne 0) { throw 'Synthetic verification command failed.' }
        return $stdout.GetAwaiter().GetResult()
    } finally {
        # Best-effort cleanup of this owned CLI while its root is alive, never
        # daemon/container processes. This is not a general orphan-tree manager.
        # Crash calls below use native ps/inspect/kill, not Compose child plugins.
        if ($started -and -not $process.HasExited) {
            try { $process.Kill($true) } catch { }
        }
        $process.Dispose()
    }
}

function Invoke-VerificationDocker {
    param([string[]]$Arguments, [int]$TimeoutMilliseconds)
    # Windows installations also expose an extensionless Unix docker launcher.
    # Preserve normal executable precedence instead of stringifying both paths.
    $executable = (Get-Command docker -CommandType Application -ErrorAction Stop |
        Select-Object -First 1).Source
    Invoke-VerificationProcess -FilePath $executable -Arguments $Arguments -TimeoutMilliseconds $TimeoutMilliseconds
}

function Invoke-SyntheticPostgresCrash {
    param([string[]]$ComposeArgs, [ValidateRange(1, 60)][int]$TimeoutSeconds = 30)
    $projectIndex = [Array]::IndexOf($ComposeArgs, '-p')
    if ($ComposeArgs.Count -lt 3 -or $ComposeArgs[0] -cne 'compose' -or
        $projectIndex -lt 1 -or $projectIndex + 1 -ge $ComposeArgs.Count) {
        throw 'Isolated verification project required.'
    }
    $project = $ComposeArgs[$projectIndex + 1]
    if ($project -cnotmatch '^newsflow-verification-[a-z0-9]+(?:-[a-z0-9]+)*$') {
        throw 'Isolated verification project required.'
    }
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    function Invoke-CrashDocker([string[]]$Arguments, [string]$FailureMessage) {
        $remaining = [int][Math]::Floor($TimeoutSeconds * 1000 - $deadline.Elapsed.TotalMilliseconds)
        if ($remaining -lt 1) { throw 'Synthetic PostgreSQL exit barrier timed out; preserve fixture.' }
        try { $result = Invoke-VerificationDocker -Arguments $Arguments -TimeoutMilliseconds $remaining }
        catch {
            if ($_.Exception.Message -eq 'Synthetic verification process timed out.') {
                throw 'Synthetic PostgreSQL exit barrier timed out; preserve fixture.'
            }
            throw $FailureMessage
        }
        if ($deadline.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            throw 'Synthetic PostgreSQL exit barrier timed out; preserve fixture.'
        }
        return $result
    }
    $container = Invoke-CrashDocker @('ps', '-aq', '--no-trunc', '--filter', "label=com.docker.compose.project=$project",
        '--filter', 'label=com.docker.compose.service=postgres') 'Exact original PostgreSQL container required.'
    if ($container -is [string]) { $container = $container.Trim() }
    if ($container -isnot [string] -or
        $container -cnotmatch '^[a-f0-9]{64}$') {
        throw 'Exact original PostgreSQL container required.'
    }
    $raw = Invoke-CrashDocker @('inspect', $container) 'Refusing foreign PostgreSQL crash target.'
    try { $records = @((($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop)) }
    catch { throw 'Refusing foreign PostgreSQL crash target.' }
    if ($records.Count -ne 1 -or
        $records[0].Config.Labels.'com.docker.compose.project' -cne $project -or
        $records[0].Config.Labels.'com.docker.compose.service' -cne 'postgres' -or
        $records[0].State.Status -cne 'running' -or $records[0].State.Running -cne $true) {
        throw 'Refusing foreign PostgreSQL crash target.'
    }
    $null = Invoke-CrashDocker @('kill', '-s', 'SIGKILL', $container) 'Synthetic PostgreSQL kill failed.'
    while ($true) {
        # Inspect the original immutable ID, not a replacement or cached ps result.
        $raw = Invoke-CrashDocker @('inspect', '-f', '{{json .State}}', $container) 'Synthetic PostgreSQL exit observation failed.'
        try { $state = ($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'Synthetic PostgreSQL exit observation failed.' }
        if ($state.Status -ceq 'exited' -and $state.Running -ceq $false -and
            $state.ExitCode -eq 137) { return }
        if ($state.Status -cne 'running' -or $state.Running -cne $true) {
            throw 'Unexpected synthetic PostgreSQL termination.'
        }
        if ($deadline.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
            throw 'Synthetic PostgreSQL exit barrier timed out; preserve fixture.'
        }
        Start-Sleep -Milliseconds 100
    }
}
