import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained YOLO plate detector.")
    parser.add_argument("--model", default=str(ROOT / "ml" / "models" / "plates" / "license_plate_detector.pt"))
    parser.add_argument("--data", default=str(ROOT / "ml" / "datasets" / "plates" / "yolo" / "data.yaml"))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()

    model_path = Path(args.model)
    data_yaml = Path(args.data)
    if not model_path.exists():
        raise SystemExit(f"Model bulunamadi: {model_path}")
    if not data_yaml.exists():
        raise SystemExit(f"data.yaml bulunamadi: {data_yaml}")

    from ultralytics import YOLO

    metrics = YOLO(str(model_path)).val(data=str(data_yaml), imgsz=args.imgsz, batch=args.batch, device=args.device)
    print(metrics)


if __name__ == "__main__":
    main()
