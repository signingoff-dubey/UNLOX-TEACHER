# One-time setup (needs internet). Run from the project folder:
#   .\setup.ps1          core: Python env, Piper voices, fonts, web app, video renderer
#   .\setup.ps1 -Gpu     also PyTorch (CUDA 12.8), IndicTrans2, Indic Parler-TTS (~6 GB)
param([switch]$Gpu)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Step "Python 3.12 environment"
$py = Join-Path $root "backend\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    py -V:3.12 --version *> $null
    if ($LASTEXITCODE -ne 0) { py install 3.12 }
    py -V:3.12 -m venv (Join-Path $root "backend\venv")
}
& $py -m pip install --disable-pip-version-check -q -r (Join-Path $root "backend\requirements.txt")
if ($Gpu) {
    Step "PyTorch (CUDA 12.8) + IndicTrans2 + Indic Parler-TTS"
    & $py -m pip install --disable-pip-version-check -q torch --index-url https://download.pytorch.org/whl/cu128
    & $py -m pip install --disable-pip-version-check -q -r (Join-Path $root "backend\requirements-ml.txt")
}

Step "Config"
$envFile = Join-Path $root "backend\.env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root "backend\.env.example") $envFile
    if (-not $Gpu) {
        # Without the GPU extras, use the LLM for translation and skip Parler.
        (Get-Content $envFile) -replace '^TRANSLATE_BACKEND=.*', 'TRANSLATE_BACKEND=ollama' `
                               -replace '^TTS_FALLBACK=.*', 'TTS_FALLBACK=silent' | Set-Content $envFile -Encoding utf8
    }
    Write-Host "Created backend\.env (edit it to point at existing models)."
}

Step "Voices, fonts$(if ($Gpu) { ' and models' })"
Push-Location (Join-Path $root "backend")
if ($Gpu) { & $py scripts\download_models.py --ml } else { & $py scripts\download_models.py }
Pop-Location

Step "Web app and video renderer"
Push-Location (Join-Path $root "web")
npm install --no-audit --no-fund
npm run build
npm run bundle
Pop-Location

Step "Local LLM"
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    $model = ((Get-Content $envFile | Select-String '^OLLAMA_MODEL=') -replace 'OLLAMA_MODEL=', '').Trim()
    ollama pull $model
} else {
    Write-Host "Ollama not found. Install it from https://ollama.com, then run: ollama pull qwen2.5:7b-instruct-q4_K_M" -ForegroundColor Yellow
}

Write-Host "`nSetup complete. Start the app with .\start.ps1" -ForegroundColor Green
