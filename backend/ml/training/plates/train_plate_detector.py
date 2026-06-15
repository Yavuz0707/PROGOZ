import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "ml" / "datasets" / "plates" / "yolo" / "data.yaml"
DEFAULT_TARGET = ROOT / "ml" / "models" / "plates" / "license_plate_detector.pt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLOv8 license plate detector training for PROGOZ.")
    parser.add_argument("--model", default="yolov8n.pt", help="Base YOLO model, e.g. yolov8n.pt or yolov8s.pt")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="YOLO data.yaml path")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--device", default="0", help="0 for CUDA GPU, cpu for CPU")
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--project", default=str(ROOT / "ml" / "runs" / "plates"))
    parser.add_argument("--name", default="plate_yolov8n")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Where best.pt should be copied")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_yaml = Path(args.data)
    if not data_yaml.exists():
        raise SystemExit(
            f"data.yaml bulunamadi: {data_yaml}\n"
            "Roboflow ile indirin veya YOLO datasetinizi backend/ml/datasets/plates/yolo klasorune koyun."
        )

    from ultralytics import YOLO

    model = YOLO(args.model)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=args.device,
        patience=args.patience,
        project=args.project,
        name=args.name,
    )
    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name))
    best = save_dir / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit(f"Egitim bitti ama best.pt bulunamadi: {best}")
    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, target)
    print(f"En iyi plaka modeli kopyalandi: {target}")


if __name__ == "__main__":
    main()
