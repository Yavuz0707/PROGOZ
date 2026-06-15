# Plate Detection Training

Bu klasor opsiyonel YOLO plaka tespit egitimi icindir. Ana uygulama egitim surecine bagli degildir; `backend/models/license_plate_detector.pt` dosyasi varsa runtime detector bunu kullanir.

## Dataset

YOLO dataset YAML ornegi:

```yaml
path: datasets/my_plate_dataset
train: images/train
val: images/val
names:
  0: plate
```

Acik dataset kullanirken lisansini kontrol edin. Roboflow license plate datasetleri, OpenALPR Benchmark, CCPD benzeri veri setleri veya Turkiye plakalari icin ozel YOLO formatli veri kullanilabilir.

## Egitim

```powershell
cd backend
venv\Scripts\activate
python ml\plate_detection\train_plate_detector.py
python ml\plate_detection\export_plate_model.py
copy ml\plate_detection\models\license_plate_detector.pt models\license_plate_detector.pt
```
