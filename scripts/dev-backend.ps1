# Start KickOff26 backend from repo root (correct cwd + port check)
$ErrorActionPreference = "Stop"
$Port = 8000
$HostAddr = "127.0.0.1"
$BackendDir = Join-Path $PSScriptRoot "..\backend" | Resolve-Path

Set-Location $BackendDir

function Test-PortInUse([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Test-BackendHealthy {
    try {
        $r = Invoke-RestMethod -Uri "http://${HostAddr}:${Port}/health" -TimeoutSec 2
        return $r.status -eq "ok"
    } catch {
        return $false
    }
}

if (Test-PortInUse $Port) {
    if (Test-BackendHealthy) {
        Write-Host "Backend already running at http://${HostAddr}:${Port}" -ForegroundColor Green
        Write-Host "Stop the existing server (Ctrl+C in its terminal) before starting a new one."
        exit 0
    }
    Write-Host "Port $Port is in use but KickOff26 is not responding on /health." -ForegroundColor Yellow
    $pids = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  PID $($proc.Id): $($proc.ProcessName)"
        }
    }
    Write-Host "Free port $Port or run: Stop-Process -Id <PID> -Force"
    exit 1
}

Write-Host "Starting backend from $BackendDir on http://${HostAddr}:${Port}" -ForegroundColor Cyan
Write-Host "First time? Run: cd backend; python scripts/init_db_data.py" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C in this terminal to stop the server." -ForegroundColor DarkGray
python -m uvicorn app.main:app --reload --host $HostAddr --port $Port
