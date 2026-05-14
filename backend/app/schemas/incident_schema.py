from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IncidentRead(BaseModel):
    id: int
    source_type: str
    camera_id: Optional[int]
    analysis_job_id: Optional[int]
    video_filename: Optional[str]
    severity: str
    status: str
    start_frame: Optional[int]
    end_frame: Optional[int]
    start_time_seconds: Optional[float]
    end_time_seconds: Optional[float]
    duration_seconds: float
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    max_score: float
    avg_score: float
    best_snapshot_path: Optional[str]
    best_snapshot_score: Optional[float]
    clip_path: Optional[str]
    involved_track_ids_json: Optional[str]
    score_timeline_json: Optional[str]
    details_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
