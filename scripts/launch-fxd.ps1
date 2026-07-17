param(
    [switch]$CheckOnly,
    [string]$StepPath
)

$ErrorActionPreference = "Stop"

try {
    $scriptPath = [System.IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
    $root = [System.IO.Path]::GetFullPath((Join-Path (Split-Path $scriptPath -Parent) ".."))
    Set-Location -LiteralPath $root

    $python = Join-Path $root ".venv\Scripts\python.exe"
    $app = Join-Path $root "scripts\fxd-app.py"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Error "FXD Python environment not found: $python"
        exit 2
    }
    if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
        Write-Error "FXD launcher target not found: $app"
        exit 2
    }

    $version = & $python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python verification failed: $version"
        exit 3
    }
    Write-Host "Python: $version"

    $ocp = & $python -c "import OCP; print(getattr(OCP, '__version__', 'unknown'))" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "OCP verification failed: $ocp"
        exit 4
    }
    Write-Host "OCP: $ocp"

    $tk = & $python -c "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy(); print('available')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tk verification failed: $tk"
        exit 5
    }
    Write-Host "Tk: $tk"

    if ($CheckOnly) {
        exit 0
    }
    if ($StepPath) {
        & $python $app "--step" $StepPath
    }
    else {
        & $python $app
    }
    exit $LASTEXITCODE
}
catch {
    Write-Error "FXD launch failed: $($_.Exception.Message)"
    exit 1
}
