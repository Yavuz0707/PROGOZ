import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.event import Event


def create_event(
    db: Session,
    *,
    source_type: str,
    severity: str,
    score: float,
    camera_id: Optional[int] = None,
    analysis_job_id: Optional[int] = None,
    frame_index: Optional[int] = None,
    person_ids: Optional[str] = None,
    snapshot_path: Optional[str] = None,
    clip_path: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> Event:
    event = Event(
        source_type=source_type,
        camera_id=camera_id,
        analysis_job_id=analysis_job_id,
        event_type="violence_anomaly",
        severity=severity,
        score=float(score),
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        frame_index=frame_index,
        person_ids=person_ids,
        snapshot_path=snapshot_path,
        clip_path=clip_path,
        details_json=json.dumps(details or {}, ensure_ascii=False),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

