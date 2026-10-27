# Make a narrated 3D lesson on any topic, offline. Examples:
#   .\make3d.ps1 -Concept "explain the water cycle" -Lang te
#   .\make3d.ps1 -Concept "how does a lever work" -Quality good
#   .\make3d.ps1 -Template atom -Element oxygen -Lang hi
#   .\make3d.ps1 -Plan out\<run>\plan.json -Lang ta          # same scene, another language
#   .\make3d.ps1 -Doctor                                      # check this PC has everything
param([string]$Concept, [string]$Template, [string]$Element = "carbon", [string]$Plan, [string]$Lang = "en",
      [ValidateSet("draft", "good")][string]$Quality = "draft", [switch]$Doctor, [switch]$NoOpen)
$backend = if ($env:VT_BACKEND) { $env:VT_BACKEND } else { Join-Path $env:USERPROFILE "visual-teacher\backend" }
$py = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Visual Teacher backend venv not found at $backend (set VT_BACKEND)" -ForegroundColor Red; exit 1 }
$env:PYTHONIOENCODING = "utf-8"
if ($Doctor) { & $py (Join-Path $PSScriptRoot "doctor.py"); exit $LASTEXITCODE }
$argv = @((Join-Path $PSScriptRoot "make3d.py"), "--lang", $Lang, "--quality", $Quality)
if ($Concept) { $argv += @("--concept", $Concept) }
if ($Template) { $argv += @("--template", $Template, "--element", $Element) }
if ($Plan) { $argv += @("--plan", $Plan) }
if (-not $NoOpen) { $argv += "--open" }
& $py @argv
