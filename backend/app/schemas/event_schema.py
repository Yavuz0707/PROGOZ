from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EventRead(BaseModel):
    id: int
    source_type: str
    camera_id: Optional[int]
    analysis_job_id: Optional[int]
    event_type: str
    severity: str
    score: float
    started_at: datetime
    ended_at: Optional[datetime]
    frame_index: Optional[int]
    person_ids: Optional[str]
    snapshot_path: Optional[str]
    clip_path: Optional[str]
    details_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

