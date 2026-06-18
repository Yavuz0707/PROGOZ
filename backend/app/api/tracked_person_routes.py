from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.camera import Camera
from app.models.tracked_person import TrackedPerson
from app.schemas.common import ok
from app.services.auth_service import get_current_user
from app.services.ownership_service import get_owned_camera, is_admin
from app.utils.file_utils import public_static_path

router = APIRouter(
    prefix="/tracked-persons",
    tags=["tracked-persons"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
def list_tracked_persons(
    camera_id: int | None = Query(None),
    limit: int = Query(60, ge=1, le=300),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Anomaliye karisip DB'ye kalici yazilmis kisileri (en yeni once) dondurur."""
    query = db.query(TrackedPerson)
    if camera_id is not None:
        get_owned_camera(db, camera_id, current_user)
        query = query.filter(TrackedPerson.camera_id == camera_id)
    elif not is_admin(current_user):
        query = query.join(Camera, TrackedPerson.camera_id == Camera.id).filter(Camera.user_id == current_user.id)
    rows = query.order_by(TrackedPerson.detected_at.desc()).limit(limit).all()
    items = [
        {
            "id": r.id,
            "camera_id": r.camera_id,
            "camera_name": r.camera_name,
            "track_id": r.track_id,
            "level": r.level,
            "score": r.score,
            "crop": public_static_path(r.crop_path),
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
        }
        for r in rows
    ]
    return ok({"items": items})
