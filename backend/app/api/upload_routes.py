from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.video_processor import VideoProcessor
from app.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.event import Event
from app.models.incident import Incident
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


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    analysis_mode: str = Form("fast"),
    save_processed_video: bool = Form(False),
    debug_scoring: bool = Form(False),
    fast_result: bool = Form(False),
    db: Session = Depends(get_db),
):
    job = await save_upload_file(file, db)
    job.analysis_mode = analysis_mode
    job.save_processed_video = 0 if fast_result else int(save_processed_video)
    job.debug_scoring = int(debug_scoring)
    job.current_stage = "queued"
    db.commit()
    db.refresh(job)
    analysis_executor.submit(processor.process_upload_job, job.id)
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
    return ok(
        {
            "job": _job_payload(job),
            "events": [EventRead.model_validate(e).model_dump(mode="json") for e in events],
            "incidents": [incident_payload(item) for item in incidents],
        }
    )


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
    data["processed_video_exists"] = bool(job.processed_path and Path(job.processed_path).exists())
    data["processed_video_size"] = Path(job.processed_path).stat().st_size if job.processed_path and Path(job.processed_path).exists() else 0
    data["performance"] = None
    if job.performance_json:
        import json

        data["performance"] = json.loads(job.performance_json)
    return data
