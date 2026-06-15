import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional Kaggle downloader for fight/violence datasets.")
    parser.add_argument("--slug", default=os.getenv("KAGGLE_FIGHT_DATASET_SLUG", ""))
    parser.add_argument("--out", default="ml/datasets/fight/raw_downloads")
    parser.add_argument("--unzip", action="store_true")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    username = os.getenv("KAGGLE_USERNAME", "").strip()
    key = os.getenv("KAGGLE_KEY", "").strip()
    slug = (args.slug or os.getenv("KAGGLE_FIGHT_DATASET_SLUG", "")).strip()
    if not username or not key:
        raise SystemExit(
            "Kaggle credential bulunamadi. .env icine KAGGLE_USERNAME ve KAGGLE_KEY ekleyin "
            "veya dataset'i manuel indirip backend/ml/datasets/fight/raw altina yerlestirin."
        )
    if not slug:
        raise SystemExit(
            "Kaggle dataset slug verilmedi. Ornek: --slug <owner/dataset-name>. "
            "Real Life Violence veya Hockey Fight sayfasindaki Kaggle slug degerini kullanin."
        )
    target = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    target.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "kaggle", "datasets", "download", "-d", slug, "-p", str(target)]
    if args.unzip:
        command.append("--unzip")
    print("Kaggle download:", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("kaggle paketi bulunamadi. `pip install kaggle` calistirin veya manuel indirme kullanin.") from exc
    print(f"Dataset indirildi: {target}")
    print("Indirilen dosyalari raw/violence ve raw/non_violence yapisina manuel ayirin, sonra prepare scriptini calistirin.")


if __name__ == "__main__":
    main()
