@echo off
REM ============================================================
REM  DeepTutor fork "Annotation Star Map" one-click launcher
REM  Usage: double-click or run start_all.bat from repo root
REM ============================================================
setlocal

REM --- Frontend must reach backend over IPv4 (localhost may resolve to ::1) ---
set "DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001"

if not exist web\node_modules (
    echo [1/3] Installing frontend dependencies ^(npm install^)...
    pushd web
    call npm install
    if errorlevel 1 (
        echo npm install failed. Check Node.js ^(>=20^) is installed.
        popd
        exit /b 1
    )
    popd
)

echo [2/3] Starting backend on http://127.0.0.1:8001 ...
start "AnnotationStarMap-Backend" cmd /k "python -m uvicorn deeptutor.api.main:app --host 127.0.0.1 --port 8001"

echo [3/3] Starting frontend on http://localhost:3782 ...
start "AnnotationStarMap-Frontend" cmd /k "set DEEPTUTOR_API_BASE_URL=http://127.0.0.1:8001&& cd web&& npx next dev --port 3782"

echo.
echo  Backend  : http://127.0.0.1:8001/docs
echo  Frontend : http://localhost:3782
echo  Hint     : First LLM setup happens in the UI settings page
echo  Hint     : If port 8001 is busy, close other DeepTutor instances first.
endlocal
