param([Parameter(Mandatory)][string]$BackupPath)
$ErrorActionPreference = "Stop"
$resolved = [System.IO.Path]::GetFullPath($BackupPath)
$manifest = Join-Path $resolved "manifest.json"
$dump = Join-Path $resolved "quant.dump"
if (!(Test-Path -LiteralPath $manifest) -or !(Test-Path -LiteralPath $dump)) {
    throw "Backup must contain manifest.json and quant.dump: $resolved"
}
Write-Host "Restore source: $resolved"
$confirmation = Read-Host "This replaces the Quant Home database. Type RESTORE"
if ($confirmation -cne "RESTORE") { throw "Restore cancelled" }

$preRestore = Join-Path ([System.IO.Path]::GetDirectoryName($resolved)) "pre-restore"
& (Join-Path $PSScriptRoot "backup.ps1") -Destination $preRestore
docker compose stop api
docker compose cp $dump db:/tmp/quant-home-restore.dump
docker compose exec -T db dropdb -U quant --if-exists quant
docker compose exec -T db createdb -U quant quant
docker compose exec -T db pg_restore -U quant -d quant --clean --if-exists /tmp/quant-home-restore.dump
docker compose exec -T db rm -f /tmp/quant-home-restore.dump
docker compose up -d api web
Write-Host "Restore completed. A pre-restore backup is in: $preRestore"
