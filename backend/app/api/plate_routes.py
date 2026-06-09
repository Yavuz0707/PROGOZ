from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import BASE_DIR, get_settings
from app.core.plate_recognition_pipeline import get_plate_pipeline
from app.database import get_db
from app.models.license_plate import LicensePlate
from app.schemas.common import ok
from app.services.auth_service import get_current_user, get_user_by_username_or_email, require_admin
from app.services.plate_service import cleanup_old_plates, cleanup_unreadable_plates, deduplicate_plates_global, delete_plate, export_plates_csv, list_plates, plate_payload, plate_stats


router = APIRouter(prefix="/plates", tags=["plates"])


def maybe_require_test_image_auth(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.plate_test_image_auth_required:
        return None
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kimlik dogrulama bilgileri gecersiz.", headers={"WWW-Authenticate": "Bearer"}) from exc
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kimlik dogrulama bilgileri gecersiz.", headers={"WWW-Authenticate": "Bearer"})
    user = get_user_by_username_or_email(db, username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kimlik dogrulama bilgileri gecersiz.", headers={"WWW-Authenticate": "Bearer"})
    return user


@router.get("", dependencies=[Depends(get_current_user)])
def get_plates(
    source_type: str | None = None,
    camera_id: int | None = None,
    analysis_job_id: int | None = None,
    plate: str | None = None,
    valid_only: bool = False,
    show_unreadable: bool = False,
    require_valid_format: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
):
    rows = list_plates(
        db,
        {
            "source_type": source_type,
            "camera_id": camera_id,
            "analysis_job_id": analysis_job_id,
            "plate": plate,
            "valid_only": valid_only,
            "show_unreadable": show_unreadable,
            "require_valid_format": require_valid_format,
            "date_from": date_from,
            "date_to": date_to,
            "min_confidence": min_confidence,
        },
    )
    return ok([plate_payload(row) for row in rows])


@router.get("/stats", dependencies=[Depends(get_current_user)])
def get_plate_stats(db: Session = Depends(get_db)):
    return ok(plate_stats(db))


@router.post("/test-image")
async def test_plate_image(_: object = Depends(maybe_require_test_image_auth), file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Gorsel dosyasi bos.")
    buffer = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise HTTPException(status_code=400, detail="Gorsel okunamadi. JPG/PNG gibi desteklenen bir dosya yukleyin.")
    pipeline = get_plate_pipeline()
    result = pipeline.analyze_image_for_debug(image)
    return ok(result)


@router.get("/by-video/{analysis_job_id}", dependencies=[Depends(get_current_user)])
def get_plates_by_video(analysis_job_id: int, db: Session = Depends(get_db)):
    rows = list_plates(db, {"analysis_job_id": analysis_job_id, "source_type": "video"})
    return ok([plate_payload(row) for row in rows])


@router.get("/by-camera/{camera_id}", dependencies=[Depends(get_current_user)])
def get_plates_by_camera(camera_id: int, db: Session = Depends(get_db)):
    rows = list_plates(db, {"camera_id": camera_id, "source_type": "camera"})
    return ok([plate_payload(row) for row in rows])


@router.get("/export/csv", dependencies=[Depends(get_current_user)])
def export_csv(db: Session = Depends(get_db)):
    rows = list_plates(db, {})
    target = BASE_DIR / "exports" / f"plates_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    export_plates_csv(db, rows, target)
    return FileResponse(path=target, media_type="text/csv", filename=Path(target).name)


@router.post("/deduplicate", dependencies=[Depends(get_current_user)])
def deduplicate_plates(db: Session = Depends(get_db)):
    deleted = deduplicate_plates_global(db)
    return ok({"deleted": deleted}, f"{deleted} yinelenen plaka kaydi temizlendi.")


@router.post("/cleanup", dependencies=[Depends(require_admin)])
def cleanup_plates(db: Session = Depends(get_db)):
    settings = get_settings()
    deleted = cleanup_old_plates(db, settings.plate_retention_days)
    return ok({"deleted": deleted, "retention_days": settings.plate_retention_days}, "Eski plaka kayitlari temizlendi.")


@router.post("/cleanup-unreadable", dependencies=[Depends(require_admin)])
def cleanup_unreadable(db: Session = Depends(get_db)):
    deleted = cleanup_unreadable_plates(db)
    return ok({"deleted": deleted}, "Okunamayan plaka kayitlari temizlendi.")


@router.get("/{plate_id}", dependencies=[Depends(get_current_user)])
def get_plate(plate_id: int, db: Session = Depends(get_db)):
    record = db.get(LicensePlate, plate_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plaka kaydi bulunamadi.")
    return ok(plate_payload(record))


@router.delete("/{plate_id}", dependencies=[Depends(require_admin)])
def remove_plate(plate_id: int, db: Session = Depends(get_db)):
    record = db.get(LicensePlate, plate_id)
    if not record:
        raise HTTPException(status_code=404, detail="Plaka kaydi bulunamadi.")
    delete_plate(db, record)
    return ok(message="Plaka kaydi silindi.")
