from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(30), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    analysis_job_id = Column(Integer, ForeignKey("analysis_jobs.id"), nullable=True)
    video_filename = Column(String(255), nullable=True)
    severity = Column(String(40), nullable=False)
    status = Column(String(40), default="confirmed", nullable=False)
    start_frame = Column(Integer, nullable=True)
    end_frame = Column(Integer, nullable=True)
    start_time_seconds = Column(Float, nullable=True)
    end_time_seconds = Column(Float, nullable=True)
    duration_seconds = Column(Float, default=0.0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    max_score = Column(Float, nullable=False)
    avg_score = Column(Float, nullable=False)
    best_snapshot_path = Column(String(700), nullable=True)
    best_snapshot_score = Column(Float, nullable=True)
    clip_path = Column(String(700), nullable=True)
    involved_track_ids_json = Column(Text, nullable=True)
    score_timeline_json = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    camera = relationship("Camera")
    analysis_job = relationship("AnalysisJob")
