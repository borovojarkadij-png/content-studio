# Test-only crash boundary. A successful kill RPC is not proof of container exit.
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
    $container = & docker @ComposeArgs ps -a -q postgres
    if ($LASTEXITCODE -ne 0 -or $container -isnot [string] -or
        $container -cnotmatch '^[a-f0-9]{64}$') {
        throw 'Exact original PostgreSQL container required.'
    }
    $raw = & docker inspect $container
    if ($LASTEXITCODE -ne 0) { throw 'Refusing foreign PostgreSQL crash target.' }
    try { $records = @((($raw -join "`n") | ConvertFrom-Json -ErrorAction Stop)) }
    catch { throw 'Refusing foreign PostgreSQL crash target.' }
    if ($records.Count -ne 1 -or
        $records[0].Config.Labels.'com.docker.compose.project' -cne $project -or
        $records[0].Config.Labels.'com.docker.compose.service' -cne 'postgres' -or
        $records[0].State.Status -cne 'running' -or $records[0].State.Running -cne $true) {
        throw 'Refusing foreign PostgreSQL crash target.'
    }
    & docker @ComposeArgs kill -s SIGKILL postgres
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic PostgreSQL kill failed.' }
    $deadline = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        # Inspect the original immutable ID, not a replacement or cached ps result.
        $raw = & docker inspect -f '{{json .State}}' $container
        if ($LASTEXITCODE -ne 0) { throw 'Synthetic PostgreSQL exit observation failed.' }
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
