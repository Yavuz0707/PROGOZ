# Plate Model Training

Plaka tespiti YOLO object detection problemidir. Kavga classifier ile ayni model kullanilmaz. Bu model sadece `license_plate` sinifini bulur; OCR ise crop uzerinde EasyOCR/PaddleOCR fallback ile calisir.

## Roboflow Turkish Number Plates

Onerilen dataset:

- Roboflow Turkish Number Plates
- Object Detection
- YOLOv8 export
- Turkiye plakalari icin uygundur

`.env`:

```env
ROBOFLOW_API_KEY=
ROBOFLOW_WORKSPACE=plakatanima-vnt3k
ROBOFLOW_PROJECT=turkish-number-plates
ROBOFLOW_VERSION=1
ROBOFLOW_FORMAT=yolov8
```

## Dataset Indirme

```powershell
cd backend
python ml/training/plates/download_roboflow_plates.py
```

API key yoksa script acik hata verir. Bu durumda Roboflow'dan YOLOv8 formatinda manuel indirip su klasore koyun:

```text
backend/ml/datasets/plates/yolo
```

Bu klasorde `data.yaml` bulunmalidir.

## YOLOv8 Egitimi

RTX 4050 6GB icin varsayilan:

- model: yolov8n.pt
- imgsz: 640
- epochs: 50
- batch: 8
- workers: 4
- device: 0
- patience: 10

```powershell
python ml/training/plates/train_plate_detector.py --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Daha iyi dogruluk icin:

```powershell
python ml/training/plates/train_plate_detector.py --model yolov8s.pt --epochs 80 --imgsz 640 --batch 6 --device 0
```

Model cikisi:

```text
backend/ml/models/plates/license_plate_detector.pt
```

## Evaluation

```powershell
python ml/training/plates/evaluate_plate_detector.py --model ml/models/plates/license_plate_detector.pt --data ml/datasets/plates/yolo/data.yaml
```

## Uygulamaya Baglama

`.env`:

```env
PLATE_RECOGNITION_ENABLED=true
PLATE_DETECTOR_MODEL_PATH=ml/models/plates/license_plate_detector.pt
PLATE_DETECTOR_IMGSZ=640
PLATE_DETECTOR_CONFIDENCE=0.45
PLATE_OCR_ENGINE=easyocr
```

Model yoksa detector devreye girmez; uygulama geri kalan ozellikleriyle calismaya devam eder.

## OCR

YOLO plaka bolgesini bulur, PROGOZ crop alir ve OCR'a verir. EasyOCR varsayilan motordur. OCR sonucu normalize edilerek Turkiye plaka formatina yaklastirilir.
