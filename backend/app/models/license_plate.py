from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class LicensePlate(Base):
    __tablename__ = "license_plates"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(30), nullable=False)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    analysis_job_id = Column(Integer, ForeignKey("analysis_jobs.id"), nullable=True)
    video_filename = Column(String(255), nullable=True)
    plate_text_raw = Column(String(120), nullable=False)
    plate_text_normalized = Column(String(40), nullable=False)
    is_valid_format = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    ocr_confidence = Column(Float, default=0.0, nullable=False)
    detection_confidence = Column(Float, default=0.0, nullable=False)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    first_seen_time_seconds = Column(Float, nullable=True)
    last_seen_time_seconds = Column(Float, nullable=True)
    frame_index = Column(Integer, nullable=True)
    seen_count = Column(Integer, default=1, nullable=False)
    best_snapshot_path = Column(String(700), nullable=True)
    crop_path = Column(String(700), nullable=True)
    bbox_json = Column(Text, nullable=True)
    status = Column(String(40), default="uncertain", nullable=False)
    recognition_source = Column(String(80), default="local_detector_easyocr", nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    camera = relationship("Camera", back_populates="plates")
    analysis_job = relationship("AnalysisJob", back_populates="plates")


Index("ix_license_plates_plate_text_normalized", LicensePlate.plate_text_normalized)
Index("ix_license_plates_source_type", LicensePlate.source_type)
Index("ix_license_plates_camera_id", LicensePlate.camera_id)
Index("ix_license_plates_analysis_job_id", LicensePlate.analysis_job_id)
Index("ix_license_plates_created_at", LicensePlate.created_at)
Index("ix_license_plates_last_seen_at", LicensePlate.last_seen_at)
