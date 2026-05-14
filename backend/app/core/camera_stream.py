import asyncio
import threading
import time
from datetime import datetime

import cv2

from app.config import get_settings
from app.core.alarm_manager import AlarmManager, cap_level
from app.core.detector import get_detector
from app.core.motion_analyzer import MotionAnalyzer
from app.core.performance_monitor import PerformanceMonitor
from app.database import SessionLocal
from app.services.event_service import create_event
from app.services.incident_service import IncidentTracker, incident_payload
from app.services.websocket_manager import manager


class CameraStreamWorker:
    def __init__(self, camera_id: int, source: str | int) -> None:
        self.camera_id = camera_id
        self.source = source
        self.running = False
        self.thread: threading.Thread | None = None
        self.latest_jpeg: bytes | None = None
        self.settings = get_settings()

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _run(self) -> None:
        detector = get_detector()
        analyzer = MotionAnalyzer(sensitivity=self.settings.sensitivity)
        alarm = AlarmManager()
        perf = PerformanceMonitor()
        profile = self.settings.analysis_profile("realtime")
        db = SessionLocal()
        incident_tracker = IncidentTracker(db, "camera", camera_id=self.camera_id, fps=25.0)
        frame_index = 0
        last_event_by_pair: dict[tuple, int] = {}
        cap = None
        try:
            while self.running:
                if cap is None or not cap.isOpened():
                    cap = cv2.VideoCapture(self.source)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if not cap.isOpened():
                        time.sleep(2)
                        continue
                ret, frame = cap.read()
                if not ret:
                    cap.release()
                    cap = None
                    time.sleep(1)
                    continue
                frame_index += 1
                interval = max(1, int(profile.get("frame_skip", self.settings.frame_skip)), int(profile.get("yolo_interval", self.settings.frame_skip)))
                if frame_index % interval == 0:
                    detections = detector.detect_and_track(frame, int(profile.get("input_size", self.settings.input_size)))
                    optical_flow_enabled = frame_index % max(1, int(profile.get("optical_flow_interval", interval))) == 0
                    _, score_info = analyzer.analyze(frame, detections, frame_index, optical_flow_enabled=optical_flow_enabled)
                    level, smoothed, consecutive = alarm.update(score_info["score"])
                    level = cap_level(level, score_info.get("label", "NORMAL"))
                    involved_ids = set(score_info.get("pair") or []) if self.settings.only_highlight_involved_persons else None
                    annotated = detector.annotate(frame, detections, smoothed, level, score_info.get("reasons", []), involved_ids)
                    incident = incident_tracker.update(frame_index, smoothed, level, score_info, annotated, datetime.utcnow())
                    if incident:
                        asyncio.run(manager.broadcast(f"live:{self.camera_id}", {"type": "incident", **incident_payload(incident)}))
                    ok, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                    if ok:
                        self.latest_jpeg = encoded.tobytes()
                    stats = perf.tick(detector.last_inference_ms)
                    asyncio.run(
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
                        asyncio.run(
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
            if cap is not None:
                cap.release()
            db.close()
