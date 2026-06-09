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
if not exist "app\static\plates" mkdir app\static\plates
if not exist "app\static\plate_crops" mkdir app\static\plate_crops
if not exist "models" mkdir models
if not exist "exports" mkdir exports
if not exist "logs" mkdir logs
echo.
echo Kurulum tamamlandi.
echo CUDA kontrol: python scripts\check_cuda.py
echo VS Code interpreter: %CD%\venv\Scripts\python.exe
echo Plaka modeli varsayilan konum: %CD%\models\license_plate_detector.pt
echo Backend baslatma: uvicorn app.main:app --reload
echo API docs: http://127.0.0.1:8000/docs
