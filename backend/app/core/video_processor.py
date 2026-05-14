import asyncio
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2

from app.config import get_settings
from app.core.alarm_manager import AlarmManager, cap_level
from app.core.detector import get_detector
from app.core.motion_analyzer import MotionAnalyzer
from app.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.event import Event
from app.models.incident import Incident
from app.services.event_service import create_event
from app.services.incident_service import IncidentTracker, incident_payload
from app.services.websocket_manager import manager
from app.utils.file_utils import public_static_path
from app.utils.ffmpeg_utils import convert_to_h264, ffmpeg_available


class VideoProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()

    def process_upload_job(self, job_id: int) -> None:
        db = SessionLocal()
        detector = get_detector()
        raw_output: Path | None = None
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if not job:
                return
            profile = self.settings.analysis_profile(job.analysis_mode)
            save_processed_video = bool(job.save_processed_video) and bool(profile.get("save_processed_video", True))
            analyzer = MotionAnalyzer(sensitivity=self.settings.sensitivity, debug_scoring=bool(job.debug_scoring))
            alarm = AlarmManager()
            job.status = "running"
            job.current_stage = "running"
            job.progress = 0.0
            job.processed_frames = 0
            job.skipped_frames = 0
            job.performance_json = None
            job.started_at = datetime.utcnow()
            if not detector.available:
                job.status = "failed"
                job.current_stage = "failed"
                job.error_message = f"YOLO modeli yuklenemedi: {detector.load_error or 'bilinmeyen hata'}"
                job.finished_at = datetime.utcnow()
                db.commit()
                asyncio.run(manager.broadcast("jobs", self._job_progress_payload(job)))
                asyncio.run(
                    manager.broadcast(
                        f"job:{job_id}",
                        {"type": "job_log", "message": "Analiz baslatilamadi; YOLO modeli yuklenemedi."},
                    )
                )
                return
            else:
                job.error_message = None
            db.commit()

            input_path = Path(job.original_path)
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise RuntimeError("Video dosyasi OpenCV ile acilamadi.")
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
            job.total_frames = total_frames
            db.commit()

            output_fps = float(profile.get("output_fps") or 0) or fps
            raw_output = self.settings.processed_dir / f"job_{job_id}_processed_raw.mp4"
            processed_output = self.settings.processed_dir / f"job_{job_id}_processed_h264.mp4"
            writer = None
            if save_processed_video:
                writer = cv2.VideoWriter(str(raw_output), cv2.VideoWriter_fourcc(*"mp4v"), output_fps, (width, height))
                if not writer.isOpened():
                    raise RuntimeError("OpenCV VideoWriter acilamadi; codec veya dosya yolu kontrol edilmeli.")
            frame_index = 0
            last_event_by_pair: dict[tuple, int] = {}
            start = perf_counter()
            yolo_times: list[float] = []
            flow_times: list[float] = []
            frame_times: list[float] = []
            db.query(Event).filter(Event.analysis_job_id == job_id).delete()
            db.query(Incident).filter(Incident.analysis_job_id == job_id).delete()
            db.commit()
            incident_tracker = IncidentTracker(db, "video", analysis_job_id=job_id, video_filename=job.filename, fps=fps)

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_index += 1
                analysis_interval = max(1, int(profile.get("frame_skip", self.settings.frame_skip)), int(profile.get("yolo_interval", self.settings.frame_skip)))
                optical_flow_interval = max(1, int(profile.get("optical_flow_interval", analysis_interval)))
                run_inference = frame_index % analysis_interval == 0
                if run_inference:
                    frame_start = perf_counter()
                    detections = detector.detect_and_track(frame, int(profile.get("input_size", self.settings.input_size)))
                    optical_flow_enabled = frame_index % optical_flow_interval == 0
                    _, score_info = analyzer.analyze(frame, detections, frame_index, optical_flow_enabled=optical_flow_enabled)
                    level, smoothed, consecutive = alarm.update(score_info["score"])
                    level = cap_level(level, score_info.get("label", "NORMAL"))
                    involved_ids = set(score_info.get("pair") or []) if self.settings.only_highlight_involved_persons else None
                    annotated = detector.annotate(frame, detections, smoothed, level, score_info.get("reasons", []), involved_ids)
                    if writer is not None:
                        writer.write(annotated)
                    incident = incident_tracker.update(frame_index, smoothed, level, score_info, annotated)
                    if incident:
                        asyncio.run(manager.broadcast(f"job:{job_id}", {"type": "incident", **incident_payload(incident)}))
                    yolo_times.append(detector.last_inference_ms)
                    flow_times.append(analyzer.last_optical_flow_ms)
                    frame_times.append((perf_counter() - frame_start) * 1000)
                    job.processed_frames += 1

                    pair_key = tuple(score_info.get("pair") or ("unknown",))
                    cooldown_frames = int(fps * self.settings.cooldown_seconds)
                    last_pair_event = last_event_by_pair.get(pair_key, -999999)
                    threshold_ok = level in {"SUPHELI", "OLASI_KAVGA", "KAVGA"} and smoothed >= self.settings.alarm_thresholds[level]
                    if self.settings.save_frame_level_events and threshold_ok and frame_index - last_pair_event > cooldown_frames:
                        snapshot_path = self.settings.snapshot_dir / f"job_{job_id}_frame_{frame_index}.jpg"
                        cv2.imwrite(str(snapshot_path), annotated)
                        event = create_event(
                            db,
                            source_type="video",
                            analysis_job_id=job_id,
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
                                "inference_ms": detector.last_inference_ms,
                            },
                        )
                        last_event_by_pair[pair_key] = frame_index
                        asyncio.run(manager.broadcast(f"job:{job_id}", self._job_event_payload(event)))
                else:
                    job.skipped_frames += 1
                if frame_index % 10 == 0 or frame_index == total_frames:
                    self._update_progress(db, job, frame_index, total_frames)
                    asyncio.run(manager.broadcast("jobs", self._job_progress_payload(job)))

            incident = incident_tracker.finalize()
            if incident:
                asyncio.run(manager.broadcast(f"job:{job_id}", {"type": "incident", **incident_payload(incident)}))
            cap.release()
            if writer is not None:
                writer.release()
            analysis_elapsed = perf_counter() - start
            final_path = None
            encoding_elapsed = 0.0
            if save_processed_video and raw_output and raw_output.exists() and raw_output.stat().st_size > 0 and ffmpeg_available():
                job.status = "encoding"
                job.current_stage = "encoding"
                job.progress = 99.0
                db.commit()
                asyncio.run(manager.broadcast("jobs", self._job_progress_payload(job)))
                encoding_start = perf_counter()
                try:
                    final_path = convert_to_h264(raw_output, processed_output)
                    encoding_elapsed = perf_counter() - encoding_start
                except Exception as exc:
                    encoding_elapsed = perf_counter() - encoding_start
                    job.error_message = f"FFmpeg H.264 donusumu basarisiz: {exc}. Ham MP4 kullanildi."
                    final_path = raw_output
            elif save_processed_video and (not raw_output or not raw_output.exists() or raw_output.stat().st_size == 0):
                raise RuntimeError("Islenmis video dosyasi uretilemedi veya 0 byte olustu.")
            elif save_processed_video:
                job.error_message = "FFmpeg bulunamadigi icin H.264 tarayici uyumlu cikti uretilemedi; tarayici onizlemesi orijinal videoya dusebilir."
                final_path = raw_output
            job.status = "completed"
            job.current_stage = "completed"
            job.progress = 100.0
            job.processed_path = str(final_path) if final_path else None
            job.finished_at = datetime.utcnow()
            total_elapsed = perf_counter() - start
            duration = frame_index / fps if fps else 0.0
            job.performance_json = json.dumps(
                {
                    "total_video_duration": round(duration, 3),
                    "total_frames": total_frames,
                    "read_frames": frame_index,
                    "processed_frames": job.processed_frames,
                    "skipped_frames": job.skipped_frames,
                    "analysis_time_seconds": round(analysis_elapsed, 3),
                    "encoding_time_seconds": round(encoding_elapsed, 3),
                    "total_job_time_seconds": round(total_elapsed, 3),
                    "effective_processing_fps": round(frame_index / max(total_elapsed, 1e-6), 2),
                    "average_yolo_ms": round(sum(yolo_times) / max(len(yolo_times), 1), 2),
                    "average_optical_flow_ms": round(sum(flow_times) / max(len(flow_times), 1), 2),
                    "average_total_frame_ms": round(sum(frame_times) / max(len(frame_times), 1), 2),
                    "cuda_enabled": detector.device_label.startswith("cuda"),
                    "device_name": self._device_name(),
                    "selected_analysis_mode": profile["mode"],
                    "input_size": profile.get("input_size"),
                    "frame_skip": analysis_interval,
                    "optical_flow_interval": optical_flow_interval,
                    "save_processed_video": save_processed_video,
                }
            )
            db.commit()
            asyncio.run(manager.broadcast("jobs", self._job_progress_payload(job)))
            asyncio.run(manager.broadcast(f"job:{job_id}", {"type": "job_log", "message": f"Analiz tamamlandi: {total_elapsed:.1f} sn"}))
        except Exception as exc:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.current_stage = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.utcnow()
                db.commit()
                asyncio.run(manager.broadcast("jobs", self._job_progress_payload(job)))
        finally:
            db.close()

    def _update_progress(self, db, job: AnalysisJob, frame_index: int, total_frames: int) -> None:
        job.progress = round(min((frame_index / max(total_frames, 1)) * 100, 99.0), 2)
        db.commit()

    def _job_progress_payload(self, job: AnalysisJob) -> dict:
        return {
            "type": "job_progress",
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "processed_frames": job.processed_frames,
            "skipped_frames": job.skipped_frames,
            "total_frames": job.total_frames,
            "current_stage": job.current_stage,
            "processed_url": public_static_path(job.processed_path),
            "original_url": public_static_path(job.original_path),
            "performance": json.loads(job.performance_json) if job.performance_json else None,
            "error_message": job.error_message,
        }

    def _device_name(self) -> str | None:
        try:
            import torch

            return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        except Exception:
            return None

    def _job_event_payload(self, event) -> dict:
        return {
            "type": "event",
            "severity": event.severity,
            "score": event.score,
            "job_id": event.analysis_job_id,
            "snapshot_url": public_static_path(event.snapshot_path),
            "created_at": event.created_at.isoformat(),
        }
