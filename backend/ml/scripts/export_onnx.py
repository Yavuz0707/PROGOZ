"""YOLOv8n-pose modelini ONNX formatina export eder (Web Yayini icin — Adim 1/N).

Sadece kisi tespiti/pose icin kullanilan yolov8n-pose modelini ONNX'e cevirir.
Fight classifier ve plaka detektoru bu adimda DAHIL DEGILDIR.

Cikti: backend/ml/models/pose/yolov8n-pose.onnx
(camera_stream.py icindeki WEB_STREAM_ONNX_POSE_PATH varsayilani ile ayni)

Kullanim:
    python ml/scripts/export_onnx.py

Not: ONNX export icin 'onnx' (+ simplify icin 'onnxslim') paketleri gerekir.
Ultralytics bunlari otomatik kurmayi deneyebilir; internet yoksa export
basarisiz olabilir — bu durumda hata mesaji raporlanir.
"""

import os
import shutil
from pathlib import Path

# torch CUDA build'i oldugundan ultralytics 'onnxruntime-gpu' kurmaya calisip takiliyor.
# CPU onnxruntime zaten yuklu; otomatik kurulumu kapatip onu kullanmasini sagliyoruz.
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

# backend/ kok dizini (script backend/ml/scripts/ altinda)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PT_MODEL = "yolov8n-pose.pt"
OUTPUT_DIR = BACKEND_ROOT / "ml" / "models" / "pose"
OUTPUT_PATH = OUTPUT_DIR / "yolov8n-pose.onnx"


def main() -> int:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # noqa: BLE001
        print(f"[HATA] ultralytics import edilemedi: {exc}")
        return 1

    # .pt zaten backend kokunde mevcutsa onu kullan, yoksa ultralytics indirir.
    pt_path = BACKEND_ROOT / PT_MODEL
    model_ref = str(pt_path) if pt_path.exists() else PT_MODEL
    print(f"[1/3] Model yukleniyor: {model_ref}")
    model = YOLO(model_ref)

    print("[2/3] ONNX export (imgsz=320, half=True, dynamic=False, simplify=True)...")
    try:
        exported = model.export(
            format="onnx",
            imgsz=320,
            half=True,
            dynamic=False,
            simplify=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[HATA] ONNX export basarisiz: {type(exc).__name__}: {exc}")
        print("       Olasi neden: 'onnx'/'onnxslim' paketi yok veya internet erisimi yok.")
        print("       Cozum: pip install onnx onnxslim onnxruntime")
        return 1

    # ultralytics export edilen dosyanin yolunu (str/Path) doner.
    exported_path = Path(str(exported))
    if not exported_path.exists():
        # Bazi surumler .pt yaninda olusturur; ad ile ara.
        candidate = pt_path.with_suffix(".onnx")
        exported_path = candidate if candidate.exists() else exported_path

    if not exported_path.exists():
        print(f"[HATA] Export edilen ONNX dosyasi bulunamadi (beklenen: {exported_path}).")
        return 1

    print(f"[3/3] Cikti tasiniyor -> {OUTPUT_PATH}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if exported_path.resolve() != OUTPUT_PATH.resolve():
        shutil.move(str(exported_path), str(OUTPUT_PATH))

    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print("\n=== BASARILI ===")
    print(f"ONNX modeli: {OUTPUT_PATH}  ({size_mb:.1f} MB)")
    print("Kullanmak icin .env: WEB_STREAM_USE_ONNX_POSE=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
