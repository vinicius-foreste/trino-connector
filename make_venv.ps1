<#
make_venv.ps1

Usage (PowerShell):
  .\make_venv.ps1            # create venv (if missing) and install requirements
  .\make_venv.ps1 -Lint     # also run linters (ruff + flake8)
  .\make_venv.ps1 -Tests    # also run pytest
  .\make_venv.ps1 -Activate # activate the venv in this session

Notes:
- Run this from the project root (where requirements.txt is).
- If you want the script to *activate* the venv for your current interactive session,
  run it with the `-Activate` flag (PowerShell restriction: script must be dot-sourced
  to persist activation in current session: `. .\make_venv.ps1 -Activate`).
#>
param(
    [switch]$Install = $true,
    [switch]$Lint = $false,
    [switch]$Tests = $false,
    [switch]$Activate = $false
)

$venvPath = Join-Path -Path (Get-Location) -ChildPath ".venv"
$pythonExe = "python"

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

try {
    if (-not (Test-Path $venvPath)) {
        Write-Info "Creating virtual environment at $venvPath..."
        & $pythonExe -m venv $venvPath
    } else {
        Write-Info "Virtual environment already exists at $venvPath"
    }

    $activateScript = Join-Path $venvPath "Scripts/Activate.ps1"
    $pipExe = Join-Path $venvPath "Scripts/pip.exe"
    $pytestExe = Join-Path $venvPath "Scripts/pytest.exe"

    if ($Install) {
        Write-Info "Upgrading pip and installing requirements..."
        & $pipExe install --upgrade pip
        if (Test-Path "requirements.txt") {
            & $pipExe install -r requirements.txt
        } else {
            Write-Info "No requirements.txt found; skipping pip install."
        }
    }

    if ($Activate) {
        # To persist activation in the calling shell, user must dot-source this script:
        # `. .\make_venv.ps1 -Activate`
        if (Test-Path $activateScript) {
            Write-Info "Activating virtual environment in current session..."
            . $activateScript
            Write-Info "Activated. Use 'deactivate' to exit the venv."
        } else {
            Write-Err "Activation script not found at $activateScript"
        }
    }

    if ($Lint) {
        Write-Info "Running linters: ruff and flake8"
        $ruffExe = Join-Path $venvPath "Scripts/ruff.exe"
        $flakeExe = Join-Path $venvPath "Scripts/flake8.exe"
        if (Test-Path $ruffExe) { & $ruffExe check . } else { Write-Info "ruff not installed in venv; skipping" }
        if (Test-Path $flakeExe) { & $flakeExe . } else { Write-Info "flake8 not installed in venv; skipping" }
    }

    if ($Tests) {
        Write-Info "Running pytest"
        if (Test-Path $pytestExe) { & $pytestExe -q } else { Write-Info "pytest not installed in venv; skipping" }
    }

    Write-Info "Done."
} catch {
    Write-Err "Unexpected error: $_"
    exit 1
}
