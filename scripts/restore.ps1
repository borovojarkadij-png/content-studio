param([Parameter(Mandatory = $true)][string]$Source)
Get-Content -Raw $Source | docker compose exec -T postgres psql -U $env:POSTGRES_USER $env:POSTGRES_DB
