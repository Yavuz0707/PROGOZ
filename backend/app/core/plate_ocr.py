import logging
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Sequence

import cv2
import numpy as np

from app.config import get_settings

logger = logging.getLogger("progoz.plate_ocr")


TR_PLATE_RE = re.compile(r"^(0[1-9]|[1-7][0-9]|8[01]) [A-Z]{1,3} [0-9]{2,4}$")
DIGIT_FIXES = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "G": "6", "Z": "2"})
LETTER_FIXES = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"})


@dataclass(frozen=True)
class PlateText:
    raw_text: str
    normalized_plate: str
    is_valid_format: bool
    status: str


@dataclass(frozen=True)
class OcrResult:
    text: PlateText
    confidence: float
    variant_name: str = "original"
    candidate_score: float = 0.0
    candidate_score_breakdown: dict[str, float] = field(default_factory=dict)
    selected: bool = False
    rejection_reason: str | None = None


def normalize_turkish_plate(raw_text: str) -> PlateText:
    ranked = rank_ocr_candidates(extract_ocr_candidates(raw_text, confidence=0.0, variant_name="normalizer"))
    if ranked:
        return ranked[0].text
    compact = re.sub(r"[^A-Z0-9]", "", (raw_text or "").strip().upper())
    if compact:
        return PlateText(raw_text=raw_text, normalized_plate=compact, is_valid_format=False, status="uncertain")
    return PlateText(raw_text=raw_text, normalized_plate="", is_valid_format=False, status="ignored")


def extract_ocr_candidates(raw_text: str, confidence: float, variant_name: str) -> list[OcrResult]:
    raw = (raw_text or "").strip().upper()
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if not compact:
        return []
    found: dict[str, OcrResult] = {}
    max_size = min(9, len(compact))
    for start in range(0, len(compact)):
        for letter_count in range(1, 4):
            for digit_count in range(2, 5):
                size = 2 + letter_count + digit_count
                if size > max_size or start + size > len(compact):
                    continue
                segment = compact[start : start + size]
                city = segment[:2].translate(DIGIT_FIXES)
                letters = segment[2 : 2 + letter_count].translate(LETTER_FIXES)
                numbers = segment[2 + letter_count :].translate(DIGIT_FIXES)
                normalized = f"{city} {letters} {numbers}"
                if not TR_PLATE_RE.match(normalized):
                    continue
                if normalized not in found or confidence > found[normalized].confidence:
                    found[normalized] = OcrResult(
                        text=PlateText(raw_text=raw_text, normalized_plate=normalized, is_valid_format=True, status="valid"),
                        confidence=confidence,
                        variant_name=variant_name,
                    )
    return list(found.values())


def rank_ocr_candidates(candidates: list[OcrResult]) -> list[OcrResult]:
    if not candidates:
        return []
    counts = Counter(candidate.text.normalized_plate for candidate in candidates if candidate.text.normalized_plate)
    max_compact_len = max(len(_compact_plate(candidate.text.normalized_plate)) for candidate in candidates)
    rescored: list[OcrResult] = []
    for candidate in candidates:
        score, breakdown = _score_candidate(candidate, counts[candidate.text.normalized_plate], max_compact_len)
        rescored.append(replace(candidate, candidate_score=score, candidate_score_breakdown=breakdown))
    rescored.sort(key=lambda item: (item.candidate_score, item.text.is_valid_format, item.confidence), reverse=True)
    if not rescored:
        return []
    selected_plate = rescored[0].text.normalized_plate
    selected: list[OcrResult] = []
    for index, candidate in enumerate(rescored):
        if index == 0:
            selected.append(replace(candidate, selected=True, rejection_reason=None))
        else:
            reason = "lower_candidate_score"
            if candidate.text.normalized_plate == selected_plate:
                reason = "same_plate_lower_variant"
            elif len(_compact_plate(candidate.text.normalized_plate)) < max_compact_len:
                reason = "less_complete_candidate"
            selected.append(replace(candidate, selected=False, rejection_reason=reason))
    return selected


def _score_candidate(candidate: OcrResult, repeat_count: int, max_compact_len: int) -> tuple[float, dict[str, float]]:
    normalized = candidate.text.normalized_plate
    compact_plate = _compact_plate(normalized)
    match = TR_PLATE_RE.match(normalized)
    if not match:
        return 0.0, {"valid_format": 0.0}
    parts = normalized.split()
    letters = parts[1]
    digits = parts[2]
    raw_compact = re.sub(r"[^A-Z0-9]", "", (candidate.text.raw_text or "").upper())
    exact_compact_in_raw = 1.0 if compact_plate in raw_compact else 0.0
    letter_points = {1: 5.0, 2: 15.0, 3: 12.0}.get(len(letters), 0.0)
    digit_points = {2: 5.0, 3: 12.0, 4: 18.0}.get(len(digits), 0.0)
    confidence_points = min(20.0, max(0.0, candidate.confidence) * 20.0)
    repeat_points = min(15.0, max(0, repeat_count - 1) * 7.5)
    length_points = len(compact_plate) * 3.0
    breakdown = {
        "valid_province": 20.0,
        "letter_group": letter_points,
        "digit_group": digit_points,
        "normalized_length": length_points,
        "repeated_across_variants": repeat_points,
        "exact_compact_in_raw": 20.0 if exact_compact_in_raw else 0.0,
        "ocr_confidence": confidence_points,
        "incomplete_short_candidate_penalty": 0.0,
        "ambiguous_letter_digit_boundary_penalty": 0.0,
        "info_loss_penalty": 0.0,
    }
    if len(letters) == 1 and len(digits) == 2:
        breakdown["incomplete_short_candidate_penalty"] = -18.0
    if len(letters) == 3 and len(digits) == 2 and letters[-1] in {"O", "I", "S", "B", "G", "Z"}:
        breakdown["ambiguous_letter_digit_boundary_penalty"] = -24.0
    if len(compact_plate) + 2 <= max_compact_len:
        breakdown["info_loss_penalty"] = -25.0
    if not exact_compact_in_raw:
        breakdown["info_loss_penalty"] += -10.0
    score = sum(breakdown.values())
    return score, breakdown


def _compact_plate(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


class PlateOCR:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = self.settings.plate_ocr_engine
        self.reader = None
        self.paddle_reader = None
        self.load_error: str | None = None
        self._load_easyocr()
        self._load_paddleocr()

    def _load_paddleocr(self) -> None:
        try:
            from paddleocr import PaddleOCR
            import torch
            use_gpu = bool(torch.cuda.is_available())
            self.paddle_reader = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                use_gpu=use_gpu,
                show_log=False,
            )
            logger.info("PaddleOCR basariyla yuklendi (gpu=%s)", use_gpu)
        except Exception as exc:
            logger.debug("PaddleOCR yuklenemedi (fallback EasyOCR): %s", exc)
            self.paddle_reader = None

    @property
    def available(self) -> bool:
        return self.reader is not None or self.paddle_reader is not None

    def read(self, crop: np.ndarray) -> OcrResult | None:
        candidates = self.read_all(crop)
        best: OcrResult | None = None
        for candidate in candidates:
            if not candidate.text.normalized_plate:
                continue
            if best is None or self._rank(candidate) > self._rank(best):
                best = candidate
        return best

    def read_all(self, crop: np.ndarray) -> list[OcrResult]:
        if crop is None or crop.size == 0:
            return []
        candidates: list[OcrResult] = []

        # EasyOCR over preprocessed variants
        if self.reader:
            for variant_name, image in self.preprocess_variants(crop):
                try:
                    results = self.reader.readtext(image, paragraph=False)
                    text, confidence = self._best_text(results)
                    candidates.extend(extract_ocr_candidates(text, confidence=confidence, variant_name=variant_name))
                except Exception as exc:
                    self.load_error = str(exc)

        # PaddleOCR on original + 2× resize (additional candidates)
        if self.paddle_reader:
            candidates.extend(self._paddle_read_all(crop))

        return rank_ocr_candidates(candidates)

    def _paddle_read_all(self, crop: np.ndarray) -> list[OcrResult]:
        candidates: list[OcrResult] = []
        variants = [("paddle_original", crop)]
        h, w = crop.shape[:2]
        if max(h, w) < 300:
            variants.append(("paddle_2x", cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)))
        for variant_name, image in variants:
            try:
                result = self.paddle_reader.ocr(image, cls=True)
                if not result or not result[0]:
                    continue
                texts: list[str] = []
                confs: list[float] = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_conf = line[1]
                        if text_conf and len(text_conf) >= 2:
                            texts.append(str(text_conf[0]).strip())
                            confs.append(float(text_conf[1] or 0.0))
                text = " ".join(t for t in texts if t)
                confidence = max(confs) if confs else 0.0
                if text:
                    candidates.extend(extract_ocr_candidates(text, confidence=confidence, variant_name=variant_name))
            except Exception as exc:
                logger.debug("PaddleOCR varyant %s hatasi: %s", variant_name, exc)
        return candidates

    def preprocess_variants(self, crop: np.ndarray) -> list[tuple[str, np.ndarray]]:
        if crop is None or crop.size == 0:
            return []
        variants: list[tuple[str, np.ndarray]] = [("original", crop)]
        height, width = crop.shape[:2]
        resized_2x = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        resized_3x = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        variants.extend([("resized_2x", resized_2x), ("resized_3x", resized_3x)])
        base = resized_3x
        if max(height, width) < 180:
            resized_4x = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            variants.append(("resized_4x", resized_4x))
            base = resized_4x
        gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY) if base.ndim == 3 else base.copy()
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
        denoised = cv2.bilateralFilter(clahe, 7, 50, 50)
        sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(denoised, -1, sharpen_kernel)
        adaptive_thresholded = cv2.adaptiveThreshold(
            sharpened,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )
        _, otsu_thresholded = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bilateral_sharpened = cv2.filter2D(cv2.bilateralFilter(gray, 9, 75, 75), -1, sharpen_kernel)
        contrast_bgr = cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR)
        sharpened_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)
        adaptive_bgr = cv2.cvtColor(adaptive_thresholded, cv2.COLOR_GRAY2BGR)
        otsu_bgr = cv2.cvtColor(otsu_thresholded, cv2.COLOR_GRAY2BGR)
        bilateral_bgr = cv2.cvtColor(bilateral_sharpened, cv2.COLOR_GRAY2BGR)
        variants.extend(
            [
                ("grayscale_resized", cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)),
                ("contrast_enhanced", contrast_bgr),
                ("sharpened", sharpened_bgr),
                ("adaptive_threshold", adaptive_bgr),
                ("otsu_threshold", otsu_bgr),
                ("bilateral_sharpened", bilateral_bgr),
                ("clahe", contrast_bgr),
            ]
        )
        return variants

    def _load_easyocr(self) -> None:
        try:
            import easyocr
            import torch

            gpu = bool(torch.cuda.is_available())
            self.reader = easyocr.Reader(self.settings.plate_ocr_languages, gpu=gpu, verbose=False)
        except Exception as exc:
            self.load_error = str(exc)
            self.reader = None
            logger.debug("EasyOCR yuklenemedi: %s", exc)

    def _best_text(self, results: Sequence) -> tuple[str, float]:
        if not results:
            return "", 0.0
        parts: list[str] = []
        confidences: list[float] = []
        for item in results:
            if len(item) < 3:
                continue
            text = str(item[1]).strip()
            if not text:
                continue
            parts.append(text)
            confidences.append(float(item[2] or 0.0))
        if not parts:
            return "", 0.0
        return " ".join(parts), max(confidences)

    def _rank(self, result: OcrResult) -> tuple[int, float, int]:
        return (
            1 if result.text.is_valid_format else 0,
            result.candidate_score,
            float(result.confidence),
            len(result.text.normalized_plate or ""),
        )


@lru_cache(maxsize=1)
def get_plate_ocr() -> PlateOCR:
    return PlateOCR()
