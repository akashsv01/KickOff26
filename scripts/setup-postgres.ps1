# Create KickOff26 PostgreSQL database (run once)
$ErrorActionPreference = "Stop"
$DbName = "kickoff26"
$PgUser = "postgres"
$PgPassword = "admin123"
$PgHost = "localhost"

$env:PGPASSWORD = $PgPassword

Write-Host "Checking PostgreSQL connection..." -ForegroundColor Cyan
psql -U $PgUser -h $PgHost -c "SELECT version();" | Out-Null

$exists = psql -U $PgUser -h $PgHost -tc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
if ($exists.Trim()) {
    Write-Host "Database '$DbName' already exists." -ForegroundColor Green
} else {
    psql -U $PgUser -h $PgHost -c "CREATE DATABASE $DbName;"
    Write-Host "Created database '$DbName'." -ForegroundColor Green
}

Write-Host ""
Write-Host "Connection string:" -ForegroundColor Cyan
Write-Host "postgresql+asyncpg://${PgUser}:${PgPassword}@${PgHost}:5432/${DbName}"
