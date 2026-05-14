from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.incident import Incident
from app.schemas.common import ok
from app.services.auth_service import get_current_user
from app.services.incident_service import incident_payload


router = APIRouter(prefix="/incidents", tags=["incidents"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_incidents(
    source_type: str | None = None,
    camera_id: int | None = None,
    analysis_job_id: int | None = None,
    severity: str | None = None,
    status: str | None = None,
    min_score: float | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if source_type:
        query = query.filter(Incident.source_type == source_type)
    if camera_id:
        query = query.filter(Incident.camera_id == camera_id)
    if analysis_job_id:
        query = query.filter(Incident.analysis_job_id == analysis_job_id)
    if severity:
        query = query.filter(Incident.severity == severity)
    if status:
        query = query.filter(Incident.status == status)
    if min_score is not None:
        query = query.filter(Incident.max_score >= min_score)
    if date_from:
        query = query.filter(Incident.created_at >= date_from)
    if date_to:
        query = query.filter(Incident.created_at <= date_to)
    incidents = query.order_by(Incident.created_at.desc()).limit(500).all()
    return ok([incident_payload(item) for item in incidents])


@router.get("/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident bulunamadi.")
    return ok(incident_payload(incident))


@router.put("/{incident_id}/status")
def update_status(incident_id: int, payload: dict, db: Session = Depends(get_db)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident bulunamadi.")
    status = payload.get("status")
    if status not in {"confirmed", "false_positive", "ignored"}:
        raise HTTPException(status_code=400, detail="Gecersiz incident status.")
    incident.status = status
    db.commit()
    db.refresh(incident)
    return ok(incident_payload(incident), "Incident durumu guncellendi.")
