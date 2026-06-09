# Fight Model Training

PROGOZ icin siddet/kavga tespiti video clip classification problemidir. Plaka modeli object detection yapar; fight modeli ayri egitilir ve `violence` / `non_violence` olasiligi uretir.

## Dataset Stratejisi

Ilk egitim icin ana dataset:

- Real Life Violence Situations Dataset
- 1000 violence + 1000 non-violence video
- Gercek hayat siddet ve normal insan aktivitesi icerir

Ikinci guclu dataset:

- RWF-2000
- Surveillance kamera tarzina daha yakindir
- Otomatik indirme garanti edilmez; manuel yerlestirme desteklenir

Ek destek/test dataset:

- Hockey Fight Dataset
- Ana dataset olarak tek basina kullanilmaz
- Ek fight/non-fight varyasyonu icin eklenebilir

Hard-negative dataset:

- Normal kalabalik koridor
- Yan yana duran veya konusan insanlar
- Hizli yuruyen kisiler
- Spor yapan ama kavga etmeyen insanlar
- Kamera onunden hizli gecen insanlar

Yanlis alarmlari azaltmak icin kendi normal/kalabalik videolarinizi mutlaka `non_violence` sinifina ekleyin.

## Raw Klasor Yapisi

Standart yapi:

```text
backend/ml/datasets/fight/raw/
├── violence/
│   ├── video1.mp4
│   └── ...
└── non_violence/
    ├── video1.mp4
    └── ...
```

Desteklenen alternatif klasor adlari:

- `fight`, `fights`, `violent`, `Violence` -> `violence`
- `normal`, `nonviolence`, `NonViolence`, `non-violence`, `non_fight` -> `non_violence`

Script raw klasoru altinda ic ice dataset klasorlerini de tarar. Ornek:

```text
backend/ml/datasets/fight/raw/Real Life Violence Dataset/Violence/
backend/ml/datasets/fight/raw/Real Life Violence Dataset/NonViolence/
```

## Datasetleri Yerlestirme

### Real Life Violence Situations Dataset

Dataset'i manuel indirin ve videolari su yapida koyun:

```text
backend/ml/datasets/fight/raw/violence/
backend/ml/datasets/fight/raw/non_violence/
```

Eger indirdiginiz paket `Violence` ve `NonViolence` klasorleriyle gelirse bu adlar da desteklenir.

### RWF-2000

RWF-2000 dosyalari her zaman dogrudan public download olarak sunulmayabilir. Manuel temin edip ayni raw yapisina yerlestirin:

```text
backend/ml/datasets/fight/raw/rwf2000/violence/
backend/ml/datasets/fight/raw/rwf2000/non_violence/
```

### Hockey Fight Dataset

Kaggle veya farkli kaynaklardan manuel indirilebilir. Ek dataset olarak kullanin:

```text
backend/ml/datasets/fight/raw/hockey/fight/
backend/ml/datasets/fight/raw/hockey/non_fight/
```

### Kendi Hard-Negative Videolariniz

Normal ama modele zor gelen videolari non_violence sinifina ekleyin:

```text
backend/ml/datasets/fight/raw/non_violence/my_crowd_001.mp4
backend/ml/datasets/fight/raw/non_violence/people_talking_001.mp4
backend/ml/datasets/fight/raw/non_violence/fast_walk_001.mp4
```

Bu adim normal kalabaligin kavga sanilmasini azaltmak icin kritik.

## Opsiyonel Kaggle Indirme

`.env`:

```env
KAGGLE_USERNAME=
KAGGLE_KEY=
KAGGLE_FIGHT_DATASET_SLUG=
```

Kaggle slug biliyorsaniz:

```powershell
cd backend
python ml/training/fight/download_kaggle_fight_dataset.py --slug owner/dataset-name --unzip
```

Credential yoksa script acik hata verir; manuel indirme her zaman desteklenir.

## Dataset Hazirlama

```powershell
cd backend
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed --clear
```

Cikti:

```text
backend/ml/datasets/fight/processed/
├── train/
│   ├── violence/
│   └── non_violence/
├── val/
│   ├── violence/
│   └── non_violence/
├── test/
│   ├── violence/
│   └── non_violence/
└── manifest.json
```

`manifest.json` hangi kaynaktan kac video geldigini ve split sayilarini raporlar.

## Model

Mevcut model MobileNetV2 feature extractor + BiLSTM yapisindadir:

- input: 16 veya 32 frame
- frame size: 224
- output: violence probability
- CUDA varsa GPU kullanir
- model yoksa uygulama heuristic fallback ile calisir

## Ilk Egitim Profili

RTX 4050 6GB icin onerilen ilk deneme:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
```

## Daha Iyi Egitim Profili

Daha uzun ve daha guclu egitim:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 40 --batch-size 4 --clip-len 32 --device cuda
```

GPU bellek yetmezse `--batch-size 2` kullanin.

Model cikisi:

```text
backend/ml/models/fight/fight_classifier.pt
```

## Evaluation

```powershell
python ml/training/fight/evaluate_fight_classifier.py --model ml/models/fight/fight_classifier.pt --data ml/datasets/fight/processed/test
```

Rapor:

- accuracy
- precision
- recall
- f1 score
- confusion matrix
- false positive ornekleri
- false negative ornekleri

JSON rapor:

```text
backend/ml/runs/fight/evaluation_report.json
```

False positive orneklerinde normal kalabaligin kavga sanilip sanilmadigina bakilmali. False negative orneklerinde gercek kavganin kacirilip kacirilmadigi incelenmelidir.

## Uygulamaya Baglama

`.env`:

```env
FIGHT_CLASSIFIER_ENABLED=true
FIGHT_CLASSIFIER_MODEL_PATH=ml/models/fight/fight_classifier.pt
FIGHT_CLASSIFIER_CLIP_LEN=16
FIGHT_CLASSIFIER_FRAME_SIZE=224
FIGHT_CLASSIFIER_INTERVAL=5
```

Fusion:

```text
final_score =
0.60 * fight_classifier_score
0.20 * interaction_score
0.10 * optical_flow_score
0.10 * pose_contact_score
```

VideoProcessor ve camera_stream ayni runtime classifier'i kullanir. Model dosyasi yoksa sistem cokmez; heuristic scoring calismaya devam eder.
