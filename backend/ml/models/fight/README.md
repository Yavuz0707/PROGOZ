# Fight Classifier Model

Bu klasore egitilmis video siniflandirma modeli konur:

```text
backend/ml/models/fight/fight_classifier.pt
```

Model `backend/ml/training/fight/train_fight_classifier.py` ile uretilir. Uygulamada kullanmak icin `.env`:

```env
FIGHT_CLASSIFIER_ENABLED=true
FIGHT_CLASSIFIER_MODEL_PATH=ml/models/fight/fight_classifier.pt
```

Model yoksa PROGOZ heuristic scoring ile calismaya devam eder.
