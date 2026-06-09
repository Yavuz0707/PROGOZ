from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(700), nullable=False)
    processed_path = Column(String(700), nullable=True)
    status = Column(String(40), default="queued", nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    total_frames = Column(Integer, default=0, nullable=False)
    processed_frames = Column(Integer, default=0, nullable=False)
    skipped_frames = Column(Integer, default=0, nullable=False)
    current_stage = Column(String(60), default="queued", nullable=False)
    analysis_mode = Column(String(40), default="fast", nullable=False)
    save_processed_video = Column(Integer, default=1, nullable=False)
    debug_scoring = Column(Integer, default=0, nullable=False)
    plate_recognition_enabled = Column(Integer, default=1, nullable=False)
    performance_json = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    events = relationship("Event", back_populates="analysis_job")
    plates = relationship("LicensePlate", back_populates="analysis_job")
