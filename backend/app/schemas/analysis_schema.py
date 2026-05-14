from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AnalysisJobRead(BaseModel):
    id: int
    filename: str
    original_path: str
    processed_path: Optional[str]
    status: str
    progress: float
    total_frames: int
    processed_frames: int
    skipped_frames: int = 0
    current_stage: str = "queued"
    analysis_mode: str = "fast"
    save_processed_video: int = 1
    debug_scoring: int = 0
    performance_json: Optional[str] = None
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]

    model_config = {"from_attributes": True}
