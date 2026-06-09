from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.video_processor import VideoProcessor
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.event import Event
from app.models.incident import Incident
from app.models.license_plate import LicensePlate
from app.schemas.analysis_schema import AnalysisJobRead
from app.schemas.common import ok
from app.schemas.event_schema import EventRead
from app.services.auth_service import get_current_user
from app.services.incident_service import incident_payload
from app.services.upload_service import save_upload_file
from app.utils.file_utils import public_static_path


router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[Depends(get_current_user)])
processor = VideoProcessor()
analysis_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="progoz-analysis")
logger = logging.getLogger("progoz.upload")

cancelled_jobs: set[int] = set()


def cancel_job(job_id: int) -> None:
    cancelled_jobs.add(job_id)


def is_cancelled(job_id: int) -> bool:
    return job_id in cancelled_jobs


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    analysis_mode: str = Form("fast"),
    save_processed_video: Any = Form(False),
    debug_scoring: Any = Form(False),
    debug_log: Any = Form(False),
    fast_result: Any = Form(False),
    only_incidents: Any = Form(True),
    plate_recognition_enabled: Any = Form(True),
    db: Session = Depends(get_db),
):
    save_processed_video_value = _parse_bool(save_processed_video)
    only_incidents_value = _parse_bool(only_incidents) or _parse_bool(fast_result)
    debug_value = _parse_bool(debug_scoring) or _parse_bool(debug_log)
    plate_enabled_value = _parse_bool(plate_recognition_enabled)
    logger.warning(
        "upload endpoint called filename=%s analysis_mode=%s save_processed_video=%s plate_recognition_enabled=%s only_incidents=%s debug_log=%s",
        file.filename,
        analysis_mode,
        save_processed_video_value,
        plate_enabled_value,
        only_incidents_value,
        debug_value,
    )
    job = await save_upload_file(file, db)
    job.analysis_mode = analysis_mode
    job.save_processed_video = 0 if only_incidents_value else int(save_processed_video_value)
    job.debug_scoring = int(debug_value)
    job.plate_recognition_enabled = int(plate_enabled_value)
    job.current_stage = "queued"
    db.commit()
    db.refresh(job)
    logger.warning("created analysis job_id=%s filename=%s", job.id, job.filename)
    analysis_executor.submit(processor.process_upload_job, job.id)
    logger.warning("background task started job_id=%s", job.id)
    return ok(_job_payload(job), "Video kaydedildi, analiz baslatildi.")


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(AnalysisJob).order_by(AnalysisJob.id.desc()).all()
    return ok([_job_payload(job) for job in jobs])


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analiz isi bulunamadi.")
    return ok(_job_payload(job))


@router.get("/jobs/{job_id}/result")
def get_job_result(job_id: int, db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analiz isi bulunamadi.")
    events = db.query(Event).filter(Event.analysis_job_id == job_id).order_by(Event.created_at.desc()).all()
    incidents = db.query(Incident).filter(Incident.analysis_job_id == job_id).order_by(Incident.created_at.desc()).all()
    plates = db.query(LicensePlate).filter(LicensePlate.analysis_job_id == job_id).order_by(LicensePlate.last_seen_time_seconds.asc()).all()
    return ok(
        {
            "job": _job_payload(job),
            "events": [EventRead.model_validate(e).model_dump(mode="json") for e in events],
            "incidents": [incident_payload(item) for item in incidents],
            "plates": [{"id": plate.id, "plate_text_normalized": plate.plate_text_normalized} for plate in plates],
        }
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_analysis(job_id: int, db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analiz isi bulunamadi.")
    cancel_job(job_id)
    job.status = "cancelled"
    job.current_stage = "cancelled"
    job.finished_at = datetime.utcnow()
    db.commit()
    return ok({"job_id": job_id}, "Analiz durduruldu.")


@router.get("/jobs/{job_id}/incidents")
def get_job_incidents(job_id: int, db: Session = Depends(get_db)):
    incidents = db.query(Incident).filter(Incident.analysis_job_id == job_id).order_by(Incident.created_at.desc()).all()
    return ok([incident_payload(item) for item in incidents])


def _job_payload(job: AnalysisJob) -> dict:
    data = AnalysisJobRead.model_validate(job).model_dump(mode="json")
    data["processed_url"] = public_static_path(job.processed_path)
    data["original_url"] = public_static_path(job.original_path)
    data["current_stage"] = job.status if job.current_stage == "queued" and job.status != "queued" else job.current_stage
    data["skipped_frames"] = job.skipped_frames
    data["plate_recognition_enabled"] = job.plate_recognition_enabled
    data["plate_count"] = len(job.plates) if getattr(job, "plates", None) is not None else 0
    data["processed_video_exists"] = bool(job.processed_path and Path(job.processed_path).exists())
    data["processed_video_size"] = Path(job.processed_path).stat().st_size if job.processed_path and Path(job.processed_path).exists() else 0
    data["performance"] = None
    if job.performance_json:
        import json

        data["performance"] = json.loads(job.performance_json)
    return data


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on", "evet"}
