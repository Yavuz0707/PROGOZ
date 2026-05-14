@echo off
setlocal
cd /d "%~dp0"
if not exist "app\main.py" (
  echo Bu dosya backend klasorunden calistirilmalidir.
  exit /b 1
)
if not exist "venv" (
  python -m venv venv
)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist "app\static\uploads" mkdir app\static\uploads
if not exist "app\static\processed" mkdir app\static\processed
if not exist "app\static\snapshots" mkdir app\static\snapshots
if not exist "app\static\clips" mkdir app\static\clips
if not exist "logs" mkdir logs
echo.
echo Kurulum tamamlandi.
echo CUDA kontrol: python scripts\check_cuda.py
echo Backend baslatma: uvicorn app.main:app --reload
echo API docs: http://127.0.0.1:8000/docs
