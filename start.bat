@echo off
echo ============================================================
echo    Starting Advanced RAG Question Generator (v2.0)
echo ============================================================
echo.

REM Start backend in WSL
echo [1/3] Starting Backend API (port 8601)...
start /B wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp/backend && ../venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8601"

REM Wait a bit
timeout /t 5 /nobreak > nul

REM Start frontend in WSL  
echo [2/3] Starting Frontend UI (port 8602)...
start /B wsl bash -c "cd /mnt/c/Users/openclaw/harry/projects/IIT/questions/questionsapp/frontend && ../venv/bin/streamlit run streamlit_app.py --server.port 8602"

REM Wait a bit
timeout /t 3 /nobreak > nul

echo [3/3] Opening browser...
timeout /t 2 /nobreak > nul
start http://localhost:8602

echo.
echo ============================================================
echo    System Running!
echo ============================================================
echo.
echo    Frontend UI: http://localhost:8602
echo    Backend API: http://localhost:8601
echo.
echo    Press Ctrl+C to stop
echo ============================================================
echo.

REM Keep window open
pause
