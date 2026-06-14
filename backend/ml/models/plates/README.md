# License Plate Detector Model

Bu klasore egitilmis YOLO plaka tespit modeli konur:

```text
backend/ml/models/plates/license_plate_detector.pt
```

Model `backend/ml/training/plates/train_plate_detector.py` ile uretilir. Uygulama `.env` icindeki su ayarla modeli yukler:

```env
PLATE_DETECTOR_MODEL_PATH=ml/models/plates/license_plate_detector.pt
```

Model yoksa plaka detector devreye girmez; uygulama geri kalan ozellikleriyle calismaya devam eder.
