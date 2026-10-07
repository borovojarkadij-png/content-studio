$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
docker compose -f (Join-Path $projectRoot 'compose.yaml') -f (Join-Path $projectRoot 'compose.dev.yaml') --profile dev up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Development stack failed to start; inspect Docker logs.' }
