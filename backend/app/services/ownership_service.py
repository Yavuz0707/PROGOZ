from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.analysis_job import AnalysisJob
from app.models.camera import Camera
from app.models.user import User


def is_admin(user: User) -> bool:
    return getattr(user, "role", None) == "admin"


def filter_by_owner(query, model, user: User):
    if is_admin(user):
        return query
    return (
        query.outerjoin(Camera, model.camera_id == Camera.id)
        .outerjoin(AnalysisJob, model.analysis_job_id == AnalysisJob.id)
        .filter(or_(Camera.user_id == user.id, AnalysisJob.user_id == user.id))
    )


def filter_camera_owned(query, model, user: User):
    if is_admin(user):
        return query
    return query.join(Camera, model.camera_id == Camera.id).filter(Camera.user_id == user.id)


def get_owned_camera(db: Session, camera_id: int, user: User) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera or (not is_admin(user) and camera.user_id != user.id):
        raise HTTPException(status_code=404, detail="Kamera bulunamadi.")
    return camera


def get_owned_job(db: Session, job_id: int, user: User) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if not job or (not is_admin(user) and getattr(job, "user_id", None) != user.id):
        raise HTTPException(status_code=404, detail="Analiz isi bulunamadi.")
    return job


def ensure_owned_source(record, user: User, not_found_detail: str) -> None:
    if is_admin(user):
        return
    camera = getattr(record, "camera", None)
    if camera is not None and camera.user_id == user.id:
        return
    job = getattr(record, "analysis_job", None)
    if job is not None and getattr(job, "user_id", None) == user.id:
        return
    raise HTTPException(status_code=404, detail=not_found_detail)
