# Starts the backend. Usage (from backend\):  .\run.ps1          -> this laptop only
#                                           .\run.ps1 -Lan     -> reachable from other devices
param([switch]$Lan, [int]$Port = 8000)

$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "No venv found. Run setup first:" -ForegroundColor Yellow
    Write-Host "  py -V:3.12 -m venv venv; .\venv\Scripts\pip install -r requirements.txt"
    exit 1
}
$bindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
Set-Location $PSScriptRoot
& $py -m uvicorn app.main:app --host $bindHost --port $Port
