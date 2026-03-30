<#
run.ps1 - Setup virtualenv, install deps, and run the API server (Windows PowerShell)

Usage:
  .\run.ps1        # create .venv if missing, install deps, run app
  .\run.ps1 -Reinstall  # recreate .venv and reinstall
#>
param(
    [switch]$Reinstall
)

$venv = ".venv"
if ($Reinstall -and (Test-Path $venv)) {
    Remove-Item -Recurse -Force $venv
}

if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venv
}

Write-Host "Activating virtual environment and installing requirements..."
& "$venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Starting server (uvicorn on :8000)..."
python -m uvicorn app:app --reload
