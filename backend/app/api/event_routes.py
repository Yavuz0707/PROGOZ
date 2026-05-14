import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event import Event
from app.schemas.common import ok
from app.schemas.event_schema import EventRead
from app.services.auth_service import get_current_user
from app.utils.file_utils import public_static_path


router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_events(
    severity: str | None = None,
    camera_id: int | None = None,
    video_job_id: int | None = None,
    min_score: float | None = None,
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if severity:
        query = query.filter(Event.severity == severity)
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if video_job_id:
        query = query.filter(Event.analysis_job_id == video_job_id)
    if min_score is not None:
        query = query.filter(Event.score >= min_score)
    if start_date:
        query = query.filter(Event.created_at >= start_date)
    if end_date:
        query = query.filter(Event.created_at <= end_date)
    events = query.order_by(Event.created_at.desc()).limit(500).all()
    return ok([_event_payload(e) for e in events])


@router.get("/stats")
def event_stats(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    counts = {"KAVGA": 0, "OLASI_KAVGA": 0, "SUPHELI": 0, "NORMAL": 0}
    for event in events:
        counts[event.severity] = counts.get(event.severity, 0) + 1
    return ok({"total": len(events), "by_severity": counts})


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    events = db.query(Event).order_by(Event.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "source_type", "severity", "score", "camera_id", "analysis_job_id", "created_at"])
    for e in events:
        writer.writerow([e.id, e.source_type, e.severity, e.score, e.camera_id, e.analysis_job_id, e.created_at])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=events.csv"})


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Olay bulunamadi.")
    return ok(_event_payload(event))


@router.delete("/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Olay bulunamadi.")
    db.delete(event)
    db.commit()
    return ok(message="Olay silindi.")


def _event_payload(event: Event) -> dict:
    data = EventRead.model_validate(event).model_dump(mode="json")
    data["snapshot_url"] = public_static_path(event.snapshot_path)
    data["clip_url"] = public_static_path(event.clip_path)
    return data

