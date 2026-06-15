from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    root = Path(__file__).resolve().parent
    weights = root / "runs" / "license_plate_detector" / "weights" / "best.pt"
    if not weights.exists():
        raise SystemExit(f"Egitilmis agirlik bulunamadi: {weights}")
    target = root / "models" / "license_plate_detector.pt"
    target.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    model.save(str(target))
    print(f"Model kaydedildi: {target}")


if __name__ == "__main__":
    main()
