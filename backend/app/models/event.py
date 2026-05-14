from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(30), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    analysis_job_id = Column(Integer, ForeignKey("analysis_jobs.id"), nullable=True)
    event_type = Column(String(80), default="violence_anomaly", nullable=False)
    severity = Column(String(40), nullable=False)
    score = Column(Float, nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    frame_index = Column(Integer, nullable=True)
    person_ids = Column(String(120), nullable=True)
    snapshot_path = Column(String(700), nullable=True)
    clip_path = Column(String(700), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    camera = relationship("Camera", back_populates="events")
    analysis_job = relationship("AnalysisJob", back_populates="events")

