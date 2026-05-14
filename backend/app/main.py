import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth_routes, camera_routes, event_routes, incident_routes, stream_routes, system_routes, upload_routes
from app.config import get_settings
from app.database import init_db
from app.schemas.common import fail


settings = get_settings()
logger = logging.getLogger("progoz.startup")
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.on_event("startup")
def on_startup() -> None:
    settings.ensure_directories()
    init_db()
    try:
        import torch

        if torch.cuda.is_available():
            logger.warning("CUDA aktif: device=cuda:0 name=%s torch=%s", torch.cuda.get_device_name(0), torch.__version__)
        else:
            logger.warning("CUDA pasif: CPU fallback kullanilacak. torch=%s", torch.__version__)
    except Exception as exc:
        logger.warning("Torch/CUDA durumu okunamadi: %s", exc)


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
app.include_router(system_routes.router, prefix=settings.api_prefix)
app.include_router(stream_routes.router)
