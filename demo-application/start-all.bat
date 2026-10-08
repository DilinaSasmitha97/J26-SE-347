@echo off
setlocal

set "DEMO_DIR=%~dp0"
pushd "%DEMO_DIR%" >nul

echo Checking demo application dependencies...
if not exist "sqlglot-service\.venv\Scripts\python.exe" goto missing_deps
if not exist "nl-to-sql-service\.venv\Scripts\python.exe" goto missing_deps
if not exist ".ner-venv\Scripts\python.exe" goto missing_deps
if not exist "presentation-service\.venv\Scripts\python.exe" goto missing_deps
if not exist "backend\node_modules" goto missing_deps
if not exist "frontend\node_modules" goto missing_deps

echo Starting SQLGlot service on port 8001...
start "SQLGlot service - 8001" /D "%DEMO_DIR%" cmd /k ""%DEMO_DIR%sqlglot-service\.venv\Scripts\python.exe" -m uvicorn app:app --app-dir "%DEMO_DIR%sqlglot-service" --host 127.0.0.1 --port 8001"

echo Starting NL-to-SQL service on port 8000...
start "NL-to-SQL service - 8000" /D "%DEMO_DIR%" cmd /k ""%DEMO_DIR%nl-to-sql-service\.venv\Scripts\python.exe" "%DEMO_DIR%nl-to-sql-service\run_server.py""

echo Starting PII NER service on port 5002...
start "PII NER service - 5002" /D "%DEMO_DIR%" cmd /k ""%DEMO_DIR%.ner-venv\Scripts\python.exe" "%DEMO_DIR%packages\security-validation-layer\pii_service\ner_service.py""

echo Starting Node backend on port 5000...
start "Demo backend - 5000" /D "%DEMO_DIR%backend" cmd /k "npm start"

echo Starting Vonara presentation service on port 8004...
start "Presentation service - 8004" /D "%DEMO_DIR%" cmd /k ""%DEMO_DIR%presentation-service\.venv\Scripts\python.exe" "%DEMO_DIR%presentation-service\run_server.py""

echo Starting frontend on port 3000...
start "Demo frontend - 3000" /D "%DEMO_DIR%frontend" cmd /k "npm run dev -- --host 127.0.0.1"

echo.
echo All six services were launched in separate terminal windows.
echo Open http://localhost:3000/#/pipeline when they are ready.
popd
exit /b 0

:missing_deps
echo.
echo Some required virtual environments or node_modules folders are missing.
echo Install the dependencies by following demo-application\README.md, then run this file again.
echo.
popd
pause
exit /b 1
