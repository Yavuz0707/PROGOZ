from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import SessionLocal, init_db
from app.models.event import Event
from app.services.event_service import create_event


def test_create_event_persists():
    init_db()
    db = SessionLocal()
    try:
        event = create_event(db, source_type="video", severity="SUPHELI", score=42.5, frame_index=12)
        saved = db.get(Event, event.id)
        assert saved is not None
        assert saved.severity == "SUPHELI"
    finally:
        db.close()

