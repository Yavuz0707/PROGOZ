# PROGOZ Training Guide

Bu dokuman PROGOZ icin iki ayri egitim hattini aciklar:

1. Kavga / siddet video classifier modeli
2. Plaka YOLO object detection modeli

Bu modeller ayni problem degildir ve ayni modelle egitilmez.

## GPU Kontrol

```powershell
cd backend
python scripts/check_cuda.py
```

RTX 4050 icin beklenen:

```text
CUDA available: True
Selected device: cuda:0
```

CUDA yoksa scriptler CPU fallback yapabilir ama egitim cok yavaslar.

## Klasorler

```text
backend/ml/datasets/fight
backend/ml/datasets/plates
backend/ml/training/fight
backend/ml/training/plates
backend/ml/models/fight
backend/ml/models/plates
```

## Model Path Ayarlari

`.env`:

```env
FIGHT_CLASSIFIER_ENABLED=true
FIGHT_CLASSIFIER_MODEL_PATH=ml/models/fight/fight_classifier.pt
PLATE_DETECTOR_MODEL_PATH=ml/models/plates/license_plate_detector.pt
```

Model dosyalari yoksa uygulama calismaya devam eder. Fight classifier yoksa heuristic scoring kullanilir. Plate detector yoksa plaka detection devreye girmez.

## Lisans Notu

Roboflow, Kaggle, RWF-2000 veya baska datasetleri kullanmadan once lisans ve kullanim sartlarini kontrol edin. Datasetler bu repoya eklenmemelidir.

## Hızli Komutlar

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
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed --clear
```

Kavga modeli egit:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
```

Daha iyi kavga modeli egit:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 40 --batch-size 4 --clip-len 32 --device cuda
```

Kavga modeli degerlendir:

```powershell
python ml/training/fight/evaluate_fight_classifier.py --model ml/models/fight/fight_classifier.pt --data ml/datasets/fight/processed/test
```

Real Life Violence Situations Dataset ilk egitim icin onerilir. RWF-2000 surveillance tarzi nedeniyle ikinci guclu datasettir ama genelde manuel temin gerekir. Hockey Fight ek destek/test olarak kullanilabilir. Kendi normal kalabalik ve yakin temas ama kavga olmayan videolarinizi `ml/datasets/fight/raw/non_violence` altina eklemek false positive azaltmak icin kritiktir.
