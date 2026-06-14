import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth_routes, camera_routes, event_routes, incident_routes, plate_routes, stream_routes, system_routes, upload_routes
import app.services.notification_service as _notification_module
from app.config import get_settings
from app.database import init_db
from app.schemas.common import fail


settings = get_settings()
logger = logging.getLogger("progoz.startup")
app = FastAPI(title=settings.app_name, version="0.1.0")
plate_cleanup_scheduler = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.cors_origins,
        "http://localhost:59729",
        "http://localhost",
        "*",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


def _auto_start_cameras() -> None:
    """Background thread: start all enabled cameras after the server is ready."""
    import time as _time
    _time.sleep(3)  # Wait for server to fully initialize

    from app.database import SessionLocal
    from app.models.camera import Camera as CameraModel
    from app.services.camera_service import camera_runtime

    db = SessionLocal()
    try:
        cameras = db.query(CameraModel).filter(CameraModel.enabled == True).all()
        for cam in cameras:
            try:
                if cam.source_type == "webcam":
                    camera_runtime.start(cam.id, 0)
                    logger.warning("Auto-start webcam id=%s name=%s", cam.id, cam.name)
                elif cam.source_type == "rtsp" and cam.rtsp_url:
                    camera_runtime.start(cam.id, cam.rtsp_url)
                    logger.warning("Auto-start rtsp id=%s name=%s", cam.id, cam.name)
                elif cam.source_type == "web" and cam.rtsp_url:
                    from app.services.stream_extractor import extract_stream_url
                    stream_url = extract_stream_url(cam.rtsp_url)
                    camera_runtime.start(cam.id, stream_url)
                    logger.warning("Auto-start web id=%s name=%s", cam.id, cam.name)
            except Exception as exc:
                logger.warning("Auto-start basarisiz id=%s name=%s: %s", cam.id, cam.name, exc)
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    global plate_cleanup_scheduler
    settings.ensure_directories()
    init_db()
    try:
        from app.services.plate_service import run_deduplicate_once_global

        deleted = run_deduplicate_once_global()
        if deleted > 0:
            logger.warning("Baslangicta %d yinelenen plaka kaydi temizlendi.", deleted)
    except Exception as exc:
        logger.warning("Baslangic deduplication hatasi: %s", exc)
    try:
        from app.services.plate_service import start_plate_cleanup_scheduler

        plate_cleanup_scheduler = start_plate_cleanup_scheduler()
    except Exception as exc:
        logger.warning("Plaka cleanup scheduler baslatilamadi: %s", exc)
    try:
        import torch

        if torch.cuda.is_available():
            logger.warning("CUDA aktif: device=cuda:0 name=%s torch=%s", torch.cuda.get_device_name(0), torch.__version__)
        else:
            logger.warning("CUDA pasif: CPU fallback kullanilacak. torch=%s", torch.__version__)
    except Exception as exc:
        logger.warning("Torch/CUDA durumu okunamadi: %s", exc)
    import threading as _threading
    _threading.Thread(target=_auto_start_cameras, daemon=True).start()
    try:
        _svc = _notification_module.notification_service
        if _svc.enabled:
            logger.warning("Firebase FCM aktif: bildirimler gonderilecek.")
        else:
            logger.warning("Firebase FCM devre disi: bildirimler gonderilmeyecek.")
    except Exception as exc:
        logger.warning("Notification service durumu okunamadi: %s", exc)
    try:
        from app.core.plate_detector import get_plate_detector

        detector = get_plate_detector()
        logger.warning(
            "Plaka detector durumu: enabled=%s path=%s exists=%s loaded=%s device=%s error=%s",
            settings.plate_recognition_enabled,
            detector.model_path,
            detector.model_exists,
            detector.available,
            detector.device_label,
            detector.load_error,
        )
    except Exception as exc:
        logger.warning("Plaka detector durumu okunamadi: %s", exc)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=fail("validation_error", str(exc)))


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=fail("http_error", str(exc.detail)))


@app.exception_handler(Exception)
async def general_exception_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content=fail("server_error", str(exc)))


@app.get("/")
def root():
    return {"success": True, "data": {"name": settings.app_name, "docs": "/docs"}, "message": "PROGOZ API calisiyor."}


app.include_router(auth_routes.router, prefix=settings.api_prefix)
app.include_router(camera_routes.router, prefix=settings.api_prefix)
app.include_router(upload_routes.router, prefix=settings.api_prefix)
app.include_router(event_routes.router, prefix=settings.api_prefix)
app.include_router(incident_routes.router, prefix=settings.api_prefix)
app.include_router(plate_routes.router, prefix=settings.api_prefix)
app.include_router(system_routes.router, prefix=settings.api_prefix)
app.include_router(_notification_module.router, prefix=settings.api_prefix)
app.include_router(stream_routes.router)
