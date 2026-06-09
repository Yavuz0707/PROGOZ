# PROGÖZ — Proaktif Gözetim Sistemi

PROGÖZ, güvenlik kameralarından veya yüklenen video dosyalarından gelen görüntülerde kavga, fiziksel saldırı, yakın temaslı şiddet, kaotik hareket ve anomali sinyallerini tespit etmeyi hedefleyen web tabanlı bir yapay zeka gözetim sistemidir.

Klasik kamera sistemleri sadece kayıt alır. PROGÖZ ise görüntüyü analiz eder, riskli durumları skorlar, olayları gruplayarak kullanıcıya sade bir panelde gösterir ve olay anına ait en iyi snapshot'ı saklar.

Bu sürüm final proje demosu için web uygulamasına odaklanır. Mobil uygulama kapsam dışıdır; ancak backend API mimarisi ileride mobil bildirim veya Firebase/FCM entegrasyonuna uygun şekilde tasarlanmıştır.

---

## Arayüz Tasarımı

PROGÖZ, iOS 26 esinli **tam siyah/beyaz/gri monokrom tema** kullanır. Teal/cyan renk paleti kaldırılmış, yerine saf siyah ve beyaz tonları getirilmiştir.

### Giriş Öncesi Splash Ekranı

Uygulama açılışında kullanıcıyı bir splash ekranı karşılar:

- Siyah arka plan üzerinde iki satır yatay kayan büyük metin animasyonu
  - Üst satır soldan sağa: `PROGÖZ • GÜVENLİK •`
  - Alt satır sağdan sola: `SECURITY • SYSTEM •`
- Ortada `PROGÖZ` başlığı ve beyaz `Başlayın →` butonu
- Butona tıklanınca splash yukarı kayarak çıkar, giriş formu aşağıdan yukarı animasyonla gelir

### Renk Şeması

| Token | Değer |
|---|---|
| Background | `#000000` |
| Surface | `#0f0f0f` |
| Card | `#141414` |
| Border | `#2a2a2a` |
| Text Primary | `#ffffff` |
| Text Secondary | `#888888` |
| Sidebar BG | `#080808` |
| Accent | `#ffffff` |
| Danger | `#ef4444` |
| Warning | `#f59e0b` |
| Success | `#4ade80` |

### Sidebar

- `#080808` arka plan
- Aktif menü: beyaz yazı + sol kenar beyaz çizgi göstergesi (`inset box-shadow`)
- Pasif menü: `#888` gri, hover'da beyaza döner

### Genel Bileşenler

- **Butonlar**: Beyaz arka plan / siyah yazı (primary), koyu gri (secondary)
- **Severity Badge**: KAVGA → kırmızı, OLASI_KAVGA → amber, ŞÜPHELİ → gri, NORMAL → koyu gri
- **Inputlar**: `#0f0f0f` zemin, focus'ta beyaz border
- **Grafikler**: Recharts — monokrom ızgara ve eksen renkleri, beyaz çizgiler
- **Scrollbar**: 4px ince, `#2a2a2a`
- **Geçiş animasyonları**: 150ms ease background/border/color global transition

---

## Öne Çıkan Özellikler

- FastAPI tabanlı JWT auth sistemi
- React + Vite + TypeScript modern dashboard
- SQLite veritabanı ve otomatik tablo oluşturma
- Video upload ile arka planda analiz
- Analiz sırasında "Analizi Durdur" butonu ile iptal desteği
- Webcam / RTSP kamera kaydı ve canlı analiz
- Canlı Kamera sayfasında kayıtlı kameralara ek olarak fiziksel cihaz (webcam) taraması
- CUDA varsa GPU, yoksa CPU fallback
- YOLOv8n-Pose + ByteTrack ile kişi tespiti ve takip
- OpenCV frame differencing ve Farneback optical flow
- Pair interaction tabanlı kavga/anomali skorlaması
- Kalabalık sahnelerde false positive azaltma filtreleri
- Yakın temas, restraint, pose contact ve grup baskısı sinyalleri
- Frame spam yerine gruplanmış Incident/Olay sistemi
- Her incident için max skor, ortalama skor, süre, timeline ve best snapshot
- İşlenmiş video üretimi opsiyonel, hızlı demo modu varsayılan
- WebSocket ile job progress ve canlı durum aktarımı
- Olayları doğru olay / yanlış alarm / yoksay olarak işaretleme
- Plaka tanıma: video ve canlı kamera akışları için vote-buffer tabanlı OCR deduplikasyonu

---

## Teknoloji Yığını

**Backend:**

- Python 3.10+
- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- Pydantic
- OpenCV, NumPy, SciPy
- Ultralytics YOLO
- PyTorch / TorchVision
- EasyOCR
- FFmpeg
- JWT auth

**Frontend:**

- React + Vite + TypeScript
- Tailwind CSS (monokrom tema — cyan/teal yok)
- Recharts
- Lucide React
- Axios
- WebSocket client

---

## Mimari Özet

```text
PROGÖZ
├── backend
│   ├── app
│   │   ├── api              # FastAPI endpointleri
│   │   ├── core             # CV, detector, analyzer, scoring, video processor, camera stream
│   │   ├── models           # SQLAlchemy modelleri
│   │   ├── schemas          # Pydantic response modelleri
│   │   ├── services         # Auth, upload, camera, incident, plate, websocket servisleri
│   │   └── static           # Upload, processed video, snapshot, clip, plate crop klasörleri
│   ├── ml                   # Model dosyaları ve eğitim scriptleri
│   ├── scripts              # CUDA kontrol ve yardımcı scriptleri
│   └── requirements.txt
├── frontend
│   └── src
│       ├── pages            # Dashboard, Video Upload, Events, Cameras, Live Camera, Plates
│       ├── components       # Layout (sidebar), SeverityBadge, StatCard
│       ├── hooks
│       └── api
├── docs
├── scripts
└── tests
```

---

## Computer Vision Pipeline

1. Video, webcam veya RTSP kaynağı OpenCV ile okunur.
2. YOLOv8n-Pose kişi tespiti yapar.
3. ByteTrack takip ile kişilere track id atanır.
4. Her kişi için hareket enerjisi, hız, bbox değişimi ve optical flow sinyalleri hesaplanır.
5. Skorlama tek kişi hareketine değil, kişi çifti etkileşimine odaklanır.
6. Proximity ve bbox overlap sadece aday etkileşim sinyalidir; tek başına kavga sayılmaz.
7. Mutual energy, mutual chaos, relative motion, temporal persistence ve pose/contact sinyalleri birlikte değerlendirilir.
8. Alarm skorlarından frame-level karar üretilir.
9. Ard arda gelen skorlar IncidentTracker ile tek kullanıcı olayı olarak gruplanır.
10. Incident içinde en yüksek skorlu frame best snapshot olarak kaydedilir.

---

## Incident / Olay Sistemi

PROGÖZ her yüksek skorlu frame'i ayrı ayrı kullanıcıya göstermek yerine olayları gruplar.

Bir incident kaydında şunlar bulunur:

- Kaynak tipi: video veya kamera
- Video dosyası ya da kamera id
- Başlangıç ve bitiş zamanı
- Süre
- Maksimum skor
- Ortalama skor
- Seviye: `SUPHELI`, `OLASI_KAVGA`, `KAVGA`
- İlgili track id'leri
- Score timeline
- Best snapshot
- Durum: `confirmed`, `false_positive`, `ignored`

---

## Analiz Modları

Varsayılan mod `fast`tır.

| Mod | Kullanım | Özellik |
|---|---|---|
| realtime | Canlı kamera | Düşük gecikme |
| fast | Demo video | 640 input, frame skip, hızlı olay çıkarma |
| balanced | Dengeli | Daha iyi kalite / hız dengesi |
| accurate | Detaylı | Daha yavaş, daha fazla frame analizi |

---

## Analiz İptali

Video analizi devam ederken "Analizi Durdur" butonu ile durdurulabilir. İptal edildiğinde:

- Mevcut frame işlemi tamamlanır, kuyruktaki diğer frame'ler temizlenir.
- O ana kadar biriken plaka vote buffer'ındaki kazanan plaka DB'ye yazılır.
- Tamamlanan incident kayıtları korunur.
- İş durumu `cancelled` olarak güncellenir.
- WebSocket üzerinden `analysis_cancelled` mesajı gönderilir.

---

## Canlı Kamera ve Webcam Desteği

Canlı Kamera sayfasında iki grup kamera seçeneği sunulur:

- **Kayıtlı Kameralar**: Veritabanına eklenmiş RTSP veya webcam tabanlı kameralar.
- **Bağlı Cihazlar**: Sunucu üzerinde fiziksel olarak bağlı webcam'ler. `GET /api/cameras/devices` endpointi `cv2.VideoCapture` ile 0–4 arası cihaz indekslerini tarar.

---

## Plaka Tanıma

Video upload ve canlı kamera akışları opsiyonel plaka tanıma destekler.

**Model**: YOLO tabanlı plaka detector `backend/ml/models/plates/license_plate_detector.pt` dosyasını kullanır. Model dosyası yoksa plaka pipeline'ı sessizce pas geçilir.

**Vote Buffer**: Her frame'de ayrı ayrı veritabanına yazmak yerine tüm OCR sonuçları bellekte toplanır:

- Video analizinde analiz bittikten sonra kazanan plaka tek bir kayıt olarak DB'ye yazılır.
- Canlı kamera akışında her 300 frame'de bir ve akış durdurulduğunda flush yapılır.
- Fuzzy matching ile benzer okumalar (%75 eşik) tek kayıt altında birleştirilir.

**OCR**: Varsayılan motor EasyOCR'dır. Türkiye plaka formatına normalize edilir.

---

## Fight Classifier Eğitimi

Kavga/şiddet modeli video clip classification olarak eğitilir.

```powershell
cd backend
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed --clear
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
python ml/training/fight/evaluate_fight_classifier.py --model ml/models/fight/fight_classifier.pt --data ml/datasets/fight/processed/test
```

---

## Windows Kurulumu

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

İlk admin kullanıcısını oluşturmak için proje kök dizininden:

```powershell
python scripts/create_admin.py --username admin --email admin@progoz.app --password admin123
```

Demo giriş bilgisi:

```
Kullanıcı adı: admin
Şifre:         admin123
```

> Not: `admin123` sadece demo içindir. Gerçek kullanımda değiştirilmelidir.

---

## Uygulamayı Çalıştırma

**Backend:**

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Frontend:**

```powershell
cd frontend
npm install
npm run dev
```

Adresler:

```
Web panel:    http://127.0.0.1:5173
Backend API:  http://127.0.0.1:8000
API Docs:     http://127.0.0.1:8000/docs
```

---

## Demo Akışı

1. `http://127.0.0.1:5173` adresine git.
2. Splash ekranında **Başlayın →** butonuna tıkla.
3. `admin / admin123` ile giriş yap.
4. Dashboard üzerinden CUDA ve sistem durumunu kontrol et.
5. **Video Analiz** sayfasına git, demo video yükle.
6. Opsiyonel olarak plaka tanımayı aktif et.
7. Varsayılan Hızlı Analiz modu ile analizi başlat.
8. Analiz bitince **Olaylar** sayfasında incident listesini incele.
9. Incident detayında best snapshot, skor timeline ve max/avg skor görülür.
10. **Plakalar** sayfasında tespit edilen araç plakalarını incele.
11. **Canlı Kamera** sayfasında webcam seçerek canlı analiz başlat.

---

## API Endpoint Özeti

**Auth:**

- `POST /api/auth/login`
- `GET /api/auth/me`

**Video analiz:**

- `POST /api/uploads/analyze`
- `GET /api/uploads/jobs`
- `GET /api/uploads/jobs/{job_id}/result`
- `POST /api/uploads/jobs/{job_id}/cancel`
- `GET /api/uploads/jobs/{job_id}/incidents`

**Incident:**

- `GET /api/incidents`
- `GET /api/incidents/{id}`
- `PUT /api/incidents/{id}/status`

**Kamera:**

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

**Plaka:**

- `GET /api/plates`
- `DELETE /api/plates/{id}`
- `POST /api/plates/cleanup-unreadable`
- `POST /api/plates/deduplicate`

**Sistem:**

- `GET /api/system/status`

---

## Testler

```powershell
pytest
```

---

## Güvenlik Notları

- `.env` repoya eklenmez.
- Şifreler hashlenir.
- JWT tabanlı auth kullanılır.
- Upload dosya uzantıları kontrol edilir.
- Veritabanı ve üretilen medya dosyaları `.gitignore` ile repoya eklenmez.

---

## Lisans

Bu proje eğitim ve final proje sunumu amacıyla hazırlanmıştır. Detaylar için `LICENSE` dosyasına bakınız.
