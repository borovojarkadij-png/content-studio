param([string]$Destination = "backups/newsflow.sql")
New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
docker compose exec -T postgres pg_dump -U $env:POSTGRES_USER $env:POSTGRES_DB > $Destination
