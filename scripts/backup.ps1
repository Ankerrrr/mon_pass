param([Parameter(Mandatory)][string]$Destination)
$ErrorActionPreference = "Stop"
$resolved = [System.IO.Path]::GetFullPath($Destination)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $resolved "quant-home-$stamp"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

docker compose exec -T db pg_dump -U quant -Fc -f /tmp/quant-home.dump quant
if ($LASTEXITCODE -ne 0) { throw "Database dump failed" }
docker compose cp db:/tmp/quant-home.dump (Join-Path $backupDir "quant.dump")
docker compose exec -T db rm -f /tmp/quant-home.dump

if (Test-Path -LiteralPath ".env") { Copy-Item -LiteralPath ".env" -Destination (Join-Path $backupDir ".env") }
@{
    format = 1
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    database = "quant"
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupDir "manifest.json") -Encoding utf8
Write-Host "Backup completed: $backupDir"
