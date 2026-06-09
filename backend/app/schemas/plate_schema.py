from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PlateRead(BaseModel):
    id: int
    source_type: str
    camera_id: Optional[int] = None
    camera_name: Optional[str] = None
    analysis_job_id: Optional[int] = None
    video_filename: Optional[str] = None
    plate_text_raw: str
    plate_text_normalized: str
    is_valid_format: bool
    confidence: float
    ocr_confidence: float
    detection_confidence: float
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    first_seen_time_seconds: Optional[float] = None
    last_seen_time_seconds: Optional[float] = None
    frame_index: Optional[int] = None
    seen_count: int
    best_snapshot_path: Optional[str] = None
    best_snapshot_url: Optional[str] = None
    crop_path: Optional[str] = None
    crop_url: Optional[str] = None
    bbox_json: Optional[str] = None
    status: str
    recognition_source: str
    details_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
