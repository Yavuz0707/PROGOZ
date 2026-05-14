from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import get_settings
from app.models.analysis_job import AnalysisJob
from app.utils.file_utils import safe_filename


settings = get_settings()


async def save_upload_file(file: UploadFile, db) -> AnalysisJob:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.allowed_video_extensions:
        raise HTTPException(status_code=400, detail="Sadece mp4, avi, mov, mkv veya webm video dosyalari yuklenebilir.")
    filename = safe_filename(file.filename or f"upload{suffix}")
    target = settings.upload_dir / filename
    counter = 1
    while target.exists():
        target = settings.upload_dir / f"{target.stem}_{counter}{suffix}"
        counter += 1
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    job = AnalysisJob(filename=target.name, original_path=str(target), status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

