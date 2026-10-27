# Starts the whole app (offline). Run from the project folder:
#   .\start.ps1          open on this laptop at http://127.0.0.1:8000
#   .\start.ps1 -Lan     also reachable from other devices on the network
param([switch]$Lan, [int]$Port = 8000)
$root = $PSScriptRoot

if (-not (Test-Path (Join-Path $root "web\dist\index.html"))) {
    Write-Host "Building the web app..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "web"); npm run build; Pop-Location
}

# Make sure Ollama is running (the lesson planner needs it).
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null }
catch {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Write-Host "Starting Ollama..." -ForegroundColor Cyan
        Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
    } else {
        Write-Host "Ollama is not installed; lessons will fail unless LLM_BACKEND=mock in backend\.env" -ForegroundColor Yellow
    }
}

Start-Job -ScriptBlock { param($p) Start-Sleep 4; Start-Process "http://127.0.0.1:$p" } -ArgumentList $Port | Out-Null
& (Join-Path $root "backend\run.ps1") -Port $Port -Lan:$Lan
