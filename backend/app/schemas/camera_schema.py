from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CameraBase(BaseModel):
    name: str
    source_type: str = "rtsp"
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    enabled: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[str] = None
    rtsp_url: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None


class CameraRead(CameraBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

