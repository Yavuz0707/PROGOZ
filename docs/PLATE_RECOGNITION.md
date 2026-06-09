# Plaka Tanima

PROGOZ plaka tanima akisi iki asamalidir:

1. YOLO tabanli license plate detector frame icinde plaka kutularini bulur.
2. EasyOCR sadece plaka crop goruntusu uzerinde calisir ve sonuc Turkiye plaka formatina gore normalize edilir.

Video uzerine plaka kutusu cizmek ilk surumde zorunlu degildir. Kayit sistemi SQLite uzerinden video veya kamera kaynagina bagli calisir.

## Hazir Model Kullanimi

Varsayilan model konumu:

```text
backend/ml/models/plates/license_plate_detector.pt
```

Model yolu `.env` ile degistirilebilir:

```env
PLATE_DETECTOR_MODEL_PATH=ml/models/plates/license_plate_detector.pt
PLATE_DETECTOR_CONFIDENCE=0.25
PLATE_DETECTOR_IMGSZ=640
```

Model dosyasi yoksa plaka pipeline'i sonuc uretmeden pas gecilir; kavga/anomali analizi calismaya devam eder.

## OCR Motoru

Varsayilan OCR motoru EasyOCR'dir:

```env
PLATE_OCR_ENGINE=easyocr
PLATE_OCR_LANGUAGES=en
PLATE_OCR_MIN_CONFIDENCE=0.30
PLATE_SAVE_UNCERTAIN=true
PLATE_SAVE_UNREADABLE=false
PLATE_SHOW_UNREADABLE_IN_DEFAULT_LIST=false
PLATE_MIN_TEXT_LENGTH_TO_SAVE=5
PLATE_REQUIRE_VALID_FORMAT_FOR_DEFAULT=false
PLATE_TEST_IMAGE_AUTH_REQUIRED=false
PLATE_DEBUG_ENABLED=false
```

EasyOCR reader singleton olarak yuklenir; her frame'de yeniden olusturulmaz. Crop uzerinde original, 2x, 3x, gerekirse 4x resize, grayscale, CLAHE, sharpen, adaptive threshold, Otsu threshold ve bilateral sharpen varyantlari denenir. Dedektor plaka bulur ama OCR dusuk guven uretirse anlamli metin varsa kayit `uncertain` olarak tutulabilir.

OCR tamamen bos donerse varsayilan olarak SQLite'a `UNREADABLE` kaydi atilmaz. Bu davranis `PLATE_SAVE_UNREADABLE=false` ile spam'i engeller. Eski okunamayan kayitlar admin endpoint'i ile temizlenebilir:

```http
POST /api/plates/cleanup-unreadable
```

## Turkiye Plaka Formati

Post-process su yapilari hedefler:

```text
07 ABC 123
34 AB 1234
06 A 1234
35 ABC 12
```

Ham OCR sonucu uppercase yapilir, tire/nokta gibi karakterler temizlenir, il kodu ve sayi bolumlerinde `O/0`, `I/1`, `S/5` benzeri karisikliklar dikkatli sekilde duzeltilir. Regex'e uyan kayitlar `valid`, uymayan ama okunabilir kayitlar `uncertain` olarak tutulur.

## Video Plakalari

Video upload sirasinda `Plaka tanima aktif` secenegi aciksa her analiz moduna gore belirlenen aralikta frame incelenir:

```env
PLATE_FRAME_INTERVAL_FAST=5
PLATE_FRAME_INTERVAL_BALANCED=3
PLATE_FRAME_INTERVAL_ACCURATE=1
```

Kayitlarda `analysis_job_id`, `video_filename`, `first_seen_time_seconds`, `last_seen_time_seconds` ve `seen_count` tutulur.

## Kamera Plakalari

Kamera ayarlarinda plaka tanima acilip kapatilabilir ve frame araligi belirlenebilir. Kayitlarda `camera_id`, kamera adi, `first_seen_at`, `last_seen_at` ve `seen_count` tutulur. Canli WebSocket kanalina `plate_detected` mesaji gonderilir.

## Deduplication

Ayni plaka ayni kaynakta kisa sure icinde tekrar gorulurse yeni kayit acilmaz:

```env
PLATE_DEDUP_WINDOW_SECONDS=30
```

Video icin `analysis_job_id + normalized_plate`, kamera icin `camera_id + normalized_plate` temel alinir. Tekrar gorulen kayitta son gorulme, gorulme sayisi, en iyi guven ve snapshot guncellenir.

## Retention

Plaka kayitlari hassas veri kabul edilir. Varsayilan saklama suresi 7 gundur:

```env
PLATE_RETENTION_DAYS=7
PLATE_CLEANUP_ON_STARTUP=true
```

Uygulama acilisinda eski kayitlar temizlenir ve scheduler gunde bir kez tekrar calisir. Admin manuel temizlik icin:

```http
POST /api/plates/cleanup
```

Snapshot ve crop dosyalari da kayitla birlikte silinir.

## API

Temel endpointler:

```text
GET /api/plates
GET /api/plates/{id}
GET /api/plates/by-video/{analysis_job_id}
GET /api/plates/by-camera/{camera_id}
GET /api/plates/stats
DELETE /api/plates/{id}
POST /api/plates/cleanup
GET /api/plates/export/csv
POST /api/plates/test-image
POST /api/plates/cleanup-unreadable
```

`GET /api/plates` filtreleri: `source_type`, `camera_id`, `analysis_job_id`, `plate`, `valid_only`, `date_from`, `date_to`, `min_confidence`.

Tek gorsel testi icin Swagger'da `POST /api/plates/test-image` endpoint'ine multipart `file` alani ile JPG/PNG gonderilir. Development modda token gerekmez; production'da auth istenirse `.env` icinde `PLATE_TEST_IMAGE_AUTH_REQUIRED=true` yapilir. Cevapta detector durumu, bbox, OCR raw adaylari, normalize plaka adaylari, final secilen plaka, crop URL'i ve preprocess debug URL'leri doner. Bu endpoint video beklemeden model/OCR baglantisini test etmek icindir.

Debug gorselleri:

```text
backend/app/static/plate_debug/
```

## Kendi Modelini Egitmek

Opsiyonel egitim klasoru:

```text
backend/ml/training/plates/
```

YOLO dataset YAML ornegi:

```yaml
path: datasets/my_plate_dataset
train: images/train
val: images/val
names:
  0: plate
```

Egitim komutlari:

```powershell
cd backend
venv\Scripts\activate
python ml\training\plates\train_plate_detector.py --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Dataset kaynaklari icin Roboflow license plate datasetleri, OpenALPR Benchmark, CCPD benzeri acik veri setleri veya Turkiye plakalari icin ozel veri setleri kullanilabilir. Lisans ve kullanim haklari kontrol edilmelidir.
