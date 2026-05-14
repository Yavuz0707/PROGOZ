@echo off
setlocal
cd /d "%~dp0\..\backend"
call setup_windows.bat
cd /d "%~dp0\..\frontend"
npm install
echo.
echo Tum kurulum tamamlandi.
echo Backend: cd backend ^&^& venv\Scripts\activate ^&^& uvicorn app.main:app --reload
echo Frontend: cd frontend ^&^& npm run dev
