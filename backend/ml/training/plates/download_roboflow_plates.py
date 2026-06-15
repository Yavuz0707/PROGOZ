import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def main() -> None:
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    workspace = os.getenv("ROBOFLOW_WORKSPACE", "plakatanima-vnt3k").strip()
    project = os.getenv("ROBOFLOW_PROJECT", "turkish-number-plates").strip()
    version = int(os.getenv("ROBOFLOW_VERSION", "1"))
    export_format = os.getenv("ROBOFLOW_FORMAT", "yolov8").strip()
    target = ROOT / "ml" / "datasets" / "plates" / "yolo"
    target.mkdir(parents=True, exist_ok=True)

    if not api_key:
        raise SystemExit(
            "Roboflow API key bulunamadi. backend/.env icine ROBOFLOW_API_KEY ekleyin "
            "veya dataset'i manuel indirip backend/ml/datasets/plates/yolo klasorune koyun."
        )

    try:
        from roboflow import Roboflow
    except Exception as exc:
        raise SystemExit(f"roboflow paketi yuklu degil: {exc}. `pip install roboflow` calistirin.") from exc

    print(f"Roboflow dataset indiriliyor: {workspace}/{project} v{version} format={export_format}")
    rf = Roboflow(api_key=api_key)
    dataset = rf.workspace(workspace).project(project).version(version).download(export_format, location=str(target))
    print(f"Dataset hazir: {dataset.location}")
    print("data.yaml yolu genellikle bu klasor altindadir. Egitim icin:")
    print("python ml/training/plates/train_plate_detector.py --data ml/datasets/plates/yolo/data.yaml")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Roboflow indirme hatasi: {exc}", file=sys.stderr)
        raise SystemExit(1)
