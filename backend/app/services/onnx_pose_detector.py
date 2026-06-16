"""Direkt ONNX Runtime ile YOLOv8-pose kisi tespiti (Web Yayini icin — Adim 2/N).

Ultralytics YOLO wrapper'inin preprocessing/postprocessing overhead'ini atlayarak
onnxruntime.InferenceSession ile dogrudan inference yapar. SADECE web yayini
(source_type == "web") akisinda kullanilir; webcam/RTSP/video analizi paylasilan
PyTorch detektorunu kullanmaya devam eder.

Cikti (Ultralytics Results'a benzer dict):
    {
        "boxes": [[x1, y1, x2, y2, conf, cls], ...],     # orijinal frame olceginde
        "keypoints": [[[x, y, conf], ... 17], ...],       # orijinal frame olceginde
        "track_ids": [],                                  # ByteTrack sonradan doldurur
    }

ByteTrack entegrasyonu camera_stream.py icinde yapilir; bu modul tracker'a dokunmaz.
"""

from __future__ import annotations

import logging
import os
from time import perf_counter

import cv2
import numpy as np

logger = logging.getLogger("progoz.onnx_pose")


# ── cuDNN/CUDA DLL'leri icin torch lib dizinini PATH'e ekle ───────────────────────────
# onnxruntime CUDAExecutionProvider, cuDNN DLL'lerini bulamazsa sessizce CPU'ya duser.
# torch zaten CUDA build oldugundan gerekli DLL'ler torch/lib altinda bulunur.
def _ensure_cuda_dll_path() -> None:
    try:
        import torch

        cudnn_path = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(cudnn_path) and cudnn_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = cudnn_path + os.pathsep + os.environ.get("PATH", "")
    except Exception as exc:  # noqa: BLE001
        logger.debug("torch lib PATH eklenemedi (CUDA DLL): %s", exc)


_ensure_cuda_dll_path()


class OnnxPoseDetector:
    """YOLOv8-pose ONNX modelini dogrudan onnxruntime ile calistirir."""

    def __init__(
        self,
        model_path: str,
        providers: list[str] | None = None,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 320,
    ) -> None:
        self.model_path = model_path
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.available = False
        self.load_error: str | None = None
        self.last_inference_ms = 0.0
        self.session = None
        self._input_name: str | None = None
        self._output_name: str | None = None
        self._providers_active: list[str] = []
        # Son frame'in letterbox parametreleri: (gain, pad_x, pad_y)
        self._lb: tuple[float, float, float] = (1.0, 0.0, 0.0)
        self._load(providers)

    def _load(self, providers: list[str] | None) -> None:
        if not os.path.exists(self.model_path):
            self.load_error = f"ONNX model bulunamadi: {self.model_path}"
            return
        try:
            import onnxruntime as ort

            requested = providers or ["CUDAExecutionProvider", "CPUExecutionProvider"]
            available = set(ort.get_available_providers())
            use = [p for p in requested if p in available] or ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(self.model_path, providers=use)
            self._providers_active = list(self.session.get_providers())
            self._input_name = self.session.get_inputs()[0].name
            self._output_name = self.session.get_outputs()[0].name
            self.available = True
            self.load_error = None
            logger.warning(
                "OnnxPoseDetector hazir: %s | providers=%s",
                self.model_path, self._providers_active,
            )
        except Exception as exc:  # noqa: BLE001
            self.session = None
            self.available = False
            self.load_error = f"{type(exc).__name__}: {exc}"

    @property
    def device_label(self) -> str:
        return "cuda:0" if self._providers_active and "CUDAExecutionProvider" in self._providers_active[0] else "cpu"

    # ── Pipeline ──────────────────────────────────────────────────────────────────────
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """BGR frame -> (1, 3, imgsz, imgsz) float32 RGB, /255 normalize, HWC->CHW.

        Ultralytics ile ayni 'letterbox' (en-boy oranini koruyan, 114 ile dolgulu)
        on-isleme kullanilir — plain resize tespit dogrulugunu ciddi dusuruyor.
        Olcek/dolgu degerleri postprocess'te kutu/keypoint'leri orijinal olcege
        geri tasimak icin saklanir.
        """
        h, w = frame.shape[:2]
        gain = min(self.imgsz / float(h), self.imgsz / float(w))
        nw, nh = int(round(w * gain)), int(round(h * gain))
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        pad_x = (self.imgsz - nw) // 2
        pad_y = (self.imgsz - nh) // 2
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
        self._lb = (gain, float(pad_x), float(pad_y))
        # YOLO RGB ile egitildi; renk dogrulugu icin BGR->RGB.
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))  # HWC -> CHW
        return np.ascontiguousarray(blob[None, ...])  # (1,3,H,W)

    def run(self, frame: np.ndarray) -> np.ndarray:
        blob = self.preprocess(frame)
        outputs = self.session.run([self._output_name], {self._input_name: blob})
        return outputs[0]

    def postprocess(self, output: np.ndarray, orig_shape: tuple[int, int], conf: float | None = None) -> dict:
        """YOLOv8-pose ciktisini (1,56,2100) parse et, NMS uygula, orijinal olcege scale et."""
        conf_thr = self.conf if conf is None else conf
        orig_h, orig_w = orig_shape
        empty = {"boxes": [], "keypoints": [], "track_ids": []}

        preds = np.squeeze(output, axis=0)  # (56, 2100)
        if preds.ndim != 2:
            return empty
        preds = preds.transpose(1, 0)  # (2100, 56)

        scores = preds[:, 4]
        mask = scores >= conf_thr
        preds = preds[mask]
        if preds.shape[0] == 0:
            return empty
        scores = preds[:, 4]

        # Box: cx,cy,w,h (model girisi olceginde, 0..imgsz) -> xyxy (girdi olceginde)
        cx, cy, w, h = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
        x1 = cx - w / 2.0
        y1 = cy - h / 2.0
        x2 = cx + w / 2.0
        y2 = cy + h / 2.0
        boxes_in = np.stack([x1, y1, x2, y2], axis=1)

        keep = self._nms(boxes_in, scores, self.iou)
        if not keep:
            return empty

        # Letterbox'i geri al: model-uzayi (0..imgsz) -> orijinal frame olcegi.
        gain, pad_x, pad_y = self._lb
        inv_gain = 1.0 / gain if gain > 0 else 1.0

        kpts_raw = preds[:, 5:].reshape(preds.shape[0], -1, 3)  # (N, 17, 3)

        boxes_out: list[list[float]] = []
        kpts_out: list[list[list[float]]] = []
        for i in keep:
            bx1 = float(np.clip((boxes_in[i, 0] - pad_x) * inv_gain, 0, orig_w))
            by1 = float(np.clip((boxes_in[i, 1] - pad_y) * inv_gain, 0, orig_h))
            bx2 = float(np.clip((boxes_in[i, 2] - pad_x) * inv_gain, 0, orig_w))
            by2 = float(np.clip((boxes_in[i, 3] - pad_y) * inv_gain, 0, orig_h))
            boxes_out.append([bx1, by1, bx2, by2, float(scores[i]), 0.0])
            kp = kpts_raw[i].copy()
            kp[:, 0] = (kp[:, 0] - pad_x) * inv_gain
            kp[:, 1] = (kp[:, 1] - pad_y) * inv_gain
            kpts_out.append(kp.tolist())

        return {"boxes": boxes_out, "keypoints": kpts_out, "track_ids": []}

    def detect(self, frame: np.ndarray, conf: float | None = None) -> dict:
        if not self.available or self.session is None or frame is None or frame.size == 0:
            self.last_inference_ms = 0.0
            return {"boxes": [], "keypoints": [], "track_ids": []}
        start = perf_counter()
        output = self.run(frame)
        result = self.postprocess(output, frame.shape[:2], conf)
        self.last_inference_ms = (perf_counter() - start) * 1000.0
        return result

    @staticmethod
    def _nms(boxes_xyxy: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
        """Basit numpy NMS — kalan kutu indekslerini (skor sirali) dondurur."""
        if boxes_xyxy.shape[0] == 0:
            return []
        x1 = boxes_xyxy[:, 0]
        y1 = boxes_xyxy[:, 1]
        x2 = boxes_xyxy[:, 2]
        y2 = boxes_xyxy[:, 3]
        areas = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            rest = order[1:]
            xx1 = np.maximum(x1[i], x1[rest])
            yy1 = np.maximum(y1[i], y1[rest])
            xx2 = np.minimum(x2[i], x2[rest])
            yy2 = np.minimum(y2[i], y2[rest])
            inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
            union = areas[i] + areas[rest] - inter
            iou = np.where(union > 0, inter / union, 0.0)
            order = rest[iou <= iou_thr]
        return keep


def build_onnx_pose_detector(model_path: str, conf: float = 0.25) -> OnnxPoseDetector | None:
    """Graceful factory: yuklenemezse None doner (cagiran PyTorch'a duser)."""
    try:
        detector = OnnxPoseDetector(model_path, conf=conf)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OnnxPoseDetector olusturulamadi: %s", exc)
        return None
    if not detector.available:
        logger.warning("OnnxPoseDetector yuklenemedi: %s", detector.load_error)
        return None
    return detector
