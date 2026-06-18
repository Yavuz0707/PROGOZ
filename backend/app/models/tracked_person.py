from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class TrackedPerson(Base):
    """Anomaliye karisan (flag'lenmis) bir kisinin kalici kaydi.

    Canli akista her track ID 60sn'lik gecici bellekte tutulur; yalnizca bir
    anomaliye (KAVGA/OLASI_KAVGA/SUPHELI) karisirsa buraya kalici yazilir.
    Karismayan kisilerin gecici crop'lari 60sn sonra silinir (DB'ye yazilmaz).
    """

    __tablename__ = "tracked_persons"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, nullable=True, index=True)
    camera_name = Column(String(120), nullable=True)
    track_id = Column(Integer, nullable=False)
    level = Column(String(40), nullable=False, default="NORMAL")
    score = Column(Float, nullable=True)
    crop_path = Column(String(700), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
