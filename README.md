# PROGOZ - Proaktif Gozetim Sistemi

PROGOZ, guvenlik kameralarindan veya yuklenen video dosyalarindan gelen goruntulerde kavga, fiziksel saldiri, yakin temasli siddet, kaotik hareket ve anomali sinyallerini tespit etmeyi hedefleyen web tabanli bir yapay zeka gozetim sistemidir.

Klasik kamera sistemleri sadece kayit alir. PROGOZ ise goruntuyu analiz eder, riskli durumlari skorlar, olaylari gruplayarak kullaniciya sade bir panelde gosterir ve olay anina ait en iyi snapshot'i saklar.

Bu surum final proje demosu icin web uygulamasina odaklanir. Mobil uygulama kapsam disidir; ancak backend API mimarisi ileride mobil bildirim veya Firebase/FCM entegrasyonuna uygun sekilde tasarlanmistir.

## One Cikan Ozellikler

- FastAPI tabanli JWT auth sistemi
- React + Vite + TypeScript modern dashboard
- SQLite veritabani ve otomatik tablo olusturma
- Video upload ile arka planda analiz
- Webcam / RTSP kamera kaydi ve canli analiz
- CUDA varsa GPU, yoksa CPU fallback
- YOLOv8n-Pose + ByteTrack ile kisi tespiti ve takip
- OpenCV frame differencing ve Farneback optical flow
- Pair interaction tabanli kavga/anomali skorlamasi
- Kalabalik sahnelerde false positive azaltma filtreleri
- Yakin temas, restraint, pose contact ve grup baskisi sinyalleri
- Frame spam yerine gruplanmis Incident/Olay sistemi
- Her incident icin max skor, ortalama skor, sure, timeline ve best snapshot
- Islenmis video uretimi opsiyonel, hizli demo modu varsayilan
- WebSocket ile job progress ve canli durum aktarimi
- Olaylari dogru olay / yanlis alarm / yoksay olarak isaretleme

## Teknoloji Yigini

Backend:

- Python 3.10+
- FastAPI
- Uvicorn
- SQLAlchemy
- SQLite
- Pydantic
- OpenCV
- NumPy / SciPy
- Ultralytics YOLO
- PyTorch / TorchVision
- FFmpeg
- JWT auth

Frontend:

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts
- Lucide React
- Axios
- WebSocket client

## Mimari Ozet

```text
PROGOZ
├── backend
│   ├── app
│   │   ├── api              # FastAPI endpointleri
│   │   ├── core             # CV, detector, analyzer, scoring, video processor
│   │   ├── models           # SQLAlchemy modelleri
│   │   ├── schemas          # Pydantic response modelleri
│   │   ├── services         # Auth, upload, camera, incident, websocket servisleri
│   │   └── static           # Upload, processed video, snapshot, clip klasorleri
│   ├── scripts              # CUDA kontrol scriptleri
│   └── requirements.txt
├── frontend
│   └── src
│       ├── pages            # Dashboard, Video Upload, Events, Cameras
│       ├── components
│       ├── hooks
│       └── api
├── docs
├── scripts
└── tests
```

## Computer Vision Pipeline

1. Video, webcam veya RTSP kaynagi OpenCV ile okunur.
2. YOLOv8n-Pose kisi tespiti yapar.
3. ByteTrack takip ile kisilere track id atanir.
4. Her kisi icin hareket enerjisi, hiz, bbox degisimi ve optical flow sinyalleri hesaplanir.
5. Skorlama tek kisi hareketine degil, kisi cifti etkilesimine odaklanir.
6. Proximity ve bbox overlap sadece aday etkilesim sinyalidir; tek basina kavga sayilmaz.
7. Mutual energy, mutual chaos, relative motion, temporal persistence ve pose/contact sinyalleri birlikte degerlendirilir.
8. Alarm skorlarindan frame-level karar uretilir.
9. Ard arda gelen skorlar IncidentTracker ile tek kullanici olayi olarak gruplanir.
10. Incident icinde en yuksek skorlu frame best snapshot olarak kaydedilir.

## Incident / Olay Sistemi

PROGOZ her yuksek skorlu frame'i ayri ayri kullaniciya gostermek yerine olaylari gruplar.

Bir incident kaydinda sunlar bulunur:

- kaynak tipi: video veya kamera
- video dosyasi ya da kamera id
- baslangic ve bitis zamani
- sure
- maksimum skor
- ortalama skor
- seviye: SUPHELI, OLASI_KAVGA, KAVGA
- ilgili track id'leri
- score timeline
- best snapshot
- durum: confirmed, false_positive, ignored

Bu sayede Events sayfasinda ayni kavga icin onlarca satir yerine tek anlamli olay kaydi gorunur.

## Analiz Modlari

Varsayilan mod `fast`tir. Demo videolari icin daha hizli sonuc verir.

| Mod | Kullanim | Ozellik |
| --- | --- | --- |
| realtime | Canli kamera | Dusuk gecikme, eski frame biriktirmeme |
| fast | Demo video | 640 input, frame skip, hizli olay cikarma |
| balanced | Dengeli | Daha iyi kalite / hiz dengesi |
| accurate | Detayli | Daha yavas, daha fazla frame analizi |

Video analiz sayfasinda su secenekler bulunur:

- Hizli Analiz
- Dengeli
- Detayli
- Islenmis video uret
- Debug log acik
- Hizli sonuc modu

Varsayilan akista islenmis video uretmek kapali tutulur. Sistem once olaylari, snapshot'i ve skor timeline'ini cikarir. Bu demo performansini belirgin sekilde artirir.

## Windows Kurulumu

Backend klasorune girin:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/check_cuda.py
```

Kolay kurulum:

```powershell
cd backend
setup_windows.bat
```

Ilk admin kullanicisini olusturmak icin proje kok dizininden:

```powershell
python scripts/create_admin.py --username admin --email admin@progoz.app --password admin123
```

Demo giris bilgisi:

```text
Kullanici adi: admin
Sifre: admin123
```

> Not: `admin123` sadece demo icindir. Gercek kullanimda degistirilmelidir.

## CUDA Kontrolu

PowerShell'e direkt Python kodu yazmayin:

```powershell
print(torch.cuda.is_available())
```

Bu yanlistir, cunku PowerShell bunu Python olarak calistirmaz.

Dogru yontem:

```powershell
cd backend
python scripts/check_cuda.py
```

Beklenen RTX 4050 ornek ciktisi:

```text
CUDA available: True
GPU: NVIDIA GeForce RTX 4050 Laptop GPU
Selected device: cuda:0
```

CUDA aktif degilse sistem CPU fallback ile calisir, ancak analiz suresi belirgin sekilde uzayabilir.

## VS Code Interpreter Ayari

FastAPI import uyarilari gorurseniz:

1. `Ctrl + Shift + P`
2. `Python: Select Interpreter`
3. `backend\venv\Scripts\python.exe` secin
4. VS Code penceresini yeniden yukleyin

Bu ayar `Import "fastapi" could not be resolved` gibi uyarilari cozer.

## Uygulamayi Calistirma

Backend:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Adresler:

```text
Web panel:    http://127.0.0.1:5173
Backend API:  http://127.0.0.1:8000
API Docs:     http://127.0.0.1:8000/docs
```

Normal kullanim icin yalnizca web paneli acilir:

```text
http://127.0.0.1:5173
```

## Demo Akisi

1. Web paneli acilir.
2. `admin / admin123` ile giris yapilir.
3. Dashboard uzerinden CUDA ve sistem durumu kontrol edilir.
4. Video Analiz sayfasina gidilir.
5. Demo video yuklenir.
6. Varsayilan Hizli Analiz modu ile incident'lar cikarilir.
7. Analiz bitince bulunan olay sayisi gosterilir.
8. Olaylar sayfasinda video/kamera filtreleriyle incident listesi incelenir.
9. Incident detayinda best snapshot, skor timeline ve max/avg skor gorulur.
10. Yanlis alarm varsa false_positive olarak isaretlenebilir.

## API Endpoint Ozeti

Auth:

- `POST /api/auth/login`
- `GET /api/auth/me`

Video analiz:

- `POST /api/uploads/analyze`
- `GET /api/uploads/jobs`
- `GET /api/uploads/jobs/{job_id}/result`
- `GET /api/uploads/jobs/{job_id}/incidents`

Incident:

- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `PUT /api/incidents/{id}/status`

Kamera:

- `GET /api/cameras`
- `POST /api/cameras`
- `POST /api/cameras/{id}/start`
- `POST /api/cameras/{id}/stop`
- `GET /api/cameras/{id}/incidents`

Sistem:

- `GET /api/system/status`

## Testler

```powershell
pytest
```

Testler scoring, motion analyzer, auth ve API olay akislari icin temel guvence saglar.

## Performans Notlari

- YOLO modeli application-level singleton olarak yuklenir.
- CUDA varsa `cuda:0` kullanilir.
- CUDA'da half precision denenir; hata olursa otomatik fallback yapilir.
- Fast modda her frame'e agir inference uygulanmaz.
- Optical flow interval ile sinirlandirilir.
- SQLite'a frame frame event yazilmaz.
- Snapshot sadece confirmed incident icin secilir.
- Islenmis video opsiyoneldir.

## Guvenlik Notlari

- `.env` repoya eklenmez.
- Sifreler hashlenir.
- JWT tabanli auth kullanilir.
- Upload dosya uzantilari kontrol edilir.
- Veritabani ve uretilen medya dosyalari `.gitignore` ile repoya eklenmez.

## Lisans

Bu proje egitim ve final proje sunumu amaciyla hazirlanmistir. Detaylar icin `LICENSE` dosyasina bakiniz.
