import logging
import os
import time

logger = logging.getLogger("progoz.notifications")

# Graceful import — system keeps running if firebase-admin is not installed
_fb_messaging = None
_FIREBASE_SDK_AVAILABLE = False
try:
    import firebase_admin
    from firebase_admin import credentials, messaging as _fb_messaging
    _FIREBASE_SDK_AVAILABLE = True
except ImportError:
    logger.warning("firebase-admin paketi yuklu degil. FCM bildirimleri devre disi.")


class NotificationService:
    def __init__(self) -> None:
        self._initialized = False
        self._last_sent: dict[str, float] = {}
        self._init_firebase()

    def _init_firebase(self) -> None:
        if not _FIREBASE_SDK_AVAILABLE:
            return
        try:
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
            if not os.path.exists(cred_path):
                logger.warning("Firebase credentials bulunamadi: %s", cred_path)
                return
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("Firebase basariyla baslatildi")
        except Exception as exc:
            logger.warning("Firebase baslatılamadi: %s", exc)

    @property
    def enabled(self) -> bool:
        return (
            self._initialized
            and os.getenv("FIREBASE_NOTIFICATIONS_ENABLED", "true").lower() == "true"
        )

    def _check_cooldown(self, key: str, seconds: int = 60) -> bool:
        """True döner → bildirim gönderilmeli. False → cooldown süresi dolmamış."""
        now = time.time()
        if now - self._last_sent.get(key, 0) < seconds:
            return False
        self._last_sent[key] = now
        return True

    def send_fight_alert(
        self,
        user_id: str,
        source_id: str,
        camera_name: str,
        score: float,
        level: str,
        timestamp: str,
        cooldown_seconds: int = 60,
    ) -> None:
        if not self.enabled:
            return
        min_score = float(os.getenv("FIGHT_ALERT_MIN_SCORE", "60"))
        if score < min_score:
            return
        if not self._check_cooldown(f"{source_id}_{level}", cooldown_seconds):
            return
        try:
            message = _fb_messaging.Message(
                notification=_fb_messaging.Notification(
                    title=f"⚠️ {level} Tespit Edildi!",
                    body=f"{camera_name} | Skor: {score:.0f} | {timestamp}",
                ),
                data={
                    "type": "fight_alert",
                    "camera_name": camera_name,
                    "score": str(score),
                    "level": level,
                    "timestamp": timestamp,
                },
                topic=f"user_{user_id}",
            )
            _fb_messaging.send(message)
            logger.info(
                "Kavga bildirimi gonderildi: user=%s level=%s score=%.0f",
                user_id, level, score,
            )
        except Exception as exc:
            logger.error("Kavga bildirimi gonderilemedi: %s", exc)

    def send_plate_alert(
        self,
        user_id: str,
        plate_text: str,
        camera_name: str,
        timestamp: str,
    ) -> None:
        if not self.enabled:
            return
        if os.getenv("PLATE_ALERT_ENABLED", "true").lower() != "true":
            return
        try:
            message = _fb_messaging.Message(
                notification=_fb_messaging.Notification(
                    title="🚗 Plaka Tespit Edildi",
                    body=f"{plate_text} | {camera_name} | {timestamp}",
                ),
                data={
                    "type": "plate_detected",
                    "plate_text": plate_text,
                    "camera_name": camera_name,
                    "timestamp": timestamp,
                },
                topic=f"user_{user_id}",
            )
            _fb_messaging.send(message)
            logger.info("Plaka bildirimi gonderildi: plate=%s user=%s", plate_text, user_id)
        except Exception as exc:
            logger.error("Plaka bildirimi gonderilemedi: %s", exc)

    def subscribe_user(self, user_id: str, fcm_token: str) -> dict:
        if not self.enabled:
            return {"subscribed": False, "reason": "Firebase devre disi"}
        try:
            topic = f"user_{user_id}"
            response = _fb_messaging.subscribe_to_topic([fcm_token], topic)
            logger.info(
                "FCM subscribe: user=%s topic=%s success=%d fail=%d",
                user_id, topic, response.success_count, response.failure_count,
            )
            return {
                "subscribed": True,
                "topic": topic,
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }
        except Exception as exc:
            logger.error("FCM subscribe hatasi: %s", exc)
            return {"subscribed": False, "reason": str(exc)}


notification_service = NotificationService()


# ---------------------------------------------------------------------------
# FastAPI router — POST /api/notifications/subscribe
# ---------------------------------------------------------------------------

from fastapi import APIRouter, Body, Depends  # noqa: E402

from app.schemas.common import ok  # noqa: E402
from app.services.auth_service import get_current_user  # noqa: E402

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/subscribe")
def subscribe_fcm(
    user_id: str = Body(..., embed=True),
    fcm_token: str = Body(..., embed=True),
):
    result = notification_service.subscribe_user(user_id, fcm_token)
    return ok(result, "FCM abonelik islendi.")
