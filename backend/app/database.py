from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import analysis_job, camera, event, incident, license_plate, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    _mark_orphan_jobs_failed()


def _mark_orphan_jobs_failed() -> None:
    """On startup, mark any jobs stuck in running/queued state as failed.

    Prevents the frontend from reconnecting to jobs that will never finish
    because the server process that owned them is gone.
    """
    from datetime import datetime

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE analysis_jobs "
                "SET status = 'failed', current_stage = 'failed', "
                "error_message = 'Sunucu yeniden baslatildi', "
                "finished_at = :now "
                "WHERE status IN ('running', 'queued')"
            ),
            {"now": datetime.utcnow().isoformat()},
        )


def _migrate_sqlite() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "analysis_jobs" not in inspector.get_table_names():
        return
    job_existing = {column["name"] for column in inspector.get_columns("analysis_jobs")}
    job_columns = {
        "skipped_frames": "INTEGER NOT NULL DEFAULT 0",
        "current_stage": "VARCHAR(60) NOT NULL DEFAULT 'queued'",
        "analysis_mode": "VARCHAR(40) NOT NULL DEFAULT 'fast'",
        "save_processed_video": "INTEGER NOT NULL DEFAULT 1",
        "debug_scoring": "INTEGER NOT NULL DEFAULT 0",
        "plate_recognition_enabled": "INTEGER NOT NULL DEFAULT 1",
        "performance_json": "TEXT",
    }
    with engine.begin() as connection:
        for name, definition in job_columns.items():
            if name not in job_existing:
                connection.execute(text(f"ALTER TABLE analysis_jobs ADD COLUMN {name} {definition}"))
        if "cameras" in inspector.get_table_names():
            camera_existing = {column["name"] for column in inspector.get_columns("cameras")}
            camera_columns = {
                "plate_recognition_enabled": "BOOLEAN NOT NULL DEFAULT 1",
                "plate_frame_interval": "INTEGER NOT NULL DEFAULT 10",
            }
            for name, definition in camera_columns.items():
                if name not in camera_existing:
                    connection.execute(text(f"ALTER TABLE cameras ADD COLUMN {name} {definition}"))
        if "license_plates" in inspector.get_table_names():
            plate_existing = {column["name"] for column in inspector.get_columns("license_plates")}
            plate_columns = {
                "recognition_source": "VARCHAR(80) NOT NULL DEFAULT 'local_detector_easyocr'",
                "details_json": "TEXT",
                "frame_index": "INTEGER",
            }
            for name, definition in plate_columns.items():
                if name not in plate_existing:
                    connection.execute(text(f"ALTER TABLE license_plates ADD COLUMN {name} {definition}"))
