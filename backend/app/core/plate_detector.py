from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path

import numpy as np

from app.config import BASE_DIR, get_settings

logger = logging.getLogger("progoz.plate_detector")


@dataclass(frozen=True)
class PlateDetection:
    bbox: tuple[int, int, int, int]
    confidence: float


class PlateDetector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        self.load_error: str | None = None
        self.device_label = "cpu"
        self.model_path: Path | None = None
        self.model_exists = False
        self._load()

    @property
    def available(self) -> bool:
        return self.model is not None

    def detect(self, frame: np.ndarray) -> list[PlateDetection]:
        if self.model is None or frame is None or frame.size == 0:
            return []
        try:
            results = self.model.predict(
                frame,
                imgsz=self.settings.plate_detector_imgsz,
                conf=self.settings.plate_detector_confidence,
                verbose=False,
                device=self.device_label,
            )
        except Exception as exc:
            self.load_error = str(exc)
            return []
        detections: list[PlateDetection] = []
        if not results:
            return detections
        height, width = frame.shape[:2]
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return detections
        for box in boxes:
            xyxy = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item()) if getattr(box, "conf", None) is not None else 0.0
            x1, y1, x2, y2 = [int(round(value)) for value in xyxy]
            x1 = max(0, min(x1, width - 1))
            x2 = max(0, min(x2, width))
            y1 = max(0, min(y1, height - 1))
            y2 = max(0, min(y2, height))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(PlateDetection(bbox=(x1, y1, x2, y2), confidence=confidence))
        return detections

    def _load(self) -> None:
        model_path = Path(self.settings.plate_detector_model_path)
        if not model_path.is_absolute():
            model_path = BASE_DIR / model_path
        self.model_path = model_path
        self.model_exists = model_path.exists()
        logger.warning(
            "Plate detector config: enabled=%s path=%s exists=%s",
            self.settings.plate_recognition_enabled,
            model_path,
            self.model_exists,
        )
        if not model_path.exists():
            self.load_error = f"Plaka modeli bulunamadi: {model_path}"
            logger.warning(self.load_error)
            return
        try:
            import torch
            from ultralytics import YOLO

            self.device_label = "cuda:0" if torch.cuda.is_available() else "cpu"
            self.model = YOLO(str(model_path))
            logger.warning(
                "Plate detector loaded: loaded=%s device=%s model=%s",
                self.available,
                self.device_label,
                model_path,
            )
        except Exception as exc:
            self.load_error = str(exc)
            self.model = None
            logger.warning("Plate detector yuklenemedi: %s", exc)


@lru_cache(maxsize=1)
def get_plate_detector() -> PlateDetector:
    return PlateDetector()
