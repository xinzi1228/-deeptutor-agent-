@echo off
REM ============================================================
REM  Label Studio one-click launcher for the Annotation Star Map
REM  - First run: auto-initializes DB + admin account
REM  - Later runs: starts existing project data
REM  Default admin: admin@localhost / admin123  (change after login!)
REM ============================================================
setlocal
set "LS_DATA=%CD%\data\label-studio"

where label-studio >nul 2>nul
if errorlevel 1 (
    echo [Label Studio] Not installed. Install with:  pip install label-studio
    echo [Label Studio] Optional - core teaching works without it.
    exit /b 1
)

if exist "%LS_DATA%\label_studio.sqlite3" (
    echo [Label Studio] Existing project data found - starting on http://localhost:8080
    label-studio start --data-dir "%LS_DATA%" --port 8080
) else (
    echo [Label Studio] First run - initializing DB and admin account ^(admin@localhost / admin123^)...
    label-studio start --init --data-dir "%LS_DATA%" --port 8080 --username admin@localhost --password admin123
)
endlocal
