@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-rpla-week8.ps1" -Demo %*
set "demoExitCode=%errorlevel%"
if not "%demoExitCode%"=="0" (
    echo.
    echo Camera demo could not start. Read the message above.
    echo If an earlier demo is running, open http://127.0.0.1:5177/ or run STOP_CAMERA_DEMO.cmd first.
    pause
)
exit /b %demoExitCode%
