import asyncio
import collections
import logging
import threading
import time
from datetime import datetime

import cv2

# Each worker thread gets its own event loop so we never create/destroy one per broadcast.
_thread_loop: threading.local = threading.local()


def _run_async(coro) -> None:
    """Run a coroutine from a sync thread using a cached per-thread event loop."""
    loop = getattr(_thread_loop, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _thread_loop.loop = loop
    loop.run_until_complete(coro)

from app.config import get_settings
from app.core.alarm_manager import AlarmManager, cap_level
from app.core.detector import get_detector
from app.core.fight_classifier import FightClipBuffer, fuse_classifier_score, get_fight_classifier
from app.core.motion_analyzer import MotionAnalyzer
from app.core.performance_monitor import PerformanceMonitor
from app.core.plate_recognition_pipeline import get_plate_pipeline
from app.database import SessionLocal
from app.models.camera import Camera
from app.services.event_service import create_event
from app.services.incident_service import IncidentTracker, incident_payload
from app.services.plate_service import plate_vote_buffer
from app.services.websocket_manager import manager
from app.utils.file_utils import public_static_path

logger = logging.getLogger("progoz.camera_stream")


class _FrameReader:
    """
    Background thread that drains a VideoCapture as fast as possible.
    Only the most recent decoded frame is kept (deque maxlen=1).
    This decouples network I/O (HLS segment download) from the analysis loop,
    preventing the main thread from freezing while waiting for the next segment.
    """

    def __init__(self, cap: cv2.VideoCapture) -> None:
        self._cap = cap
        self._buf: collections.deque = collections.deque(maxlen=1)
        self._seq = 0  # increments on every new frame
        self._eof = False
        self._running = True
        # Rate-limit reading to source FPS so HLS frames aren't consumed faster
        # than real-time (which would cause 5-10x fast-forward effect).
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

    def _open_capture(self, db) -> cv2.VideoCapture | None:
        """
        Open VideoCapture for the current source.
        On reconnections, web cameras re-run yt-dlp to get a fresh URL
        (extracted URLs often have short-lived auth tokens).
        First open uses the URL already extracted by camera_routes.py.
        """
        source = self.source
        if not self._is_first_open:
            camera = db.get(Camera, self.camera_id)
            if camera and camera.source_type == "web" and camera.rtsp_url:
                try:
                    from app.services.stream_extractor import extract_stream_url
                    source = extract_stream_url(camera.rtsp_url)
                    self.source = source
                    logger.info("Web stream URL yenilendi camera_id=%s", self.camera_id)
                except Exception as exc:
                    logger.warning("Web stream URL alinamadi camera_id=%s: %s", self.camera_id, exc)
                    return None
        self._is_first_open = False

        cap = cv2.VideoCapture(source)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            return None
        return cap

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
        plate_pipeline = get_plate_pipeline() if plate_enabled else None
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

                    reader = _FrameReader(cap)
                    # Brief pause so the reader can buffer at least one frame
                    time.sleep(0.15)
                    # Start (or restart) the display thread for this reader session
                    display_thread = threading.Thread(
                        target=self._run_display, args=(reader,), daemon=True
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
                            plate_vote_buffer.add_vote(
                                f"webcam_{self.camera_id}",
                                ocr_result.text.normalized_plate or ocr_result.text.raw_text or "",
                                confidence,
                                crop_path,
                            )
                            _run_async(
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
                        plate_vote_buffer.flush_webcam(self.camera_id, db)
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
                    level, smoothed, consecutive = alarm.update(score_info["score"])
                    level = cap_level(level, score_info.get("label", "NORMAL"))
                    involved_ids = set(score_info.get("pair") or []) if self.settings.only_highlight_involved_persons else None
                    annotated = detector.annotate(frame, detections, smoothed, level, score_info.get("reasons", []), involved_ids)
                    incident = incident_tracker.update(frame_index, smoothed, level, score_info, annotated, datetime.utcnow())
                    if incident:
                        _run_async(manager.broadcast(f"live:{self.camera_id}", {"type": "incident", **incident_payload(incident)}))

                    # Push annotated frame; display thread will hold it briefly then resume raw
                    self._last_score = round(smoothed, 1)
                    self._last_level = level
                    ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ok:
                        self.latest_jpeg = encoded.tobytes()
                        self._annotated_at = time.monotonic()

                    stats = perf.tick(detector.last_inference_ms)
                    _run_async(
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
                        _run_async(
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
            loop = getattr(_thread_loop, "loop", None)
            if loop and not loop.is_closed():
                loop.close()
            if reader is not None:
                reader.stop()
            if cap is not None:
                cap.release()
            if plate_pipeline:
                try:
                    plate_vote_buffer.flush_webcam(self.camera_id, db)
                except Exception as exc:
                    logger.warning("Camera %d stream kapanirken plaka flush hatasi: %s", self.camera_id, exc)
            db.close()
