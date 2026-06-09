import asyncio
import json
import logging
import queue
import threading
from datetime import datetime
from pathlib import Path
from time import perf_counter

import cv2

from app.config import get_settings
from app.core.alarm_manager import AlarmManager, cap_level
from app.core.detector import get_detector
from app.core.fight_classifier import FightClipBuffer, fuse_classifier_score, get_fight_classifier
from app.core.motion_analyzer import MotionAnalyzer
from app.core.plate_recognition_pipeline import get_plate_pipeline
from app.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.event import Event
from app.models.incident import Incident
from app.models.license_plate import LicensePlate
from app.services.event_service import create_event
from app.services.incident_service import IncidentTracker, incident_payload
from app.services.plate_service import plate_vote_buffer, upsert_plate_detection
from app.services.websocket_manager import manager
from app.utils.file_utils import public_static_path
from app.utils.ffmpeg_utils import convert_to_h264, ffmpeg_available

logger = logging.getLogger("progoz.video_processor")

_LEVEL_LABELS: dict[str, str] = {
    "KAVGA": "KAVGA",
    "OLASI_KAVGA": "OLASI KAVGA",
    "SUPHELI": "ŞÜPHELİ",
    "NORMAL": "NORMAL",
}


class AsyncBroadcaster:
    """Persistent asyncio event loop in a dedicated thread for non-blocking WebSocket broadcasts.

    Replaces per-call asyncio.run() which recreates the event loop on every frame,
    causing severe throughput degradation under high frame rates.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ws-broadcaster")
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def broadcast(self, channel: str, data: dict) -> None:
        asyncio.run_coroutine_threadsafe(manager.broadcast(channel, data), self._loop)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)


class VideoProcessor:
    def __init__(self) -> None:
        self.settings = get_settings()

    def process_upload_job(self, job_id: int) -> None:
        db = SessionLocal()
        detector = get_detector()
        raw_output: Path | None = None
        broadcaster = AsyncBroadcaster()

        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if not job:
                return

            profile = self.settings.analysis_profile(job.analysis_mode)
            save_processed_video = bool(job.save_processed_video) and bool(profile.get("save_processed_video", True))
            analyzer = MotionAnalyzer(sensitivity=self.settings.sensitivity, debug_scoring=bool(job.debug_scoring))
            alarm = AlarmManager()
            fight_classifier = get_fight_classifier()
            fight_buffer = FightClipBuffer(maxlen=self.settings.fight_classifier_clip_len)
            last_classifier_probability: float | None = None
            plate_pipeline = get_plate_pipeline() if bool(job.plate_recognition_enabled) else None
            if plate_pipeline:
                plate_pipeline.reset_stats()
                logger.warning(
                    "Plate recognition job=%s enabled=%s available=%s detector_loaded=%s ocr_loaded=%s interval_mode=%s plate_frame_interval=%s",
                    job_id,
                    bool(job.plate_recognition_enabled),
                    plate_pipeline.available,
                    plate_pipeline.detector.available,
                    bool(plate_pipeline.ocr and plate_pipeline.ocr.available),
                    job.analysis_mode,
                    self.settings.plate_frame_interval(job.analysis_mode),
                )

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
                broadcaster.broadcast("jobs", self._job_progress_payload(job))
                broadcaster.broadcast(
                    f"job:{job_id}",
                    {"type": "job_log", "message": "Analiz baslatilamadi; YOLO modeli yuklenemedi."},
                )
                return
            else:
                job.error_message = None
            db.commit()

            input_path = Path(job.original_path)

            # Read video metadata once, then release
            cap_meta = cv2.VideoCapture(str(input_path))
            if not cap_meta.isOpened():
                raise RuntimeError("Video dosyasi OpenCV ile acilamadi.")
            fps = cap_meta.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap_meta.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            width = int(cap_meta.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
            height = int(cap_meta.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
            cap_meta.release()

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

            # Pre-compute intervals outside the hot loop
            analysis_interval = max(
                1,
                int(profile.get("frame_skip", self.settings.frame_skip)),
                int(profile.get("yolo_interval", self.settings.frame_skip)),
            )
            optical_flow_interval = max(1, int(profile.get("optical_flow_interval", analysis_interval)))

            # Resolution-based frame skip: higher resolution → skip more frames
            if height >= 1080:
                analysis_interval = max(analysis_interval, 3)
            elif height >= 720:
                analysis_interval = max(analysis_interval, 2)

            plate_interval = self.settings.plate_frame_interval(profile["mode"])

            frame_index = 0
            last_event_by_pair: dict[tuple, int] = {}
            start = perf_counter()
            yolo_times: list[float] = []
            flow_times: list[float] = []
            frame_times: list[float] = []

            db.query(Event).filter(Event.analysis_job_id == job_id).delete()
            db.query(Incident).filter(Incident.analysis_job_id == job_id).delete()
            db.query(LicensePlate).filter(LicensePlate.analysis_job_id == job_id).delete()
            db.commit()

            incident_tracker = IncidentTracker(
                db, "video", analysis_job_id=job_id, video_filename=job.filename, fps=fps
            )
            plate_count = 0
            job_cancelled = False

            # Thread 1: Frame reader → fills frame_queue
            frame_queue: queue.Queue = queue.Queue(maxsize=64)

            def _read_frames() -> None:
                cap_r = cv2.VideoCapture(str(input_path))
                while True:
                    ret_r, frame_r = cap_r.read()
                    if not ret_r:
                        break
                    frame_queue.put(frame_r)
                cap_r.release()
                frame_queue.put(None)  # sentinel

            reader_thread = threading.Thread(target=_read_frames, daemon=True, name=f"reader-{job_id}")
            reader_thread.start()

            # Main loop: Thread 2 (this thread) — YOLO + analysis + DB writes
            while True:
                frame = frame_queue.get()
                if frame is None:
                    break

                frame_index += 1
                fight_buffer.append(frame)

                # Plate detection (every plate_interval frames) — vote buffer only, no DB writes
                if plate_pipeline and plate_pipeline.available and frame_index % plate_interval == 0:
                    try:
                        plate_pipeline.stats["sampled_frames"] += 1
                        plate_pipeline.stats["detector_called"] += 1
                        for detection in plate_pipeline.detector.detect(frame):
                            if detection.confidence < self.settings.plate_detector_confidence:
                                continue
                            plate_pipeline.stats["detections"] += 1
                            crop = plate_pipeline._crop(frame, detection)
                            plate_pipeline.stats["ocr_attempted"] += 1
                            ocr_candidates = (
                                plate_pipeline.ocr.read_all(crop)
                                if plate_pipeline.ocr and plate_pipeline.ocr.available
                                else []
                            )
                            plate_pipeline.stats["ocr_raw_text_count"] += len(ocr_candidates)
                            plate_pipeline.stats["normalized_candidate_count"] += sum(
                                1 for c in ocr_candidates if c.text.normalized_plate
                            )
                            ocr_result = ocr_candidates[0] if ocr_candidates else None
                            if not ocr_result or not plate_pipeline._should_save_ocr_result(ocr_result):
                                plate_pipeline.stats["skipped_unreadable_count"] += 1
                                if not ocr_result:
                                    plate_pipeline.stats["unreadable_plate_count"] += 1
                                continue
                            crop_path = plate_pipeline._save_image(
                                crop, "crop", "video", None, job_id, frame_index
                            )
                            confidence = (
                                min(detection.confidence, ocr_result.confidence)
                                if ocr_result.confidence > 0
                                else detection.confidence
                            )
                            if ocr_result.text.is_valid_format:
                                plate_pipeline.stats["readable_plate_count"] += 1
                            current_best = plate_vote_buffer.add_vote(
                                job_id,
                                ocr_result.text.normalized_plate or ocr_result.text.raw_text or "",
                                confidence,
                                crop_path,
                            )
                            if current_best:
                                broadcaster.broadcast(
                                    f"job:{job_id}",
                                    {
                                        "type": "plate_update",
                                        "plate_text": current_best["text"],
                                        "confidence": round(current_best["confidence"], 3),
                                        "seen_count": current_best["count"],
                                        "crop_url": public_static_path(current_best["crop_path"]),
                                        "source_type": "video",
                                        "analysis_job_id": job_id,
                                        "time_seconds": round(frame_index / fps, 2) if fps else None,
                                    },
                                )
                    except Exception as exc:
                        logger.warning("Frame %d plaka tespiti hatasi: %s", frame_index, exc)

                run_inference = frame_index % analysis_interval == 0
                if run_inference:
                    frame_start = perf_counter()

                    try:
                        detections = detector.detect_and_track(frame, int(profile.get("input_size", self.settings.input_size)))
                    except Exception as exc:
                        logger.warning("Frame %d YOLO hatasi, atlaniyor: %s", frame_index, exc)
                        job.skipped_frames += 1
                        if frame_index % 10 == 0:
                            self._update_progress(db, job, frame_index, total_frames)
                            broadcaster.broadcast("jobs", self._job_progress_payload(job))
                        continue

                    try:
                        optical_flow_enabled = frame_index % optical_flow_interval == 0
                        _, score_info = analyzer.analyze(frame, detections, frame_index, optical_flow_enabled=optical_flow_enabled)
                    except Exception as exc:
                        logger.warning("Frame %d hareket analizi hatasi, atlaniyor: %s", frame_index, exc)
                        job.skipped_frames += 1
                        continue

                    if (
                        fight_classifier.available
                        and frame_index % max(1, self.settings.fight_classifier_interval) == 0
                        and fight_buffer.ready(fight_classifier.clip_len)
                    ):
                        try:
                            last_classifier_probability = fight_classifier.predict(fight_buffer.latest(fight_classifier.clip_len))
                        except Exception as exc:
                            logger.warning("Frame %d kavga siniflandirici hatasi: %s", frame_index, exc)

                    try:
                        score_info = fuse_classifier_score(score_info, last_classifier_probability)
                        level, smoothed, consecutive = alarm.update(score_info["score"])
                        level = cap_level(level, score_info.get("label", "NORMAL"))
                        involved_ids = (
                            set(score_info.get("pair") or []) if self.settings.only_highlight_involved_persons else None
                        )
                        annotated = detector.annotate(frame, detections, smoothed, level, score_info.get("reasons", []), involved_ids)
                    except Exception as exc:
                        logger.warning("Frame %d skor/annotation hatasi, atlaniyor: %s", frame_index, exc)
                        job.skipped_frames += 1
                        continue

                    if writer is not None:
                        try:
                            writer.write(annotated)
                        except Exception as exc:
                            logger.warning("Frame %d video yazma hatasi: %s", frame_index, exc)

                    try:
                        incident = incident_tracker.update(frame_index, smoothed, level, score_info, annotated)
                        if incident:
                            broadcaster.broadcast(f"job:{job_id}", {"type": "incident", **incident_payload(incident)})
                    except Exception as exc:
                        logger.warning("Frame %d olay takip hatasi: %s", frame_index, exc)
                        incident = None

                    yolo_times.append(detector.last_inference_ms)
                    flow_times.append(analyzer.last_optical_flow_ms)
                    frame_times.append((perf_counter() - frame_start) * 1000)
                    job.processed_frames += 1

                    # Per-frame score update for real-time frontend chart
                    broadcaster.broadcast(
                        f"job:{job_id}",
                        {
                            "type": "frame_score",
                            "frame_number": frame_index,
                            "timestamp_sec": round(frame_index / fps, 2) if fps else 0,
                            "fight_score": round(smoothed, 1),
                            "fight_label": _LEVEL_LABELS.get(level, level),
                            "plates_detected": [],
                            "event_detected": incident is not None,
                        },
                    )

                    pair_key = tuple(score_info.get("pair") or ("unknown",))
                    cooldown_frames = int(fps * self.settings.cooldown_seconds)
                    last_pair_event = last_event_by_pair.get(pair_key, -999999)
                    threshold_ok = (
                        level in {"SUPHELI", "OLASI_KAVGA", "KAVGA"}
                        and smoothed >= self.settings.alarm_thresholds[level]
                    )
                    if (
                        self.settings.save_frame_level_events
                        and threshold_ok
                        and frame_index - last_pair_event > cooldown_frames
                    ):
                        try:
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
                            broadcaster.broadcast(f"job:{job_id}", self._job_event_payload(event))
                        except Exception as exc:
                            logger.warning("Frame %d olay kayit hatasi: %s", frame_index, exc)
                else:
                    job.skipped_frames += 1

                if frame_index % 10 == 0 or (total_frames > 0 and frame_index == total_frames):
                    from app.api.upload_routes import is_cancelled
                    if is_cancelled(job_id):
                        job_cancelled = True
                        broadcaster.broadcast(
                            f"job:{job_id}",
                            {
                                "type": "analysis_cancelled",
                                "processed_frames": job.processed_frames,
                                "total_frames": total_frames,
                            },
                        )
                        break
                    self._update_progress(db, job, frame_index, total_frames)
                    broadcaster.broadcast("jobs", self._job_progress_payload(job))

            if job_cancelled:
                try:
                    while True:
                        frame_queue.get_nowait()
                except queue.Empty:
                    pass
            reader_thread.join(timeout=5)

            # Save vote-buffer winner as the single plate record for this job (no DB writes during analysis)
            vote_winner: dict | None = None
            if plate_pipeline:
                try:
                    vote_winner = plate_vote_buffer.get_final_winner(job_id, min_votes=1)
                    if vote_winner and vote_winner.get("text"):
                        upsert_plate_detection(
                            db,
                            source_type="video",
                            analysis_job_id=job_id,
                            video_filename=job.filename,
                            plate_text_raw=vote_winner["text"],
                            plate_text_normalized=vote_winner["text"],
                            is_valid_format=True,
                            confidence=vote_winner["confidence"],
                            ocr_confidence=vote_winner["confidence"],
                            detection_confidence=vote_winner["confidence"],
                            crop_path=vote_winner["crop_path"],
                            recognition_source="vote_buffer_winner",
                            details={"seen_count": vote_winner["seen_count"]},
                        )
                        plate_count = vote_winner["seen_count"]
                        plate_pipeline.stats["plates_saved"] += 1
                except Exception as exc:
                    logger.warning("Job %d vote winner DB yazma hatasi: %s", job_id, exc)
                finally:
                    plate_vote_buffer.clear_job(job_id)

            try:
                broadcaster.broadcast(
                    f"job:{job_id}",
                    {
                        "type": "plates_finalized",
                        "final_plate": vote_winner["text"] if vote_winner else None,
                        "confidence": round(vote_winner["confidence"], 3) if vote_winner else None,
                        "seen_count": vote_winner["seen_count"] if vote_winner else 0,
                        "crop_url": public_static_path(vote_winner["crop_path"]) if vote_winner else None,
                    },
                )
            except Exception as exc:
                logger.warning("Job %d plates_finalized hatasi: %s", job_id, exc)

            if job_cancelled:
                from app.api.upload_routes import cancelled_jobs
                cancelled_jobs.discard(job_id)
                incident = incident_tracker.finalize()
                if incident:
                    broadcaster.broadcast(f"job:{job_id}", {"type": "incident", **incident_payload(incident)})
                if writer is not None:
                    writer.release()
                db.refresh(job)
                if job.finished_at is None:
                    job.finished_at = datetime.utcnow()
                db.commit()
                broadcaster.broadcast("jobs", self._job_progress_payload(job))
                broadcaster.broadcast(
                    f"job:{job_id}",
                    {"type": "job_log", "message": "Analiz kullanici tarafindan durduruldu."},
                )
                return

            broadcaster.broadcast(
                f"job:{job_id}",
                {
                    "type": "analysis_complete",
                    "total_frames": total_frames if total_frames > 0 else frame_index,
                    "processed_frames": job.processed_frames,
                    "skipped_frames": job.skipped_frames,
                    "duration_sec": round(frame_index / fps if fps else 0, 2),
                },
            )

            incident = incident_tracker.finalize()
            if incident:
                broadcaster.broadcast(f"job:{job_id}", {"type": "incident", **incident_payload(incident)})

            if writer is not None:
                writer.release()

            analysis_elapsed = perf_counter() - start
            final_path = None
            encoding_elapsed = 0.0

            if (
                save_processed_video
                and raw_output
                and raw_output.exists()
                and raw_output.stat().st_size > 0
                and ffmpeg_available()
            ):
                job.status = "encoding"
                job.current_stage = "encoding"
                job.progress = 99.0
                db.commit()
                broadcaster.broadcast("jobs", self._job_progress_payload(job))
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
                    "plate_recognition_enabled": bool(job.plate_recognition_enabled),
                    "plate_frame_interval": plate_interval,
                    "plate_count": plate_count,
                    "plate_pipeline": plate_pipeline.stats if plate_pipeline else None,
                    "plate_detector_called_count": (plate_pipeline.stats.get("detector_called") if plate_pipeline else 0),
                    "plate_detection_count": (plate_pipeline.stats.get("detections") if plate_pipeline else 0),
                    "ocr_attempt_count": (plate_pipeline.stats.get("ocr_attempted") if plate_pipeline else 0),
                    "ocr_raw_text_count": (plate_pipeline.stats.get("ocr_raw_text_count") if plate_pipeline else 0),
                    "normalized_candidate_count": (plate_pipeline.stats.get("normalized_candidate_count") if plate_pipeline else 0),
                    "readable_plate_count": (plate_pipeline.stats.get("readable_plate_count") if plate_pipeline else 0),
                    "unreadable_plate_count": (plate_pipeline.stats.get("unreadable_plate_count") if plate_pipeline else 0),
                    "saved_plate_count": (plate_pipeline.stats.get("plates_saved") if plate_pipeline else 0),
                    "skipped_unreadable_count": (plate_pipeline.stats.get("skipped_unreadable_count") if plate_pipeline else 0),
                }
            )
            db.commit()

            if plate_pipeline:
                logger.warning("Plate recognition summary job=%s stats=%s", job_id, plate_pipeline.stats)

            broadcaster.broadcast("jobs", self._job_progress_payload(job))
            broadcaster.broadcast(
                f"job:{job_id}",
                {"type": "job_log", "message": f"Analiz tamamlandi: {total_elapsed:.1f} sn"},
            )

        except Exception as exc:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.current_stage = "failed"
                job.error_message = str(exc)
                job.finished_at = datetime.utcnow()
                db.commit()
                broadcaster.broadcast("jobs", self._job_progress_payload(job))
        finally:
            broadcaster.stop()
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
