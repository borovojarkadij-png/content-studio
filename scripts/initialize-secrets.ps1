$secretDir = Join-Path $PSScriptRoot "..\secrets"
$keyPath = Join-Path $secretDir "newsflow_master_key"
if (Test-Path $keyPath) {
  Write-Output "Existing master key retained: $keyPath"
  exit 0
}
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes) | Set-Content -NoNewline -Encoding ascii $keyPath
Write-Output "Master key created once at $keyPath. Back it up securely; do not replace it."
