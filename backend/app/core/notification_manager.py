from app.services.websocket_manager import manager
from app.utils.file_utils import public_static_path


class NotificationManager:
    async def publish_event(self, channel: str, event) -> None:
        await manager.broadcast(
            channel,
            {
                "type": "event",
                "severity": event.severity,
                "score": event.score,
                "camera_id": event.camera_id,
                "job_id": event.analysis_job_id,
                "snapshot_url": public_static_path(event.snapshot_path),
                "created_at": event.created_at.isoformat(),
            },
        )


notification_manager = NotificationManager()

