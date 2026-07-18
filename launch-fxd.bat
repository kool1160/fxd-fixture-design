@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Resolve paths from this file so the launcher works from a shortcut or drag-and-drop.
set "FXD_ROOT=%~dp0"
set "FXD_PYTHON=%FXD_ROOT%.venv\Scripts\python.exe"
set "FXD_APP=%FXD_ROOT%scripts\fxd-app.py"

if not exist "%FXD_PYTHON%" (
    echo ERROR: FXD virtual environment is missing.
    echo Expected Python: "%FXD_PYTHON%"
    echo Create the repository .venv, then launch FXD again.
    goto :failure
)

if not exist "%FXD_APP%" (
    echo ERROR: FXD application entry point is missing.
    echo Expected entry point: "%FXD_APP%"
    goto :failure
)

if "%~1"=="" (
    "%FXD_PYTHON%" "%FXD_APP%"
) else (
    if not exist "%~f1" (
        echo ERROR: STEP file was not found.
        echo Requested file: "%~f1"
        goto :failure
    )
    "%FXD_PYTHON%" "%FXD_APP%" --step "%~f1"
)

set "FXD_EXIT=%ERRORLEVEL%"
if not "%FXD_EXIT%"=="0" (
    echo.
    echo ERROR: FXD exited with code %FXD_EXIT%.
    goto :failure
)

exit /b 0

:failure
echo.
echo FXD did not start. Review the error above before trying again.
pause
exit /b 1
