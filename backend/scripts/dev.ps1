# Run backend locally (SQLite, no Docker)
$ErrorActionPreference = "Stop"
$Port = 8000
$HostAddr = "127.0.0.1"

Set-Location $PSScriptRoot\..

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
        exit 0
    }
    Write-Host "ERROR: Port $Port is already in use." -ForegroundColor Red
    Write-Host "Stop the other process or run from repo root: .\scripts\dev-backend.ps1"
    exit 1
}

pip install -r requirements.txt -q
python -m uvicorn app.main:app --reload --host $HostAddr --port $Port
