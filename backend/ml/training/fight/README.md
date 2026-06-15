# Fight Classifier Training

Bu klasor PROGOZ icin `violence` / `non_violence` video classifier egitim scriptlerini icerir.

## Dataset

Raw klasor:

```text
backend/ml/datasets/fight/raw/
├── violence/
└── non_violence/
```

Alternatif adlar desteklenir: `fight`, `Violence`, `normal`, `NonViolence`, `nonviolence`, `non_fight`.

Onerilen veri sirasi:

1. Real Life Violence Situations Dataset
2. RWF-2000
3. Hockey Fight Dataset, ek destek/test icin
4. Kendi hard-negative normal/kalabalik videolariniz

## Hazirlama

```powershell
cd backend
python ml/training/fight/prepare_fight_dataset.py --raw ml/datasets/fight/raw --out ml/datasets/fight/processed --clear
```

## Egitim

Ilk egitim:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 20 --batch-size 4 --clip-len 16 --device cuda
```

Daha iyi egitim:

```powershell
python ml/training/fight/train_fight_classifier.py --epochs 40 --batch-size 4 --clip-len 32 --device cuda
```

Model cikisi:

```text
backend/ml/models/fight/fight_classifier.pt
```

## Evaluation

```powershell
python ml/training/fight/evaluate_fight_classifier.py --model ml/models/fight/fight_classifier.pt --data ml/datasets/fight/processed/test
```

Evaluation accuracy, precision, recall, f1, confusion matrix ve false positive / false negative ornekleri verir.

Ayrintili rehber: `docs/FIGHT_MODEL_TRAINING.md`.
