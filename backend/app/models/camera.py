from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    source_type = Column(String(30), nullable=False)
    rtsp_url = Column(String(500), nullable=True)
    location = Column(String(180), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    plate_recognition_enabled = Column(Boolean, default=True, nullable=False)
    plate_frame_interval = Column(Integer, default=10, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    events = relationship("Event", back_populates="camera")
    plates = relationship("LicensePlate", back_populates="camera")
