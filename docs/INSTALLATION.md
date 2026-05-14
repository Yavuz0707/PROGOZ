# Installation

## Windows

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/check_cuda.py
cd ..
python scripts/create_admin.py
```

Alternatif kolay kurulum:

```powershell
cd backend
setup_windows.bat
```

## VS Code Interpreter

FastAPI import uyarilari gorurseniz VS Code yanlis Python ortamını kullaniyor olabilir:

1. `Ctrl + Shift + P`
2. `Python: Select Interpreter`
3. `backend\venv\Scripts\python.exe` secin
4. VS Code penceresini gerekirse yeniden yukleyin

## CUDA

Backend klasoru icinde `python scripts/check_cuda.py` Python, torch, CUDA, GPU adi, GPU sayisi, Ultralytics, OpenCV ve secilen inference device bilgisini yazdirir. CUDA aktif degilse PyTorch'un resmi kurulum sayfasindan CUDA destekli wheel kurulmalidir.

PowerShell'e direkt `print(torch.cuda.is_available())` yazmak yanlistir; PowerShell bunu Python kodu olarak calistirmaz. Dogru yontem:

```powershell
python scripts/check_cuda.py
```

veya:

```powershell
python
import torch
print(torch.cuda.is_available())
```

## FFmpeg

FFmpeg indirilip `ffmpeg.exe` PATH'e eklenmelidir. H.264 tarayici uyumlulugu icin gereklidir.

## Backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

FastAPI dokumani: `http://127.0.0.1:8000/docs`

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend paneli: `http://127.0.0.1:5173`

## Analiz Modlari

Varsayilan mod `fast`tir. Video demo icin onerilir.

- `realtime`: canlı kamera icin dusuk gecikme, frame birikmesini azaltir.
- `fast`: 30-60 saniyelik demo videolari hizli analiz eder.
- `balanced`: daha dengeli kalite/hiz.
- `accurate`: en detayli ama daha yavas analiz.

Video Analiz sayfasinda mod, islenmis video uretimi ve debug log secenekleri bulunur. `Hizli sonuc modu` islenmis video yazmayi atlayarak yalniz event/snapshot/skor uretir.
