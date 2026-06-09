from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.plate_detector import PlateDetection, get_plate_detector
from app.core.plate_ocr import OcrResult, get_plate_ocr
from app.models.license_plate import LicensePlate
from app.services.plate_service import upsert_plate_detection
from app.utils.file_utils import public_static_path

logger = logging.getLogger("progoz.plate_pipeline")


@dataclass(frozen=True)
class PlatePipelineResult:
    record: LicensePlate
    created: bool


class PlateRecognitionPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.detector = get_plate_detector()
        self.ocr = get_plate_ocr() if self.detector.available else None
        self.stats = self._empty_stats()
        logger.warning(
            "Plate pipeline ready: enabled=%s detector_loaded=%s ocr_loaded=%s model=%s device=%s error=%s",
            self.settings.plate_recognition_enabled,
            self.detector.available,
            bool(self.ocr and self.ocr.available),
            self.detector.model_path,
            self.detector.device_label,
            self.detector.load_error or (self.ocr.load_error if self.ocr else None),
        )

    @property
    def available(self) -> bool:
        return self.detector.available and self.ocr is not None and self.ocr.available

    def reset_stats(self) -> None:
        self.stats = self._empty_stats()

    def process_frame(
        self,
        db: Session,
        frame: np.ndarray,
        *,
        source_type: str,
        frame_index: int,
        camera_id: int | None = None,
        camera_name: str | None = None,
        analysis_job_id: int | None = None,
        video_filename: str | None = None,
        time_seconds: float | None = None,
        seen_at: datetime | None = None,
    ) -> list[PlatePipelineResult]:
        self.stats["sampled_frames"] += 1
        if not self.settings.plate_recognition_enabled or not self.detector.available:
            return []
        results: list[PlatePipelineResult] = []
        self.stats["detector_called"] += 1
        for detection in self.detector.detect(frame):
            if detection.confidence < self.settings.plate_detector_confidence:
                continue
            self.stats["detections"] += 1
            crop = self._crop(frame, detection)
            self.stats["ocr_attempted"] += 1
            ocr_candidates = self.ocr.read_all(crop) if self.ocr and self.ocr.available else []
            self.stats["ocr_raw_text_count"] += len(ocr_candidates)
            self.stats["normalized_candidate_count"] += sum(1 for item in ocr_candidates if item.text.normalized_plate)
            ocr_result = ocr_candidates[0] if ocr_candidates else None
            if not ocr_result:
                self.stats["unreadable_plate_count"] += 1
                self.stats["skipped_unreadable_count"] += 1
                if self.settings.plate_debug_enabled:
                    self._save_debug_images(frame, crop, source_type, camera_id, analysis_job_id, frame_index)
                if not self.settings.plate_save_unreadable:
                    continue
                continue
            if not self._should_save_ocr_result(ocr_result):
                self.stats["skipped_unreadable_count"] += 1
                continue
            snapshot_path = self._save_image(frame, "snapshot", source_type, camera_id, analysis_job_id, frame_index)
            crop_path = self._save_image(crop, "crop", source_type, camera_id, analysis_job_id, frame_index)
            debug_paths = self._save_debug_images(frame, crop, source_type, camera_id, analysis_job_id, frame_index) if self.settings.plate_debug_enabled else []
            confidence = min(detection.confidence, ocr_result.confidence) if ocr_result.confidence > 0 else detection.confidence
            record, created = upsert_plate_detection(
                db,
                source_type=source_type,
                camera_id=camera_id,
                analysis_job_id=analysis_job_id,
                video_filename=video_filename,
                plate_text_raw=ocr_result.text.raw_text,
                plate_text_normalized=ocr_result.text.normalized_plate,
                is_valid_format=ocr_result.text.is_valid_format,
                confidence=confidence,
                ocr_confidence=ocr_result.confidence,
                detection_confidence=detection.confidence,
                bbox=detection.bbox,
                snapshot_path=snapshot_path,
                crop_path=crop_path,
                time_seconds=time_seconds,
                seen_at=seen_at,
                frame_index=frame_index,
                recognition_source="local_detector_easyocr",
                details={
                    "ocr_variant": ocr_result.variant_name,
                    "debug_paths": debug_paths,
                    "ocr_candidates": [self._ocr_result_payload(candidate) for candidate in ocr_candidates[:12]],
                },
            )
            if ocr_result.text.is_valid_format:
                self.stats["readable_plate_count"] += 1
            self.stats["plates_saved"] += 1
            results.append(PlatePipelineResult(record=record, created=created))
        return results

    def analyze_image_for_debug(self, frame: np.ndarray) -> dict:
        data = {
            "plate_recognition_enabled": self.settings.plate_recognition_enabled,
            "detector_loaded": self.detector.available,
            "detector_error": self.detector.load_error,
            "ocr_loaded": bool(self.ocr and self.ocr.available),
            "ocr_error": self.ocr.load_error if self.ocr else None,
            "model_path": str(self.detector.model_path) if self.detector.model_path else None,
            "model_file_exists": self.detector.model_exists,
            "device": self.detector.device_label,
            "detections": [],
            "final_plate": None,
            "original_frame_url": None,
        }
        if frame is None or frame.size == 0 or not self.detector.available:
            return data
        original_path = self._save_debug_image(frame, "test_original_frame.jpg")
        data["original_frame_url"] = public_static_path(original_path)
        detections = self.detector.detect(frame)
        best_plate: tuple[str, bool, float] | None = None
        for index, detection in enumerate(detections):
            crop = self._crop(frame, detection)
            ocr_candidates = self.ocr.read_all(crop) if self.ocr and self.ocr.available else []
            ocr_result = ocr_candidates[0] if ocr_candidates else None
            crop_path = self._save_debug_image(crop, f"test_detection_{index}_crop.jpg")
            preprocess_urls = []
            if self.ocr:
                for variant_index, (name, variant) in enumerate(self.ocr.preprocess_variants(crop)):
                    path = self._save_debug_image(variant, f"test_detection_{index}_{variant_index}_{name}.jpg")
                    if path:
                        preprocess_urls.append({"name": name, "url": public_static_path(path)})
            item = {
                "bbox": list(detection.bbox),
                "detection_confidence": detection.confidence,
                "confidence": detection.confidence,
                "ocr_results": [self._ocr_result_payload(candidate) for candidate in ocr_candidates],
                "ocr_raw": ocr_result.text.raw_text if ocr_result else "",
                "ocr_confidence": ocr_result.confidence if ocr_result else 0.0,
                "ocr_variant": ocr_result.variant_name if ocr_result else None,
                "normalized_plate": ocr_result.text.normalized_plate if ocr_result else "",
                "final_normalized_plate": ocr_result.text.normalized_plate if ocr_result else None,
                "valid": bool(ocr_result and ocr_result.text.is_valid_format),
                "status": ocr_result.text.status if ocr_result else "unreadable",
                "crop_url": public_static_path(crop_path),
                "preprocess_variants": preprocess_urls,
                "debug_preprocess_urls": preprocess_urls,
                "debug_preprocess_url": preprocess_urls[0]["url"] if preprocess_urls else None,
            }
            data["detections"].append(item)
            if ocr_result and ocr_result.text.normalized_plate and (
                best_plate is None
                or (ocr_result.text.is_valid_format, ocr_result.candidate_score) > (best_plate[1], best_plate[2])
            ):
                best_plate = (ocr_result.text.normalized_plate, ocr_result.text.is_valid_format, ocr_result.candidate_score)
        data["final_plate"] = best_plate[0] if best_plate else None
        return data

    def _crop(self, frame: np.ndarray, detection: PlateDetection) -> np.ndarray:
        x1, y1, x2, y2 = detection.bbox
        pad_x = max(2, int((x2 - x1) * 0.08))
        pad_y = max(2, int((y2 - y1) * 0.18))
        height, width = frame.shape[:2]
        x1 = max(0, x1 - pad_x)
        x2 = min(width, x2 + pad_x)
        y1 = max(0, y1 - pad_y)
        y2 = min(height, y2 + pad_y)
        return frame[y1:y2, x1:x2].copy()

    def _save_image(
        self,
        image: np.ndarray,
        kind: str,
        source_type: str,
        camera_id: int | None,
        analysis_job_id: int | None,
        frame_index: int,
    ) -> str | None:
        if image is None or image.size == 0:
            return None
        if kind == "snapshot":
            if not self.settings.plate_save_snapshots:
                return None
            directory = self.settings.plate_snapshot_dir
        else:
            if not self.settings.plate_save_crops:
                return None
            directory = self.settings.plate_crop_dir
        directory.mkdir(parents=True, exist_ok=True)
        source_id = analysis_job_id if source_type == "video" else camera_id
        filename = f"{source_type}_{source_id or 'unknown'}_frame_{frame_index}_{kind}.jpg"
        path = directory / filename
        counter = 1
        while path.exists():
            path = directory / f"{Path(filename).stem}_{counter}.jpg"
            counter += 1
        if cv2.imwrite(str(path), image):
            return str(path)
        return None

    def _save_debug_images(
        self,
        frame: np.ndarray,
        crop: np.ndarray,
        source_type: str,
        camera_id: int | None,
        analysis_job_id: int | None,
        frame_index: int,
    ) -> list[str]:
        saved: list[str] = []
        if not self.ocr:
            return saved
        source_id = analysis_job_id if source_type == "video" else camera_id
        frame_path = self._save_debug_image(frame, f"frame_{source_id or 'unknown'}_{frame_index}.jpg")
        if frame_path:
            saved.append(frame_path)
        crop_path = self._save_debug_image(crop, f"crop_original_{source_id or 'unknown'}_{frame_index}.jpg")
        if crop_path:
            saved.append(crop_path)
        for _, (name, image) in enumerate(self.ocr.preprocess_variants(crop)):
            path = self._save_debug_image(image, f"crop_{name}_{source_id or 'unknown'}_{frame_index}.jpg")
            if path:
                saved.append(path)
        return saved

    def _save_debug_image(self, image: np.ndarray, filename: str) -> str | None:
        if image is None or image.size == 0:
            return None
        self.settings.plate_debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.plate_debug_dir / filename
        counter = 1
        while path.exists():
            path = self.settings.plate_debug_dir / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
            counter += 1
        if cv2.imwrite(str(path), image):
            return str(path)
        return None

    def _should_save_ocr_result(self, result: OcrResult) -> bool:
        normalized = (result.text.normalized_plate or "").strip()
        raw = (result.text.raw_text or "").strip()
        meaningful_length = max(len(normalized.replace(" ", "")), len(raw.replace(" ", "")))
        if result.text.is_valid_format:
            return True
        if meaningful_length < self.settings.plate_min_text_length_to_save:
            return False
        if result.confidence < self.settings.plate_ocr_min_confidence and not self.settings.plate_save_uncertain:
            return False
        return self.settings.plate_save_uncertain

    def _ocr_result_payload(self, result: OcrResult) -> dict:
        return {
            "variant": result.variant_name,
            "raw_text": result.text.raw_text,
            "ocr_confidence": result.confidence,
            "normalized_candidate": result.text.normalized_plate,
            "valid": result.text.is_valid_format,
            "status": result.text.status,
            "candidate_score": result.candidate_score,
            "candidate_score_breakdown": result.candidate_score_breakdown,
            "selected": result.selected,
            "rejection_reason": result.rejection_reason,
        }

    def _empty_stats(self) -> dict[str, int]:
        return {
            "sampled_frames": 0,
            "detector_called": 0,
            "detections": 0,
            "ocr_attempted": 0,
            "ocr_raw_text_count": 0,
            "normalized_candidate_count": 0,
            "readable_plate_count": 0,
            "unreadable_plate_count": 0,
            "plates_saved": 0,
            "skipped_unreadable_count": 0,
        }


def get_plate_pipeline() -> PlateRecognitionPipeline:
    return PlateRecognitionPipeline()
