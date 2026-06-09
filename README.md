# PROGOZ - Proaktif Gozetim Sistemi

PROGOZ, guvenlik kameralarindan veya yuklenen video dosyalarindan gelen goruntulerde kavga, fiziksel saldiri, yakin temasli siddet, kaotik hareket ve anomali sinyallerini tespit etmeyi hedefleyen web tabanli bir yapay zeka gozetim sistemidir.

Klasik kamera sistemleri sadece kayit alir. PROGOZ ise goruntuyu analiz eder, riskli durumlari skorlar, olaylari gruplayarak kullaniciya sade bir panelde gosterir ve olay anina ait en iyi snapshot'i saklar.

Bu surum final proje demosu icin web uygulamasina odaklanir. Mobil uygulama kapsam disidir; ancak backend API mimarisi ileride mobil bildirim veya Firebase/FCM entegrasyonuna uygun sekilde tasarlanmistir.

## One Cikan Ozellikler

- FastAPI tabanli JWT auth sistemi
- React + Vite + TypeScript modern dashboard
- SQLite veritabani ve otomatik tablo olusturma
- Video upload ile arka planda analiz
- Analiz sirasinda "Analizi Durdur" butonu ile iptal destegi
- Webcam / RTSP kamera kaydi ve canli analiz
- Canli Kamera sayfasinda kayitli kameralara ek olarak fiziksel cihaz (webcam) taramasi
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
- Plaka tanima: video ve canli kamera akislari icin vote-buffer tabanli OCR deduplikasyonu

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
- EasyOCR
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
│   │   ├── core             # CV, detector, analyzer, scoring, video processor, camera stream
│   │   ├── models           # SQLAlchemy modelleri
│   │   ├── schemas          # Pydantic response modelleri
│   │   ├── services         # Auth, upload, camera, incident, plate, websocket servisleri
│   │   └── static           # Upload, processed video, snapshot, clip, plate crop klasorleri
│   ├── ml                   # Model dosyalari ve egitim scriptleri
│   ├── scripts              # CUDA kontrol ve yardimci scriptleri
│   └── requirements.txt
├── frontend
│   └── src
│       ├── pages            # Dashboard, Video Upload, Events, Cameras, Live Camera, Plates
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
- Plaka tanima aktif
- Debug log acik
- Sadece olaylari cikar

Varsayilan akista islenmis video uretmek kapali tutulur. Sistem once olaylari, snapshot'i ve skor timeline'ini cikarir. Bu demo performansini belirgin sekilde artirir.

## Analiz Iptali

Video analizi devam ederken "Analizi Durdur" butonu ile durdurulabilir. Iptal edildiginde:

- Mevcut frame islemi tamamlanir, kuyruktaki diger frame'ler temizlenir.
- O ana kadar biriken plaka vote buffer'indaki kazanan plaka DB'ye yazilir.
- Tamamlanan incident kayitlari korunur.
- Is durumu `cancelled` olarak guncellenir.
- WebSocket uzerinden `analysis_cancelled` mesaji gonderilir.
- Frontend is durumunu iptal edildi olarak gosterir.

## Canli Kamera ve Webcam Destegi

Canli Kamera sayfasinda iki grup kamera secenegi sunulur:

- **Kayitli Kameralar**: Veritabanina eklenmis RTSP veya webcam tabanli kameralar.
- **Bagli Cihazlar**: Sunucu uzerinde fiziksel olarak bagli webcam'ler. `GET /api/cameras/devices` endpointi `cv2.VideoCapture` ile 0–4 arasi cihaz indekslerini tarar; frame okuyabilen cihazlar listede gorunur (Windows icin DirectShow backend kullanilir).

Webcam'ler kayitli kamera gibi `POST /api/cameras/webcam/start` ve `POST /api/cameras/webcam/stop` endpointleri ile baslatilip durdurulur. MJPEG akisi ve WebSocket bildirimleri kayitli kameralarda oldugu gibi calisir.

## Plaka Tanima

Video upload ve canli kamera akislari opsiyonel plaka tanima destekler.

**Model**: YOLO tabanli plaka detector `backend/ml/models/plates/license_plate_detector.pt` dosyasini kullanir. Model dosyasi yoksa plaka pipeline'i sessizce pas gecilir; kavga/anomali analizi etkilenmez.

**Vote Buffer**: Plaka pipeline'i her frame'de ayri ayri veritabanina yazmaz. Bunun yerine tum tespit edilen OCR sonuclari bellekte biriken bir vote buffer'inda toplanir:

- Video analizinde analiz bittikten sonra buffer'daki kazanan plaka tek bir kayit olarak DB'ye yazilir.
- Canli kamera akisinda her 300 frame'de bir (~30 saniye, 10 fps'de) ve akis durduruldugunda flush yapilir.
- Fuzzy matching ile benzer okumalar (esik: %75 benzerlik) tek kayit altinda birlestirilir.

Bu yontemle ayni plakadan onlarca tekrar kayit olusumu engellenir.

**OCR**: Varsayilan motor EasyOCR'dir. Birden fazla onislem varyantinda denenir ve Turkiye plaka formatina normalize edilir. `PLATE_SAVE_UNCERTAIN=true` ile dusuk guvenli okumalar da `Dusuk guven` etiketiyle Plakalar sayfasinda gorunur. `PLATE_SAVE_UNREADABLE=false` (varsayilan) ile bos OCR sonuclari kaydedilmez.

**Plakalar Sayfasi**: Sidebar'daki Plakalar sayfasinda tum kayitlar, video kaynakli plakalar ve kamera kaynakli plakalar ayri sekmelerle listelenir. Video kayitlarinda videonun saniyesi, kamera kayitlarinda gercek tarih/saat tutulur.

**Veri Temizleme**: Plaka kayitlari hassas veri kabul edildigi icin varsayilan saklama suresi 7 gundur. Uygulama acilisinda ve gunde bir kez eski kayitlar ile snapshot/crop dosyalari temizlenir.

Ayrintili dokumantasyon: `docs/PLATE_RECOGNITION.md`

## Fight Classifier Egitimi

Kavga/siddet modeli video clip classification olarak egitilir. Ilk dataset icin Real Life Violence Situations Dataset, ikinci guclu veri icin RWF-2000 onerilir. Hockey Fight ek destek/test olarak kullanilabilir. Kendi normal/kalabalik hard-negative videolarinizi `backend/ml/datasets/fight/raw/non_violence/` altina eklemek false positive azaltmak icin onemlidir.

Raw dataset yapisi:

```text
backend/ml/datasets/fight/raw/
├── violence/
└── non_violence/
```

Hazirlama ve egitim:

```powershell
cd backend
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed --clear
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
python ml/training/fight/evaluate_fight_classifier.py --model ml/models/fight/fight_classifier.pt --data ml/datasets/fight/processed/test
```

Daha iyi egitim icin:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 40 --batch-size 4 --clip-len 32 --device cuda
```

Egitilen modeli uygulamaya baglamak icin:

```env
FIGHT_CLASSIFIER_ENABLED=true
FIGHT_CLASSIFIER_MODEL_PATH=ml/models/fight/fight_classifier.pt
FIGHT_CLASSIFIER_CLIP_LEN=16
FIGHT_CLASSIFIER_FRAME_SIZE=224
FIGHT_CLASSIFIER_INTERVAL=5
```

Ayrintilar: `docs/FIGHT_MODEL_TRAINING.md`

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

Repo kokunden acilan VS Code icin `.vscode/settings.json` su interpreter'i isaret eder:

```text
C:\Users\sukru\Desktop\PROGÖZ\backend\venv\Scripts\python.exe
```

Workspace'i direkt `backend` klasorunden acarsaniz interpreter'i manuel secmeniz gerekir.

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

Backend farkli bir portta calisiyorsa frontend API adresi `frontend/.env` icinden ayarlanir:

```env
VITE_API_BASE_URL=http://127.0.0.1:8002
```

`.env` degistikten sonra Vite dev server yeniden baslatilmalidir.

Adresler:

```text
Web panel:    http://127.0.0.1:5173
Backend API:  http://127.0.0.1:8000
API Docs:     http://127.0.0.1:8000/docs
```

## Demo Akisi

1. Web paneli acilir.
2. `admin / admin123` ile giris yapilir.
3. Dashboard uzerinden CUDA ve sistem durumu kontrol edilir.
4. Video Analiz sayfasina gidilir.
5. Demo video yuklenir.
6. Opsiyonel olarak plaka tanima aktif edilir.
7. Varsayilan Hizli Analiz modu ile analiz baslatilir.
8. Analiz sirasinda "Analizi Durdur" butonuyla iptal edilebilir.
9. Analiz bitince bulunan olay sayisi gosterilir.
10. Olaylar sayfasinda video/kamera filtreleriyle incident listesi incelenir.
11. Incident detayinda best snapshot, skor timeline ve max/avg skor gorulur.
12. Yanlis alarm varsa false_positive olarak isaretlenebilir.
13. Plakalar sayfasinda tespit edilen arac plakalari incelenir.
14. Canli Kamera sayfasinda kayitli kamera veya dogrudan bagli webcam secilerek canli analiz baslatilir.

## API Endpoint Ozeti

Auth:

- `POST /api/auth/login`
- `GET /api/auth/me`

Video analiz:

- `POST /api/uploads/analyze`
- `GET /api/uploads/jobs`
- `GET /api/uploads/jobs/{job_id}/result`
- `POST /api/uploads/jobs/{job_id}/cancel`
- `GET /api/uploads/jobs/{job_id}/incidents`

Incident:

- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `PUT /api/incidents/{id}/status`

Kamera:

- `GET /api/cameras`
- `POST /api/cameras`
- `GET /api/cameras/devices`
- `POST /api/cameras/webcam/start`
- `POST /api/cameras/webcam/stop`
- `GET /api/cameras/{id}`
- `PUT /api/cameras/{id}`
- `DELETE /api/cameras/{id}`
- `POST /api/cameras/{id}/start`
- `POST /api/cameras/{id}/stop`
- `GET /api/cameras/{id}/incidents`

Plaka:

- `GET /api/plates`
- `GET /api/plates/{id}`
- `DELETE /api/plates/{id}`
- `POST /api/plates/test-image`
- `POST /api/plates/cleanup-unreadable`
- `POST /api/plates/deduplicate`

Sistem:

- `GET /api/system/status`

## Testler

```powershell
pytest
```

Testler scoring, motion analyzer, auth ve API olay akislari icin temel guvence saglar.

## Model Egitimi

PROGOZ iki ayri egitim hattini destekler:

- Kavga / siddet video classifier: `backend/ml/training/fight`
- Plaka YOLO detector: `backend/ml/training/plates`

Plaka dataset indir:

```powershell
cd backend
python ml/training/plates/download_roboflow_plates.py
```

Plaka modeli egit:

```powershell
python ml/training/plates/train_plate_detector.py --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Kavga dataset hazirla:

```powershell
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed
```

Kavga modeli egit:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
```

Detaylar:

- `docs/TRAINING_GUIDE.md`
- `docs/FIGHT_MODEL_TRAINING.md`
- `docs/PLATE_MODEL_TRAINING.md`

## Performans Notlari

- YOLO modeli application-level singleton olarak yuklenir.
- CUDA varsa `cuda:0` kullanilir.
- CUDA'da half precision denenir; hata olursa otomatik fallback yapilir.
- Fast modda her frame'e agir inference uygulanmaz.
- Optical flow interval ile sinirlandirilir.
- SQLite'a frame frame event yazilmaz; incident sistemi gruplar.
- Plaka tespiti vote buffer ile calisir: frame basi DB yazimi yoktur, analiz sonu tek kazanan kayit yazilir.
- Canli kamera plaka vote buffer her 300 frame'de ve akis kapanirken flush edilir.
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
