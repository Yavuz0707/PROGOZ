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
    from app.models import analysis_job, camera, event, incident, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def _migrate_sqlite() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "analysis_jobs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("analysis_jobs")}
    columns = {
        "skipped_frames": "INTEGER NOT NULL DEFAULT 0",
        "current_stage": "VARCHAR(60) NOT NULL DEFAULT 'queued'",
        "analysis_mode": "VARCHAR(40) NOT NULL DEFAULT 'fast'",
        "save_processed_video": "INTEGER NOT NULL DEFAULT 1",
        "debug_scoring": "INTEGER NOT NULL DEFAULT 0",
        "performance_json": "TEXT",
    }
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE analysis_jobs ADD COLUMN {name} {definition}"))
