import asyncio
import collections
import logging
import os
import threading
import time
from datetime import datetime

import cv2
import numpy as np

class _BackgroundBroadcaster:
    """One always-running event loop in a daemon thread for fire-and-forget WS broadcasts.

    Keeps WebSocket I/O off the frame analysis/delivery hot loop so a slow client can
    never stall frame processing. Coroutines are scheduled without waiting for them.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro) -> None:
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception:
            # Scheduling must never break the stream loop.
            try:
                coro.close()
            except Exception:
                pass


_broadcaster = _BackgroundBroadcaster()


def _broadcast_bg(coro) -> None:
    """Schedule a WS broadcast without blocking the caller (frame delivery path)."""
    _broadcaster.submit(coro)

from app.config import get_settings
from app.core.alarm_manager import AlarmManager, cap_level
from app.core.detector import get_detector
from app.core.fight_classifier import FightClipBuffer, fuse_classifier_score, get_fight_classifier
from app.core.motion_analyzer import MotionAnalyzer
from app.core.performance_monitor import PerformanceMonitor
from app.core.scoring import apply_classifier_suppression
from app.core.plate_recognition_pipeline import get_plate_pipeline
from app.database import SessionLocal
from app.models.camera import Camera
from app.services.event_service import create_event
from app.services.incident_service import IncidentTracker, incident_payload
from app.services.person_registry import PersonRegistry
from app.services.plate_service import plate_vote_buffer
from app.services.vehicle_tracker import VehicleTracker, expand_bbox_crop
from app.services.websocket_manager import manager
from app.utils.file_utils import public_static_path

logger = logging.getLogger("progoz.camera_stream")


# ── Web Yayini (external/YouTube stream) icin opsiyonel ONNX pose detektoru ───────────
# SADECE source_type == "web" akisini etkiler. Webcam/RTSP/video analizi paylasilan
# PyTorch detektorunu (get_detector singleton'i) kullanmaya devam eder.
def _web_stream_use_onnx_pose() -> bool:
    return os.getenv("WEB_STREAM_USE_ONNX_POSE", "false").strip().lower() in ("1", "true", "yes", "on")


def _web_onnx_pose_path() -> str:
    return os.getenv("WEB_STREAM_ONNX_POSE_PATH", "ml/models/pose/yolov8n-pose.onnx")


class _ByteTrackInput:
    """Ultralytics BYTETracker.update() icin Results benzeri hafif sarmalayici.

    Tracker yalnizca .conf / .xywh (center format) / .cls ve boolean-maske ile
    indekslemeye ihtiyac duyar. ByteTrack koduna DOKUNULMAZ.
    """

    def __init__(self, xywh: np.ndarray, conf: np.ndarray, cls: np.ndarray) -> None:
        self.xywh = xywh
        self.conf = conf
        self.cls = cls

    def __len__(self) -> int:
        return int(len(self.conf))

    def __getitem__(self, idx) -> "_ByteTrackInput":
        return _ByteTrackInput(self.xywh[idx], self.conf[idx], self.cls[idx])


class _OnnxWebDetector:
    """OnnxPoseDetector + ByteTrack'i, PersonDetector.detect_and_track ile ayni
    arayuzde sunan drop-in sarmalayici (sadece web yayini akisinda kullanilir).

    detect_and_track() ciktisi PyTorch detektoruyle birebir ayni formattadir:
        {"track_id", "bbox":[x1,y1,x2,y2], "confidence", "keypoints":[{x,y,confidence}*17]}
    annotate() cizimi paylasilan PyTorch detektore delege edilir (model gerektirmez).
    """

    def __init__(self, onnx_detector, annotate_source) -> None:
        self._onnx = onnx_detector
        self._annotate_source = annotate_source
        self.available = bool(onnx_detector.available)
        self.model_name = onnx_detector.model_path
        self.last_inference_ms = 0.0
        self._tracker = self._make_tracker()

    @staticmethod
    def _make_tracker():
        from types import SimpleNamespace

        from ultralytics.trackers.byte_tracker import BYTETracker

        # bytetrack.yaml varsayilanlari (PyTorch yolundaki tracker="bytetrack.yaml" ile ayni)
        args = SimpleNamespace(
            track_high_thresh=0.25,
            track_low_thresh=0.1,
            new_track_thresh=0.25,
            track_buffer=30,
            match_thresh=0.8,
            fuse_score=True,
        )
        return BYTETracker(args)

    @property
    def device_label(self) -> str:
        return self._onnx.device_label

    def detect_and_track(self, frame, input_size=None):
        result = self._onnx.detect(frame)
        self.last_inference_ms = self._onnx.last_inference_ms
        boxes = result.get("boxes") or []
        keypoints = result.get("keypoints") or []
        if not boxes:
            return []
        boxes_np = np.asarray(boxes, dtype=np.float32)  # (N,6): x1,y1,x2,y2,conf,cls
        xyxy = boxes_np[:, :4]
        conf = boxes_np[:, 4]
        cls = boxes_np[:, 5]
        # xyxy -> xywh (center) — ByteTrack center-format bekliyor
        cxcywh = np.empty_like(xyxy)
        cxcywh[:, 0] = (xyxy[:, 0] + xyxy[:, 2]) / 2.0
        cxcywh[:, 1] = (xyxy[:, 1] + xyxy[:, 3]) / 2.0
        cxcywh[:, 2] = xyxy[:, 2] - xyxy[:, 0]
        cxcywh[:, 3] = xyxy[:, 3] - xyxy[:, 1]
        try:
            tracks = self._tracker.update(_ByteTrackInput(cxcywh, conf, cls), frame)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ByteTrack update hatasi (web onnx): %s", exc)
            return []
        detections: list[dict] = []
        if tracks is None or len(tracks) == 0:
            return detections
        for row in tracks:
            # row: [x1, y1, x2, y2, track_id, score, cls, det_idx]
            det = {
                "track_id": int(row[4]),
                "bbox": [int(row[0]), int(row[1]), int(row[2]), int(row[3])],
                "confidence": float(row[5]),
            }
            det_idx = int(row[7])
            if 0 <= det_idx < len(keypoints):
                det["keypoints"] = [
                    {"x": float(p[0]), "y": float(p[1]), "confidence": float(p[2])}
                    for p in keypoints[det_idx]
                ]
            detections.append(det)
        return detections

    def annotate(self, *args, **kwargs):
        return self._annotate_source.annotate(*args, **kwargs)


def _build_web_onnx_detector(annotate_source) -> "_OnnxWebDetector | None":
    """Web yayini icin direkt ONNX Runtime pose detektoru + ByteTrack sarmalayici olustur.

    Paylasilan get_detector() singleton'ina DOKUNMAZ; ByteTrack durumu bu worker'a
    ozeldir. Model yoksa/yuklenemezse None doner (cagiran PyTorch'a geri duser).
    annotate_source: cizim icin kullanilacak PyTorch detektoru (model gerektirmez).
    """
    from app.services.onnx_pose_detector import build_onnx_pose_detector

    onnx_detector = build_onnx_pose_detector(
        _web_onnx_pose_path(),
        conf=get_settings().confidence_threshold,
    )
    if onnx_detector is None:
        return None
    return _OnnxWebDetector(onnx_detector, annotate_source)


def _web_stream_tiled() -> bool:
    return os.getenv("WEB_STREAM_TILED_DETECTION", "false").strip().lower() in ("1", "true", "yes", "on")


def _nms_numpy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float = 0.5) -> list[int]:
    """Bagimsizlik icin saf-numpy NMS (parcalar arasi cakisan kutulari tekillestirir)."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thr]
    return keep


class _TiledPoseDetector:
    """Kareyi rows×cols parcaya bolup HER parcada ayri tespit yapar -> uzaktaki/kucuk
    insanlar (tam karede kacarken) parca icinde gorece buyur ve YAKALANIR.

    OOM olmamasi icin YENI MODEL YUKLEMEZ; paylasilan detektorun zaten yuklu YOLO
    modelini predict ile kullanir. Parca tespitleri tam-kare koordinatina tasinir,
    NMS ile tekillestirilir, kendi ByteTracker'iyla ID atanir. detect_and_track/annotate
    arayuzu PersonDetector ile birebir aynidir.
    """

    def __init__(self, base_detector, rows: int = 2, cols: int = 2, overlap: float = 0.2) -> None:
        self._base = base_detector
        self._model = base_detector.model
        self._device = base_detector.device
        self._half = bool(getattr(base_detector, "half_enabled", False)) and base_detector.device != "cpu"
        self._conf = float(os.getenv("WEB_STREAM_TILED_CONF", "0.15"))
        self.rows, self.cols, self.overlap = rows, cols, overlap
        # Uzak/minik insanlar dusuk-guvenli (0.15-0.25) tespit edilir; varsayilan ByteTrack
        # esikleri (0.25) bunlari eler. Tiled icin DUSUK esikli tracker -> uzaklari da ID'ler.
        from types import SimpleNamespace

        from ultralytics.trackers.byte_tracker import BYTETracker

        # ID kararliligi: track_buffer uzun (kisa kayipta ayni ID korunur) + match_thresh
        # yuksek (yeniden yakalamada mevcut track'e baglanir, yeni ID acmaz).
        self._tracker = BYTETracker(SimpleNamespace(
            track_high_thresh=0.12,
            track_low_thresh=0.05,
            new_track_thresh=0.20,
            track_buffer=150,
            match_thresh=0.92,
            fuse_score=True,
        ))
        self.available = bool(base_detector.available)
        self.model_name = f"{base_detector.model_name} (tiled {rows}x{cols})"
        self.last_inference_ms = 0.0

    @property
    def device_label(self) -> str:
        return self._base.device_label

    def detect_and_track(self, frame, input_size=None):
        import time as _t

        sz = int(input_size or 640)
        h, w = frame.shape[:2]
        th, tw = h // self.rows, w // self.cols
        oy, ox = int(self.overlap * th), int(self.overlap * tw)
        all_xyxy: list = []
        all_conf: list = []
        all_kpts: list = []
        t0 = _t.perf_counter()
        for ri in range(self.rows):
            for ci in range(self.cols):
                y1 = max(0, ri * th - oy)
                y2 = min(h, (ri + 1) * th + oy)
                x1 = max(0, ci * tw - ox)
                x2 = min(w, (ci + 1) * tw + ox)
                tile = frame[y1:y2, x1:x2]
                if tile.size == 0:
                    continue
                try:
                    r = self._model.predict(
                        tile, imgsz=sz, conf=self._conf, classes=[0],
                        device=self._device, half=self._half, verbose=False,
                    )[0]
                except Exception:
                    continue
                if r.boxes is None or len(r.boxes) == 0:
                    continue
                xyxy = r.boxes.xyxy.cpu().numpy()
                conf = r.boxes.conf.cpu().numpy()
                kxy = r.keypoints.xy.cpu().numpy() if (getattr(r, "keypoints", None) is not None and r.keypoints.xy is not None) else None
                kcf = r.keypoints.conf.cpu().numpy() if (getattr(r, "keypoints", None) is not None and r.keypoints.conf is not None) else None
                for j in range(len(xyxy)):
                    bx = xyxy[j].astype(np.float32).copy()
                    bx[0] += x1; bx[1] += y1; bx[2] += x1; bx[3] += y1
                    all_xyxy.append(bx)
                    all_conf.append(float(conf[j]))
                    if kxy is not None:
                        kk = kxy[j].astype(np.float32).copy()
                        kk[:, 0] += x1; kk[:, 1] += y1
                        cc = kcf[j] if kcf is not None else np.ones(len(kk), dtype=np.float32)
                        all_kpts.append((kk, cc))
                    else:
                        all_kpts.append(None)
        self.last_inference_ms = (_t.perf_counter() - t0) * 1000
        if not all_xyxy:
            return []
        boxes = np.array(all_xyxy, dtype=np.float32)
        scores = np.array(all_conf, dtype=np.float32)
        # IoU 0.4: parca sinirindaki ayni kisinin 2 kopyasini daha agresif birlestir.
        keep = _nms_numpy(boxes, scores, 0.4)
        mxyxy = boxes[keep]
        mconf = scores[keep]
        cxcywh = np.empty_like(mxyxy)
        cxcywh[:, 0] = (mxyxy[:, 0] + mxyxy[:, 2]) / 2.0
        cxcywh[:, 1] = (mxyxy[:, 1] + mxyxy[:, 3]) / 2.0
        cxcywh[:, 2] = mxyxy[:, 2] - mxyxy[:, 0]
        cxcywh[:, 3] = mxyxy[:, 3] - mxyxy[:, 1]
        mcls = np.zeros(len(keep), dtype=np.float32)
        try:
            tracks = self._tracker.update(_ByteTrackInput(cxcywh, mconf, mcls), frame)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Tiled ByteTrack update hatasi: %s", exc)
            return []
        detections: list[dict] = []
        if tracks is None or len(tracks) == 0:
            return detections
        for row in tracks:
            d = {
                "track_id": int(row[4]),
                "bbox": [int(row[0]), int(row[1]), int(row[2]), int(row[3])],
                "confidence": float(row[5]),
            }
            di = int(row[7])
            if 0 <= di < len(keep):
                kp = all_kpts[keep[di]]
                if kp is not None:
                    kk, cc = kp
                    d["keypoints"] = [
                        {"x": float(p[0]), "y": float(p[1]), "confidence": float(c)}
                        for p, c in zip(kk, cc)
                    ]
            detections.append(d)
        return detections

    def annotate(self, *args, **kwargs):
        return self._base.annotate(*args, **kwargs)


class _FrameReader:
    """
    Background thread that drains a VideoCapture as fast as possible.
    Only the most recent decoded frame is kept (deque maxlen=1).
    This decouples network I/O (HLS segment download) from the analysis loop,
    preventing the main thread from freezing while waiting for the next segment.
    """

    def __init__(self, cap: cv2.VideoCapture, *, live_drain: bool = True) -> None:
        self._cap = cap
        self._buf: collections.deque = collections.deque(maxlen=1)
        self._seq = 0  # increments on every new frame
        self._eof = False
        self._running = True
        # Detect live stream vs finite VOD. For finite files CAP_PROP_FRAME_COUNT is
        # positive; for live HLS/RTSP it is 0 or negative.
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        is_live = frame_count is None or frame_count <= 0
        # VOD: rate-limit reading to source FPS so frames aren't consumed faster than
        # real-time (which would cause a 5-10x fast-forward effect).
        # Live (when live_drain): drain as fast as frames arrive and keep only the latest,
        # so the display always shows the freshest frame instead of a buffered/stale one.
        # cap.read() on a live source blocks until the next real-time frame, so this does
        # not busy-spin and does not change analysis frequency/accuracy.
        self._rate_limited = not (live_drain and is_live)
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        self._frame_interval = 1.0 / max(1.0, min(src_fps or 25.0, 60.0))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            t0 = time.monotonic()
            ret, frame = self._cap.read()
            if ret:
                self._buf.append(frame)
                self._seq += 1
                if self._rate_limited:
                    elapsed = time.monotonic() - t0
                    wait = self._frame_interval - elapsed
                    if wait > 0:
                        time.sleep(wait)
            else:
                self._eof = True
                break

    def get_new(self, last_seq: int):
        """
        Return (frame, new_seq) if a frame newer than last_seq is available.
        Returns (None, last_seq) if nothing new yet.
        Always returns the *latest* frame — never a stale buffered one.
        """
        seq = self._seq
        if seq > last_seq:
            try:
                return self._buf[-1], seq
            except IndexError:
                pass
        return None, last_seq

    def get_latest(self):
        """Return the most recent frame without consuming the sequence counter."""
        try:
            return self._buf[-1]
        except IndexError:
            return None

    @property
    def eof(self) -> bool:
        return self._eof

    def stop(self) -> None:
        self._running = False


class CameraStreamWorker:
    def __init__(self, camera_id: int, source: str | int) -> None:
        self.camera_id = camera_id
        self.source = source
        self.running = False
        self.thread: threading.Thread | None = None
        self.latest_jpeg: bytes | None = None
        self.settings = get_settings()
        self._is_first_open = True  # skip re-extraction on first open
        # Shared state written by analysis thread, read by display thread
        self._last_score: float = 0.0
        self._last_level: str = "NORMAL"
        self._annotated_at: float = 0.0  # monotonic time of last annotated frame
        # Web stream only: most recent plate detections for the overlay_update message.
        self._web_recent_plates: list[dict] = []

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run_display(self, reader: "_FrameReader") -> None:
        """
        Display thread: pushes raw frames at ~25 FPS so the browser sees smooth video
        even when YOLO analysis is running slowly (1-3 FPS on CPU).
        Draws the last known score/level as a lightweight text overlay.
        When YOLO just produced an annotated frame, holds it briefly before switching
        back to raw frames so the user can see the bounding boxes.
        """
        _FONT = cv2.FONT_HERSHEY_SIMPLEX
        _ANNOTATED_HOLD = 0.18  # seconds to show full annotated frame before switching back
        _TARGET_DT = 1.0 / 25   # ~25 FPS display target
        _COLORS = {
            "NORMAL": (40, 200, 40),
            "SUPHELI": (40, 180, 255),
            "OLASI_KAVGA": (30, 100, 255),
            "KAVGA": (30, 30, 220),
        }
        while self.running and not reader.eof:
            t0 = time.monotonic()
            frame = reader.get_latest()
            since_annotated = t0 - self._annotated_at
            if frame is not None and since_annotated > _ANNOTATED_HOLD:
                disp = frame.copy()
                level = self._last_level
                color = _COLORS.get(level, (40, 200, 40))
                cv2.putText(
                    disp,
                    f"{level}  {self._last_score:.1f}",
                    (8, 32),
                    _FONT,
                    0.75,
                    color,
                    2,
                    cv2.LINE_AA,
                )
                ok, enc = cv2.imencode(".jpg", disp, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if ok:
                    self.latest_jpeg = enc.tobytes()
            elapsed = time.monotonic() - t0
            time.sleep(max(0.008, _TARGET_DT - elapsed))

    def _run_web_display(self, reader: "_FrameReader") -> None:
        """Web yayini icin SADELESTIRILMIS ham gosterim thread'i (Thread 1 ciktisi).

        Analizden TAMAMEN bagimsiz: en guncel ham frame'i ~30 FPS'te JPEG'e cevirip
        MJPEG endpoint'ine verir. Frame uzerine HICBIR SEY cizmez — bounding box'lar,
        skor ve seviye frontend canvas'inda 'overlay_update' mesajiyla cizilir.
        Boylece analiz ~1 FPS'te calissa bile video akici kalir (donma olmaz).

        SADECE source_type == "web" akisinda kullanilir; webcam/RTSP _run_display
        ile calismaya devam eder.
        """
        _TARGET_DT = 1.0 / 30  # ~30 FPS ham gorüntü hedefi
        while self.running and not reader.eof:
            t0 = time.monotonic()
            frame = reader.get_latest()  # thread-safe latest-frame handoff (deque maxlen=1)
            if frame is not None:
                ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok:
                    self.latest_jpeg = enc.tobytes()
            elapsed = time.monotonic() - t0
            time.sleep(max(0.005, _TARGET_DT - elapsed))

    def _open_capture(self, db) -> cv2.VideoCapture | None:
        """
        Open VideoCapture for the current source.
        On reconnections, web cameras re-run yt-dlp to get a fresh URL
        (extracted URLs often have short-lived auth tokens) — UNLESS the URL is a
        direct stream (.m3u8 / .mjpg), in which case it is opened as-is (no yt-dlp).
        First open uses the URL already extracted by camera_routes.py.
        """
        source = self.source
        if not self._is_first_open:
            camera = db.get(Camera, self.camera_id)
            if camera and camera.source_type == "web" and camera.rtsp_url:
                from app.services.stream_extractor import extract_stream_url, is_direct_stream_url
                if is_direct_stream_url(camera.rtsp_url):
                    # Dogrudan akis: yt-dlp kullanma, URL'yi dogrudan ac.
                    source = camera.rtsp_url
                    self.source = source
                else:
                    try:
                        source = extract_stream_url(camera.rtsp_url)
                        self.source = source
                        logger.info("Web stream URL yenilendi camera_id=%s", self.camera_id)
                    except Exception as exc:
                        logger.warning("Web stream URL alinamadi camera_id=%s: %s", self.camera_id, exc)
                        return None
        self._is_first_open = False

        cap = self._make_capture(source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    @staticmethod
    def _make_capture(source) -> cv2.VideoCapture:
        """VideoCapture'i kaynak turune gore acar.

        - Webcam (int / sayisal) -> varsayilan backend (degismez).
        - Ag akisi (http/https/m3u8, ozellikle YouTube HLS) -> FFmpeg + otomatik
          yeniden baglanma; segment takilmalarinda goruntu donmasini azaltir.
        - RTSP -> FFmpeg + TCP tasima (UDP paket kaybindan kaynakli kasma/donma azalir).
        Webcam/RTSP davranisi yalnizca daha kararli hale gelir; analiz sikligi DEGISMEZ.
        """
        if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
            return cv2.VideoCapture(int(source))
        if isinstance(source, str):
            low = source.lower()
            if low.startswith("rtsp://"):
                ff_opts = "rtsp_transport;tcp|max_delay;500000|stimeout;5000000"
            else:
                # http/https/m3u8 (YouTube canli HLS dahil): kopuklukte yeniden baglan.
                ff_opts = "reconnect;1|reconnect_streamed;1|reconnect_delay_max;2"
            prev = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = ff_opts
            try:
                return cv2.VideoCapture(source, cv2.CAP_FFMPEG)
            finally:
                # Secenekleri sadece bu acilis icin uygula; diger yollari (VOD vb.) etkileme.
                if prev is None:
                    os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
                else:
                    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = prev
        return cv2.VideoCapture(source)

    def _run(self) -> None:
        detector = get_detector()
        analyzer = MotionAnalyzer(sensitivity=self.settings.sensitivity)
        alarm = AlarmManager()
        fight_classifier = get_fight_classifier()
        fight_buffer = FightClipBuffer(maxlen=self.settings.fight_classifier_clip_len)
        last_classifier_probability: float | None = None
        perf = PerformanceMonitor()
        profile = self.settings.analysis_profile("realtime")
        db = SessionLocal()
        camera = db.get(Camera, self.camera_id)
        plate_enabled = bool(camera and camera.plate_recognition_enabled)
        plate_interval = max(1, int(camera.plate_frame_interval if camera else self.settings.plate_frame_interval("realtime")))
        camera_name = camera.name if camera else None

        # Web Yayini (external stream) icin opsiyonel ONNX pose modeli.
        # Yalnizca source_type == "web" + flag acik + model yuklenebiliyorsa devreye girer;
        # aksi halde paylasilan PyTorch detektoru aynen kullanilir (varsayilan davranis).
        is_web_stream = bool(camera and getattr(camera, "source_type", None) == "web")
        if is_web_stream and _web_stream_use_onnx_pose():
            # PyTorch detector (annotate kaynagi) zaten yuklu; detection icin direkt ONNX'e gec.
            web_detector = _build_web_onnx_detector(annotate_source=detector)
            if web_detector is not None and web_detector.available:
                detector = web_detector
                logger.warning(
                    "Web stream camera_id=%s direkt ONNX pose detektoru aktif: %s (%s)",
                    self.camera_id, web_detector.model_name, web_detector.device_label,
                )
            else:
                logger.warning(
                    "Web stream camera_id=%s ONNX pose yuklenemedi, PyTorch'a donuluyor",
                    self.camera_id,
                )
        elif is_web_stream and _web_stream_tiled():
            # TILED: uzak/genis cam'lerde minik insanlari yakalamak icin kareyi parcalara
            # bolup her parcada tespit yapar. YENI MODEL YUKLEMEZ (paylasilan modeli predict
            # ile kullanir -> OOM yok). Olcumde tam-kare 1 kisi iken 2x2 parca 5 kisi yakaladi.
            try:
                tiled = _TiledPoseDetector(detector)
                if tiled.available:
                    detector = tiled
                    logger.warning(
                        "Web stream camera_id=%s TILED pose detektoru aktif (%s)",
                        self.camera_id, tiled.model_name,
                    )
            except Exception as exc:
                logger.warning("Web stream camera_id=%s tiled detektor olusturulamadi: %s", self.camera_id, exc)
        elif is_web_stream:
            # Web yayini PAYLASILAN PyTorch pose detektorunu (get_detector singleton) kullanir.
            # Neden ayri (dedicated) model DEGIL: auto-start kapali + ayni anda tek yayin
            # izlendigi icin tracker durumu cakismasi pratikte olmaz; ayrica 2. yolov8s
            # modelini @640 yuklemek 6GB GPU'da OOM/native cokme yapiyordu. Tek model = stabil.
            logger.warning(
                "Web stream camera_id=%s paylasilan PyTorch pose detektoru kullaniyor (%s)",
                self.camera_id, detector.device_label,
            )
        plate_pipeline = get_plate_pipeline() if plate_enabled else None
        vehicle_tracker = VehicleTracker() if plate_pipeline else None
        if plate_pipeline:
            plate_pipeline.reset_stats()
            logger.warning(
                "Camera plate recognition camera_id=%s enabled=%s available=%s plate_frame_interval=%s detector_loaded=%s ocr_loaded=%s",
                self.camera_id,
                plate_enabled,
                plate_pipeline.available,
                plate_interval,
                plate_pipeline.detector.available,
                bool(plate_pipeline.ocr and plate_pipeline.ocr.available),
            )
        incident_tracker = IncidentTracker(db, "camera", camera_id=self.camera_id, fps=25.0)
        # Kisi Takibi kayit defteri (per-ID crop + 60sn TTL + anomalide DB'ye yukseltme)
        person_registry = PersonRegistry(self.camera_id, camera_name)
        frame_index = 0
        last_event_by_pair: dict[tuple, int] = {}
        cap = None
        reader: _FrameReader | None = None
        display_thread: threading.Thread | None = None
        last_seq = -1

        try:
            while self.running:
                # ── Open capture + start background reader if needed ──────────
                need_open = cap is None or not cap.isOpened() or (reader is not None and reader.eof)
                if need_open:
                    if reader is not None:
                        reader.stop()
                        reader = None
                    if cap is not None:
                        cap.release()
                        cap = None
                    last_seq = -1

                    cap = self._open_capture(db)
                    if cap is None:
                        time.sleep(3)
                        continue

                    live_drain = os.getenv("STREAM_LIVE_DRAIN_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
                    reader = _FrameReader(cap, live_drain=live_drain)
                    # Brief pause so the reader can buffer at least one frame
                    time.sleep(0.15)
                    # Start (or restart) the display thread for this reader session.
                    # Web streams get a dedicated RAW display (frames only, overlays via
                    # WebSocket); webcam/RTSP keep the existing annotated display path.
                    display_target = self._run_web_display if is_web_stream else self._run_display
                    display_thread = threading.Thread(
                        target=display_target, args=(reader,), daemon=True
                    )
                    display_thread.start()

                # ── Get latest frame (non-blocking) ──────────────────────────
                assert reader is not None
                frame, last_seq = reader.get_new(last_seq)
                if frame is None:
                    time.sleep(0.02)
                    continue

                frame_index += 1
                fight_buffer.append(frame)

                # ── Plate detection (every plate_interval frames) ─────────────
                if plate_pipeline and plate_pipeline.available and frame_index % plate_interval == 0:
                    try:
                        for detection in plate_pipeline.detector.detect(frame):
                            if detection.confidence < self.settings.plate_detector_confidence:
                                continue
                            crop = plate_pipeline._crop(frame, detection)
                            ocr_candidates = (
                                plate_pipeline.ocr.read_all(crop)
                                if plate_pipeline.ocr and plate_pipeline.ocr.available
                                else []
                            )
                            ocr_result = ocr_candidates[0] if ocr_candidates else None
                            if not ocr_result or not plate_pipeline._should_save_ocr_result(ocr_result):
                                continue
                            crop_path = plate_pipeline._save_image(
                                crop, "crop", "camera", self.camera_id, None, frame_index
                            )
                            confidence = (
                                min(detection.confidence, ocr_result.confidence)
                                if ocr_result.confidence > 0
                                else detection.confidence
                            )
                            plate_text = ocr_result.text.normalized_plate or ocr_result.text.raw_text or ""
                            # Vehicle tracking layer: stable vehicle_id + body color.
                            if vehicle_tracker is not None:
                                try:
                                    body_crop = expand_bbox_crop(frame, detection.bbox, scale=3.0)
                                    vehicle_tracker.update(detection.bbox, plate_text, confidence, body_crop)
                                except Exception:
                                    pass
                            plate_vote_buffer.add_vote(
                                f"webcam_{self.camera_id}",
                                plate_text,
                                confidence,
                                crop_path,
                            )
                            # Web stream: keep a small recent-plates list for overlay_update
                            # (display only — does not affect vote buffer / dedup logic).
                            if is_web_stream and plate_text:
                                self._web_recent_plates = (
                                    [{"plate": plate_text, "confidence": round(confidence, 3)}]
                                    + [p for p in self._web_recent_plates if p.get("plate") != plate_text]
                                )[:5]
                            _broadcast_bg(
                                manager.broadcast(
                                    f"live:{self.camera_id}",
                                    {
                                        "type": "plate_detected",
                                        "camera_id": self.camera_id,
                                        "plate": ocr_result.text.normalized_plate or ocr_result.text.raw_text,
                                        "confidence": round(confidence, 3),
                                    },
                                )
                            )
                    except Exception as exc:
                        logger.warning("Frame %d kamera plaka tespiti hatasi: %s", frame_index, exc)

                # ── Flush plate vote buffer every 300 frames ──────────────────
                if plate_pipeline and frame_index % 300 == 0 and frame_index > 0:
                    try:
                        plate_vote_buffer.flush_webcam(self.camera_id, db, vehicle_tracker)
                    except Exception as exc:
                        logger.warning("Camera %d plaka buffer flush hatasi: %s", self.camera_id, exc)

                # ── YOLO + motion analysis (every interval frames) ────────────
                interval = max(1, int(profile.get("frame_skip", self.settings.frame_skip)), int(profile.get("yolo_interval", self.settings.frame_skip)))
                if frame_index % interval == 0:
                    detections = detector.detect_and_track(frame, int(profile.get("input_size", self.settings.input_size)))
                    optical_flow_enabled = frame_index % max(1, int(profile.get("optical_flow_interval", interval))) == 0
                    _, score_info = analyzer.analyze(frame, detections, frame_index, optical_flow_enabled=optical_flow_enabled)
                    if (
                        fight_classifier.available
                        and frame_index % max(1, self.settings.fight_classifier_interval) == 0
                        and fight_buffer.ready(fight_classifier.clip_len)
                    ):
                        last_classifier_probability = fight_classifier.predict(fight_buffer.latest(fight_classifier.clip_len))
                    score_info = fuse_classifier_score(score_info, last_classifier_probability)
                    score_info["score"] = apply_classifier_suppression(
                        float(score_info["score"]),
                        float(score_info.get("heuristic_score", score_info["score"])),
                        last_classifier_probability,
                        float(self.settings.alarm_thresholds.get("OLASI_KAVGA", 55.0)),
                    )
                    level, smoothed, consecutive = alarm.update(score_info["score"])
                    level = cap_level(level, score_info.get("label", "NORMAL"))
                    involved_ids = set(score_info.get("pair") or []) if self.settings.only_highlight_involved_persons else None
                    annotated = detector.annotate(frame, detections, smoothed, level, score_info.get("reasons", []), involved_ids)
                    incident = incident_tracker.update(frame_index, smoothed, level, score_info, annotated, datetime.utcnow())
                    if incident:
                        _broadcast_bg(manager.broadcast(f"live:{self.camera_id}", {"type": "incident", **incident_payload(incident)}))

                    # ── Kisi Takibi: per-ID crop yakala + anomalide DB'ye yukselt + canli yayinla ──
                    # Tamamen savunmaci: hata olsa bile analiz/akis dongusunu ASLA bozmaz.
                    try:
                        person_registry.update(frame, detections)
                        if level != "NORMAL":
                            _flag_ids = involved_ids if involved_ids else set(score_info.get("pair") or [])
                            person_registry.flag_and_persist(_flag_ids, level, smoothed, SessionLocal)
                        _broadcast_bg(manager.broadcast(
                            f"live:{self.camera_id}",
                            {"type": "persons_update", "camera_id": self.camera_id,
                             "persons": person_registry.live_payload()},
                        ))
                    except Exception:
                        pass

                    self._last_score = round(smoothed, 1)
                    self._last_level = level
                    if is_web_stream:
                        # Web: ham video AYRI thread'de akar (latest_jpeg'e dokunma).
                        # Analiz sonucu yalnizca koordinat olarak frontend canvas'ina gider,
                        # boylece video analizden bagimsiz, akici kalir.
                        frame_h, frame_w = frame.shape[:2]
                        _broadcast_bg(
                            manager.broadcast(
                                f"live:{self.camera_id}",
                                {
                                    "type": "overlay_update",
                                    "camera_id": self.camera_id,
                                    "boxes": [
                                        {
                                            "id": int(d.get("track_id") or -1),
                                            "x1": int(d["bbox"][0]),
                                            "y1": int(d["bbox"][1]),
                                            "x2": int(d["bbox"][2]),
                                            "y2": int(d["bbox"][3]),
                                            "conf": round(float(d.get("confidence", 0.0)), 3),
                                        }
                                        for d in detections
                                    ],
                                    "score": round(smoothed, 1),
                                    "level": level,
                                    "plates": list(self._web_recent_plates),
                                    "frame_w": int(frame_w),
                                    "frame_h": int(frame_h),
                                    "timestamp": time.time(),
                                },
                            )
                        )
                    else:
                        # Push annotated frame; display thread will hold it briefly then resume raw
                        ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        if ok:
                            self.latest_jpeg = encoded.tobytes()
                            self._annotated_at = time.monotonic()

                    stats = perf.tick(detector.last_inference_ms)
                    _broadcast_bg(
                        manager.broadcast(
                            f"live:{self.camera_id}",
                            {
                                "type": "frame_status",
                                "camera_id": self.camera_id,
                                "fps": stats["fps"],
                                "latency_ms": stats["latency_ms"],
                                "alarm_level": level,
                                "score": round(smoothed, 1),
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )
                    )
                    pair_key = tuple(score_info.get("pair") or ("unknown",))
                    last_pair_event = last_event_by_pair.get(pair_key, -999999)
                    threshold_ok = level in {"OLASI_KAVGA", "KAVGA"} and smoothed >= self.settings.alarm_thresholds[level]
                    if threshold_ok:
                        try:
                            from app.services.notification_service import notification_service as _ns
                            _ns.send_fight_alert(
                                user_id=str(getattr(camera, "user_id", None) or "all"),
                                source_id=f"camera_{self.camera_id}",
                                camera_name=camera_name or f"camera_{self.camera_id}",
                                score=smoothed,
                                level=level,
                                timestamp=datetime.utcnow().isoformat(),
                            )
                        except Exception as _exc:
                            logger.debug("Fight alert gonderilemedi: %s", _exc)
                    if self.settings.save_frame_level_events and threshold_ok and frame_index - last_pair_event > int(25 * self.settings.cooldown_seconds):
                        snapshot_path = self.settings.snapshot_dir / f"camera_{self.camera_id}_frame_{frame_index}.jpg"
                        cv2.imwrite(str(snapshot_path), annotated)
                        event = create_event(
                            db,
                            source_type="camera",
                            camera_id=self.camera_id,
                            severity=level,
                            score=smoothed,
                            frame_index=frame_index,
                            person_ids=",".join(map(str, score_info.get("pair") or [])),
                            snapshot_path=str(snapshot_path),
                            details={
                                "criteria": score_info.get("criteria", {}),
                                "penalties": score_info.get("penalties", {}),
                                "raw_score": score_info.get("raw_score", score_info["score"]),
                                "reasons": score_info.get("reasons", []),
                                "consecutive": consecutive,
                            },
                        )
                        last_event_by_pair[pair_key] = frame_index
                        _broadcast_bg(
                            manager.broadcast(
                                f"live:{self.camera_id}",
                                {
                                    "type": "event",
                                    "severity": event.severity,
                                    "score": event.score,
                                    "camera_id": self.camera_id,
                                    "snapshot_url": f"/static/snapshots/{snapshot_path.name}",
                                    "created_at": event.created_at.isoformat(),
                                },
                            )
                        )
        finally:
            self.running = False  # mark dead so is_running() returns False
            try:
                person_registry.stop()  # flag'lenmemis gecici crop'lari sil
            except Exception:
                pass
            if reader is not None:
                reader.stop()
            if cap is not None:
                cap.release()
            if plate_pipeline:
                try:
                    plate_vote_buffer.flush_webcam(self.camera_id, db, vehicle_tracker)
                except Exception as exc:
                    logger.warning("Camera %d stream kapanirken plaka flush hatasi: %s", self.camera_id, exc)
            db.close()
