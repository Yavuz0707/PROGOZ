from functools import lru_cache
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from app.config import get_settings


class PersonDetector:
    def __init__(self, model_name: str | None = None, confidence: float | None = None, input_size: int | None = None) -> None:
        self.settings = get_settings()
        self.model_name = model_name or self.settings.yolo_model
        self.confidence = confidence or self.settings.confidence_threshold
        self.input_size = input_size or self.settings.input_size
        self.device = "cpu"
        self.model = None
        self.available = False
        self.load_error: str | None = None
        self.last_inference_ms = 0.0
        self.load_time_ms = 0.0
        self.half_enabled = False
        self._load_model()

    def _load_model(self) -> None:
        try:
            import torch
            from ultralytics import YOLO

            start = perf_counter()
            self.device = 0 if torch.cuda.is_available() else "cpu"
            self.model = YOLO(self.model_name)
            self.load_time_ms = (perf_counter() - start) * 1000
            self.available = True
            self.half_enabled = self.device != "cpu"
            self.load_error = None
        except Exception as exc:
            self.model = None
            self.available = False
            self.load_error = f"{type(exc).__name__}: {exc}"

    @property
    def device_label(self) -> str:
        return "cuda:0" if self.device != "cpu" else "cpu"

    def detect_and_track(self, frame: np.ndarray, input_size: int | None = None) -> list[dict[str, Any]]:
        if not self.available or self.model is None:
            self.last_inference_ms = 0.0
            return []
        start = perf_counter()
        try:
            results = self._track(frame, input_size, self.half_enabled)
        except Exception:
            if not self.half_enabled:
                raise
            self.half_enabled = False
            results = self._track(frame, input_size, False)
        self.last_inference_ms = (perf_counter() - start) * 1000
        detections: list[dict[str, Any]] = []
        if not results:
            return detections
        boxes = results[0].boxes
        if boxes is None:
            return detections
        xyxy = boxes.xyxy.cpu().numpy() if boxes.xyxy is not None else []
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else [0.0] * len(xyxy)
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else list(range(1, len(xyxy) + 1))
        keypoints_xy = None
        keypoints_conf = None
        if getattr(results[0], "keypoints", None) is not None and results[0].keypoints is not None:
            keypoints_xy = results[0].keypoints.xy.cpu().numpy() if results[0].keypoints.xy is not None else None
            keypoints_conf = results[0].keypoints.conf.cpu().numpy() if results[0].keypoints.conf is not None else None
        for index, (box, conf, track_id) in enumerate(zip(xyxy, confs, ids)):
            detection = {"track_id": int(track_id), "bbox": [int(v) for v in box], "confidence": float(conf)}
            if keypoints_xy is not None and index < len(keypoints_xy):
                kpts = []
                for kp_index, point in enumerate(keypoints_xy[index]):
                    kp_conf = float(keypoints_conf[index][kp_index]) if keypoints_conf is not None else 1.0
                    kpts.append({"x": float(point[0]), "y": float(point[1]), "confidence": kp_conf})
                detection["keypoints"] = kpts
            detections.append(detection)
        return detections

    def _track(self, frame: np.ndarray, input_size: int | None, half: bool):
        return self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],
            conf=self.confidence,
            imgsz=input_size or self.input_size,
            device=self.device,
            half=half and self.device != "cpu",
            verbose=False,
        )

    def annotate(
        self,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        score: float,
        level: str,
        reasons: list[str] | None = None,
        involved_ids: set[int] | None = None,
    ) -> np.ndarray:
        annotated = frame.copy()
        color = (40, 220, 40) if level == "NORMAL" else (0, 215, 255) if level in {"SUPHELI", "OLASI_KAVGA"} else (0, 0, 255)
        neutral_color = (40, 220, 40)
        height, width = frame.shape[:2]
        scale_factor = max(0.75, min(1.35, height / 720.0))
        font_scale = self.settings.overlay_font_scale * scale_factor
        small_font_scale = self.settings.overlay_small_font_scale * scale_factor
        thickness = max(1, int(round(self.settings.overlay_font_thickness * scale_factor)))
        padding = max(4, int(round(self.settings.overlay_padding * scale_factor)))
        box_thickness = max(1, int(round(2 * scale_factor)))
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            track_id = int(det.get("track_id") or det.get("id") or -1)
            box_color = color
            if self.settings.only_highlight_involved_persons and level != "NORMAL" and involved_ids is not None and track_id not in involved_ids:
                box_color = neutral_color
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, box_thickness)
            label = f"ID {det.get('track_id')} {det.get('confidence', 0):.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, small_font_scale, thickness)
            label_y = max(label_size[1] + padding, y1 - padding)
            cv2.rectangle(annotated, (x1, label_y - label_size[1] - padding), (x1 + label_size[0] + padding, label_y + padding // 2), (15, 15, 20), -1)
            cv2.putText(annotated, label, (x1 + padding // 2, label_y), cv2.FONT_HERSHEY_SIMPLEX, small_font_scale, box_color, thickness)

        reason_text = ""
        if self.settings.debug_scoring and reasons:
            reason_text = " | " + ",".join(reasons[:2])
        text = f"{level} | {score:.1f}{reason_text}" if self.settings.overlay_compact_mode else f"PROGOZ | {level} | {score:.1f}{reason_text}"
        if not self.settings.overlay_compact_mode:
            text = f"PROGOZ | {level} | {score:.1f}"
        banner_h = max(28, int(height * self.settings.overlay_banner_height_ratio))
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        banner_w = min(width - 2 * padding, text_size[0] + padding * 3)
        cv2.rectangle(annotated, (padding, padding), (padding + banner_w, padding + banner_h), (15, 15, 20), -1)
        baseline_y = padding + (banner_h + text_size[1]) // 2 - 2
        cv2.putText(annotated, text, (padding * 2, baseline_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        return annotated


@lru_cache(maxsize=1)
def get_detector() -> PersonDetector:
    return PersonDetector()
