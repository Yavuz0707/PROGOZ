# Plate Detector Training

Bu klasor YOLOv8 ile `license_plate` sinifi icin object detection modeli egitir.

## Roboflow Indirme

`.env`:

```env
ROBOFLOW_API_KEY=
ROBOFLOW_WORKSPACE=plakatanima-vnt3k
ROBOFLOW_PROJECT=turkish-number-plates
ROBOFLOW_VERSION=1
ROBOFLOW_FORMAT=yolov8
```

```powershell
cd backend
python ml/training/plates/download_roboflow_plates.py
```

API key yoksa dataset'i Roboflow'dan manuel indirip `backend/ml/datasets/plates/yolo` klasorune koyun.

## YOLO Egitimi

```powershell
python ml/training/plates/train_plate_detector.py --model yolov8n.pt --epochs 50 --imgsz 640 --batch 8 --device 0
```

Model cikisi:

```text
backend/ml/models/plates/license_plate_detector.pt
```

## Evaluation

```powershell
python ml/training/plates/evaluate_plate_detector.py --model ml/models/plates/license_plate_detector.pt --data ml/datasets/plates/yolo/data.yaml
```
