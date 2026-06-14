import cv2
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.camera import Camera
from app.models.incident import Incident
from app.schemas.camera_schema import CameraCreate, CameraRead, CameraUpdate
from app.schemas.common import ok
from app.services.auth_service import get_current_user
from app.services.camera_service import camera_runtime
from app.services.incident_service import incident_payload


router = APIRouter(prefix="/cameras", tags=["cameras"], dependencies=[Depends(get_current_user)])


@router.get("")
def list_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).order_by(Camera.created_at.desc()).all()
    return ok([CameraRead.model_validate(c).model_dump(mode="json") for c in cameras])


@router.post("")
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    camera = Camera(**payload.model_dump())
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return ok(CameraRead.model_validate(camera).model_dump(mode="json"), "Kamera eklendi.")


@router.get("/devices")
def list_devices():
    devices = []
    for i in range(5):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    devices.append({"id": i, "name": f"Webcam ({i})", "type": "webcam"})
            cap.release()
        except Exception:
            continue
    return ok(devices)


@router.post("/webcam/start")
def start_webcam(device_id: int = Body(..., embed=True)):
    camera_runtime.start(device_id, device_id)
    return ok({"running": True, "camera_id": device_id}, "Webcam baslatildi.")


@router.post("/webcam/stop")
def stop_webcam(device_id: int = Body(..., embed=True)):
    camera_runtime.stop(device_id)
    return ok({"running": False}, "Webcam durduruldu.")


@router.get("/{camera_id}")
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Kamera bulunamadi.")
    return ok(CameraRead.model_validate(camera).model_dump(mode="json"))


@router.put("/{camera_id}")
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Kamera bulunamadi.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera, key, value)
    db.commit()
    db.refresh(camera)
    return ok(CameraRead.model_validate(camera).model_dump(mode="json"), "Kamera guncellendi.")


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Kamera bulunamadi.")
    camera_runtime.stop(camera_id)
    db.delete(camera)
    db.commit()
    return ok(message="Kamera silindi.")


@router.post("/{camera_id}/start")
def start_camera(camera_id: int, db: Session = Depends(get_db)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Kamera bulunamadi.")
    if camera.source_type == "webcam":
        source: str | int = 0
    elif camera.source_type == "web":
        if not camera.rtsp_url:
            raise HTTPException(status_code=400, detail="Web yayin URL'si eksik.")
        from app.services.stream_extractor import extract_stream_url
        try:
            source = extract_stream_url(camera.rtsp_url)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        source = camera.rtsp_url
    if source is None:
        raise HTTPException(status_code=400, detail="Kamera kaynagi eksik.")
    camera_runtime.start(camera_id, source)
    return ok({"running": True}, "Kamera analizi baslatildi.")


@router.post("/{camera_id}/stop")
def stop_camera(camera_id: int):
    camera_runtime.stop(camera_id)
    return ok({"running": False}, "Kamera analizi durduruldu.")


@router.get("/{camera_id}/incidents")
def camera_incidents(camera_id: int, db: Session = Depends(get_db)):
    incidents = db.query(Incident).filter(Incident.camera_id == camera_id).order_by(Incident.created_at.desc()).all()
    return ok([incident_payload(item) for item in incidents])
