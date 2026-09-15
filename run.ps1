# AgriSmart AI - Windows launcher (PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File run.ps1
#   powershell -ExecutionPolicy Bypass -File run.ps1 -Port 8010
#   powershell -ExecutionPolicy Bypass -File run.ps1 -Doctor
#   powershell -ExecutionPolicy Bypass -File run.ps1 -Test
#
# Does exactly what run.sh does on Linux/macOS: finds Python, creates .venv when
# needed, installs the CPU wheels, runs the environment check and starts the server.
# Prefer the double-clickable run.bat if you would rather not touch PowerShell.
[CmdletBinding()]
param(
  [int]$Port = 8000,
  [switch]$Doctor,
  [switch]$Test,
  [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Find-Python {
  foreach ($cand in @("python", "py")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { continue }
    & $cand -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return $cand }
  }
  return $null
}

$py = Find-Python
if ($null -eq $py) {
  Write-Host "!!  No Python 3.10+ found." -ForegroundColor Red
  Write-Host "    Install it from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
  exit 1
}

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
function Test-Deps($interpreter) {
  & $interpreter -c "import importlib.util as u; need=['fastapi','uvicorn','multipart','torch','torchvision','PIL','numpy','sklearn','joblib','requests']; raise SystemExit(0 if all(u.find_spec(m) for m in need) else 1)" 2>$null
  return ($LASTEXITCODE -eq 0)
}

$target = $null
if ((Test-Path $venvPy) -and (Test-Deps $venvPy)) { $target = $venvPy }
elseif (Test-Deps $py) { $target = $py }

if ($Doctor) {
  & $py scripts/doctor.py --port $Port
  exit $LASTEXITCODE
}

if ($Test) {
  if ($null -eq $target) { $target = $py }
  & $target -m pytest tests/ -q
  exit $LASTEXITCODE
}

if ($null -eq $target) {
  if ($NoInstall) {
    Write-Host "!!  dependencies missing and -NoInstall was given." -ForegroundColor Red
    & $py scripts/doctor.py --port $Port
    exit 1
  }
  if (-not (Test-Path $venvPy)) {
    Write-Host "==> creating a virtualenv in .venv (keeps your system Python clean)"
    & $py -m venv .venv
  }
  $target = $venvPy
  Write-Host "==> installing Python dependencies (first run only, a few minutes)"
  & $target -m pip install --upgrade pip
  Write-Host "    torch + torchvision (CPU wheels, ~200 MB)"
  & $target -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  Write-Host "    the rest of requirements.txt"
  & $target -m pip install -r requirements.txt
}

& $target scripts/doctor.py --port $Port

if (-not (Test-Path "model\best_model.pth")) {
  Write-Host "!!  model\best_model.pth missing - the UI will start in demo mode (no detection)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> AgriSmart AI starting on http://localhost:$Port   (API docs: http://localhost:$Port/docs)"
Write-Host "    stop with Ctrl+C"
Write-Host ""
& $target -m uvicorn app.backend.main:app --host 0.0.0.0 --port $Port
