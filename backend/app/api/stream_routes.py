import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.services.camera_service import camera_runtime
from app.services.websocket_manager import manager


router = APIRouter(tags=["stream"])


@router.websocket("/ws/live/{camera_id}")
async def live_ws(websocket: WebSocket, camera_id: int):
    channel = f"live:{camera_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/ws/jobs")
async def jobs_ws(websocket: WebSocket):
    await manager.connect("jobs", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("jobs", websocket)


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: int):
    channel = f"job:{job_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.get("/api/stream/{camera_id}/mjpeg")
def mjpeg_stream(camera_id: int):
    def gen():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        last_frame: bytes | None = None
        target_interval = 1.0 / 25  # cap MJPEG output at 25 fps
        while camera_runtime.is_running(camera_id):
            t0 = time.monotonic()
            frame = camera_runtime.latest_jpeg(camera_id)
            if frame is not None and frame is not last_frame:
                yield boundary + frame + b"\r\n"
                last_frame = frame
            elapsed = time.monotonic() - t0
            wait = target_interval - elapsed
            time.sleep(max(wait, 0.008))  # never sleep less than 8 ms

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
