from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    root = Path(__file__).resolve().parent
    dataset_yaml = root / "datasets" / "plate_dataset.yaml"
    if not dataset_yaml.exists():
        raise SystemExit(f"Dataset YAML bulunamadi: {dataset_yaml}")
    model = YOLO("yolov8n.pt")
    model.train(data=str(dataset_yaml), epochs=80, imgsz=640, project=str(root / "runs"), name="license_plate_detector")


if __name__ == "__main__":
    main()
