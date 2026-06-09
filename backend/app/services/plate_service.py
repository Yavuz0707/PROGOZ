import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.camera import Camera
from app.models.license_plate import LicensePlate
from app.utils.file_utils import public_static_path

# ---------------------------------------------------------------------------
# Fuzzy matching helpers — graceful fallback chain:
#   thefuzz (user-requested) → rapidfuzz (already installed) → exact match
# ---------------------------------------------------------------------------
try:
    from thefuzz import fuzz as _fuzz_lib  # type: ignore
except ImportError:
    try:
        from rapidfuzz import fuzz as _fuzz_lib  # type: ignore
    except ImportError:
        _fuzz_lib = None


def _fuzzy_ratio(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if _fuzz_lib is None:
        return 100 if a == b else 0
    return int(_fuzz_lib.ratio(a, b))


# ---------------------------------------------------------------------------
# PlateVoteBuffer — in-memory vote accumulator per analysis job
# ---------------------------------------------------------------------------

class PlateVoteBuffer:
    """Accumulates per-frame OCR readings for a job and fuzzy-groups them.

    Near-identical readings (e.g. "66 MA 019" / "66 NF 019") collapse into
    a single winning entry so the frontend sees one canonical plate per job.
    """

    def __init__(self) -> None:
        # job_id (int for video jobs, str "webcam_N" for live cameras) → {group_key: entry_dict}
        self._buffer: dict[int | str, dict[str, dict]] = {}

    def add_vote(
        self,
        job_id: int | str,
        plate_text: str,
        confidence: float,
        crop_path: str | None,
    ) -> dict | None:
        if not plate_text:
            return None
        buf = self._buffer.setdefault(job_id, {})
        matched_key = self._find_fuzzy_match(buf, plate_text)
        if matched_key:
            entry = buf[matched_key]
            entry["count"] += 1
            if confidence > entry["max_confidence"]:
                entry["max_confidence"] = confidence
                entry["best_crop_path"] = crop_path
                entry["best_text"] = plate_text
        else:
            buf[plate_text] = {
                "count": 1,
                "max_confidence": confidence,
                "best_crop_path": crop_path,
                "best_text": plate_text,
            }
        return self._get_current_best(job_id)

    def _find_fuzzy_match(self, buf: dict, new_text: str) -> str | None:
        best_key: str | None = None
        best_score = 0
        for key in buf:
            score = _fuzzy_ratio(new_text, key)
            if score >= 75 and score > best_score:
                best_score = score
                best_key = key
        return best_key

    def _get_current_best(self, job_id: int | str) -> dict | None:
        buf = self._buffer.get(job_id, {})
        if not buf:
            return None
        best = max(buf.values(), key=lambda x: x["max_confidence"])
        return {
            "text": best["best_text"],
            "confidence": best["max_confidence"],
            "crop_path": best["best_crop_path"],
            "count": best["count"],
        }

    def get_final_winner(self, job_id: int | str, min_votes: int = 3) -> dict | None:
        buf = self._buffer.get(job_id, {})
        if not buf:
            return None
        candidates = [e for e in buf.values() if e["count"] >= min_votes]
        if not candidates:
            candidates = list(buf.values())
        winner = max(candidates, key=lambda x: x["max_confidence"])
        return {
            "text": winner["best_text"],
            "confidence": winner["max_confidence"],
            "crop_path": winner["best_crop_path"],
            "seen_count": winner["count"],
        }

    def clear_job(self, job_id: int | str) -> None:
        self._buffer.pop(job_id, None)

    def flush_webcam(self, camera_id: int, db: Session) -> dict | None:
        """Write the accumulated webcam vote-buffer winner to DB, then clear.

        Called every ~300 frames and on stream stop so a live camera produces
        one consolidated DB record per 30-second window instead of one per frame.
        """
        key = f"webcam_{camera_id}"
        winner = self.get_final_winner(key, min_votes=1)
        if winner and winner.get("text"):
            try:
                upsert_plate_detection(
                    db,
                    source_type="camera",
                    camera_id=camera_id,
                    plate_text_raw=winner["text"],
                    plate_text_normalized=winner["text"],
                    is_valid_format=True,
                    confidence=winner["confidence"],
                    ocr_confidence=winner["confidence"],
                    detection_confidence=winner["confidence"],
                    crop_path=winner["crop_path"],
                    seen_at=datetime.utcnow(),
                    recognition_source="webcam_vote_buffer",
                    details={"seen_count": winner["seen_count"]},
                )
            except Exception:
                pass
        self.clear_job(key)
        return winner


plate_vote_buffer = PlateVoteBuffer()


# ---------------------------------------------------------------------------
# Core upsert
# ---------------------------------------------------------------------------

def upsert_plate_detection(
    db: Session,
    *,
    source_type: str,
    plate_text_raw: str,
    plate_text_normalized: str,
    is_valid_format: bool,
    confidence: float,
    ocr_confidence: float,
    detection_confidence: float,
    camera_id: int | None = None,
    analysis_job_id: int | None = None,
    video_filename: str | None = None,
    bbox: tuple[int, int, int, int] | None = None,
    snapshot_path: str | None = None,
    crop_path: str | None = None,
    time_seconds: float | None = None,
    seen_at: datetime | None = None,
    frame_index: int | None = None,
    recognition_source: str = "local_detector_easyocr",
    details: dict[str, Any] | None = None,
) -> tuple[LicensePlate, bool]:
    settings = get_settings()
    now = seen_at or datetime.utcnow()
    status = "valid" if is_valid_format else "uncertain"
    existing = _find_recent_duplicate(
        db,
        source_type=source_type,
        plate_text_normalized=plate_text_normalized,
        camera_id=camera_id,
        analysis_job_id=analysis_job_id,
        time_seconds=time_seconds,
        seen_at=now,
        window_seconds=settings.plate_dedup_window_seconds,
    )
    bbox_json = json.dumps({"xyxy": list(bbox or [])})
    details_json = json.dumps(details or {}, ensure_ascii=False)
    if existing:
        existing.plate_text_raw = plate_text_raw
        existing.is_valid_format = is_valid_format or existing.is_valid_format
        existing.status = "valid" if existing.is_valid_format else status
        existing.last_seen_at = now
        existing.last_seen_time_seconds = time_seconds if time_seconds is not None else existing.last_seen_time_seconds
        existing.frame_index = frame_index if frame_index is not None else existing.frame_index
        existing.seen_count += 1
        existing.ocr_confidence = max(existing.ocr_confidence, float(ocr_confidence))
        existing.detection_confidence = max(existing.detection_confidence, float(detection_confidence))
        existing.bbox_json = bbox_json
        existing.recognition_source = recognition_source
        existing.details_json = details_json
        if confidence >= existing.confidence:
            existing.confidence = float(confidence)
            existing.best_snapshot_path = snapshot_path or existing.best_snapshot_path
            existing.crop_path = crop_path or existing.crop_path
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return existing, False

    record = LicensePlate(
        source_type=source_type,
        camera_id=camera_id,
        analysis_job_id=analysis_job_id,
        video_filename=video_filename,
        plate_text_raw=plate_text_raw,
        plate_text_normalized=plate_text_normalized,
        is_valid_format=is_valid_format,
        confidence=float(confidence),
        ocr_confidence=float(ocr_confidence),
        detection_confidence=float(detection_confidence),
        first_seen_at=now,
        last_seen_at=now,
        first_seen_time_seconds=time_seconds,
        last_seen_time_seconds=time_seconds,
        frame_index=frame_index,
        seen_count=1,
        best_snapshot_path=snapshot_path,
        crop_path=crop_path,
        bbox_json=bbox_json,
        status=status,
        recognition_source=recognition_source,
        details_json=details_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, True


# ---------------------------------------------------------------------------
# List / query
# ---------------------------------------------------------------------------

def list_plates(db: Session, filters: dict[str, Any]) -> list[LicensePlate]:
    settings = get_settings()
    query = db.query(LicensePlate)
    if not filters.get("show_unreadable", settings.plate_show_unreadable_in_default_list):
        query = query.filter(
            LicensePlate.status != "unreadable",
            LicensePlate.plate_text_normalized.is_not(None),
            LicensePlate.plate_text_normalized != "",
            LicensePlate.plate_text_normalized != "UNREADABLE",
        )
    if filters.get("require_valid_format", settings.plate_require_valid_format_for_default):
        query = query.filter(LicensePlate.is_valid_format.is_(True))
    if filters.get("source_type"):
        query = query.filter(LicensePlate.source_type == filters["source_type"])
    if filters.get("camera_id") is not None:
        query = query.filter(LicensePlate.camera_id == filters["camera_id"])
    if filters.get("analysis_job_id") is not None:
        query = query.filter(LicensePlate.analysis_job_id == filters["analysis_job_id"])
    if filters.get("plate"):
        query = query.filter(LicensePlate.plate_text_normalized.ilike(f"%{filters['plate'].upper()}%"))
    if filters.get("valid_only"):
        query = query.filter(LicensePlate.is_valid_format.is_(True))
    if filters.get("date_from"):
        query = query.filter(LicensePlate.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(LicensePlate.created_at <= filters["date_to"])
    if filters.get("min_confidence") is not None:
        query = query.filter(LicensePlate.confidence >= filters["min_confidence"])
    return query.order_by(LicensePlate.last_seen_at.desc(), LicensePlate.created_at.desc()).all()


def plate_payload(record: LicensePlate) -> dict:
    data = {
        "id": record.id,
        "source_type": record.source_type,
        "camera_id": record.camera_id,
        "camera_name": record.camera.name if record.camera else None,
        "analysis_job_id": record.analysis_job_id,
        "video_filename": record.video_filename,
        "plate_text_raw": record.plate_text_raw,
        "plate_text_normalized": record.plate_text_normalized,
        "is_valid_format": record.is_valid_format,
        "confidence": record.confidence,
        "ocr_confidence": record.ocr_confidence,
        "detection_confidence": record.detection_confidence,
        "first_seen_at": record.first_seen_at.isoformat() if record.first_seen_at else None,
        "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
        "first_seen_time_seconds": record.first_seen_time_seconds,
        "last_seen_time_seconds": record.last_seen_time_seconds,
        "frame_index": record.frame_index,
        "seen_count": record.seen_count,
        "best_snapshot_path": record.best_snapshot_path,
        "best_snapshot_url": public_static_path(record.best_snapshot_path),
        "crop_path": record.crop_path,
        "crop_url": public_static_path(record.crop_path),
        "bbox_json": record.bbox_json,
        "status": record.status,
        "recognition_source": record.recognition_source,
        "details_json": record.details_json,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
    return data


# ---------------------------------------------------------------------------
# Delete / cleanup
# ---------------------------------------------------------------------------

def delete_plate(db: Session, record: LicensePlate) -> None:
    _delete_file(record.best_snapshot_path)
    _delete_file(record.crop_path)
    db.delete(record)
    db.commit()


def cleanup_old_plates(db: Session, retention_days: int | None = None) -> int:
    settings = get_settings()
    days = retention_days or settings.plate_retention_days
    cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    records = db.query(LicensePlate).filter(
        ((LicensePlate.last_seen_at.is_not(None)) & (LicensePlate.last_seen_at < cutoff))
        | ((LicensePlate.last_seen_at.is_(None)) & (LicensePlate.created_at < cutoff))
    ).all()
    count = len(records)
    for record in records:
        _delete_file(record.best_snapshot_path)
        _delete_file(record.crop_path)
        db.delete(record)
    db.commit()
    return count


def cleanup_unreadable_plates(db: Session) -> int:
    records = (
        db.query(LicensePlate)
        .filter(
            or_(
                LicensePlate.plate_text_normalized.is_(None),
                LicensePlate.plate_text_normalized == "",
                LicensePlate.plate_text_normalized == "UNREADABLE",
                LicensePlate.status == "unreadable",
            )
        )
        .all()
    )
    count = len(records)
    for record in records:
        _delete_file(record.best_snapshot_path)
        _delete_file(record.crop_path)
        db.delete(record)
    db.commit()
    return count


def run_plate_cleanup_once() -> int:
    db = SessionLocal()
    try:
        return cleanup_old_plates(db)
    finally:
        db.close()


def start_plate_cleanup_scheduler() -> Any | None:
    settings = get_settings()
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        return None
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(run_plate_cleanup_once, "interval", days=1, id="plate_cleanup", replace_existing=True)
    scheduler.start()
    if settings.plate_cleanup_on_startup:
        run_plate_cleanup_once()
    return scheduler


# ---------------------------------------------------------------------------
# Stats / export
# ---------------------------------------------------------------------------

def plate_stats(db: Session) -> dict:
    today = datetime.utcnow().date()
    totals_by_source = dict(db.query(LicensePlate.source_type, func.count(LicensePlate.id)).group_by(LicensePlate.source_type).all())
    valid_count = db.query(LicensePlate).filter(LicensePlate.is_valid_format.is_(True)).count()
    total = db.query(LicensePlate).count()
    unreadable_count = (
        db.query(LicensePlate)
        .filter(
            or_(
                LicensePlate.plate_text_normalized.is_(None),
                LicensePlate.plate_text_normalized == "",
                LicensePlate.plate_text_normalized == "UNREADABLE",
                LicensePlate.status == "unreadable",
            )
        )
        .count()
    )
    camera_counts = dict(
        db.query(LicensePlate.camera_id, func.count(LicensePlate.id))
        .filter(LicensePlate.camera_id.is_not(None))
        .group_by(LicensePlate.camera_id)
        .all()
    )
    video_counts = dict(
        db.query(LicensePlate.analysis_job_id, func.count(LicensePlate.id))
        .filter(LicensePlate.analysis_job_id.is_not(None))
        .group_by(LicensePlate.analysis_job_id)
        .all()
    )
    return {
        "total": total,
        "today": db.query(LicensePlate).filter(func.date(LicensePlate.created_at) == today.isoformat()).count(),
        "by_source": totals_by_source,
        "by_camera": camera_counts,
        "by_video": video_counts,
        "valid": valid_count,
        "uncertain": max(total - valid_count - unreadable_count, 0),
        "unreadable": unreadable_count,
    }


def export_plates_csv(db: Session, rows: list[LicensePlate], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "plate", "source_type", "camera_id", "analysis_job_id", "confidence", "first_seen", "last_seen", "seen_count", "status"])
        for row in rows:
            writer.writerow([row.id, row.plate_text_normalized, row.source_type, row.camera_id, row.analysis_job_id, row.confidence, row.first_seen_at, row.last_seen_at, row.seen_count, row.status])
    return target


# ---------------------------------------------------------------------------
# Fuzzy deduplication
# ---------------------------------------------------------------------------

def _fuzzy_dedup_list(db: Session, plates: list[LicensePlate]) -> int:
    """Fuzzy-group plates (ratio >= 75), keep highest-confidence per group.

    Merges seen_count, first/last seen times. Does NOT commit — caller must.
    Returns number of deleted records.
    """
    if len(plates) <= 1:
        return 0
    assigned: set[int] = set()
    groups: list[list[LicensePlate]] = []
    for plate in plates:
        if plate.id in assigned:
            continue
        group = [plate]
        assigned.add(plate.id)
        for other in plates:
            if other.id in assigned:
                continue
            if _fuzzy_ratio(
                plate.plate_text_normalized or "",
                other.plate_text_normalized or "",
            ) >= 75:
                group.append(other)
                assigned.add(other.id)
        groups.append(group)

    deleted = 0
    for group in groups:
        if len(group) <= 1:
            continue
        keep = max(group, key=lambda r: r.confidence)
        keep.seen_count = sum(r.seen_count for r in group)
        keep.first_seen_at = min((r.first_seen_at for r in group if r.first_seen_at), default=keep.first_seen_at)
        keep.last_seen_at = max((r.last_seen_at for r in group if r.last_seen_at), default=keep.last_seen_at)
        keep.first_seen_time_seconds = min(
            (r.first_seen_time_seconds for r in group if r.first_seen_time_seconds is not None),
            default=keep.first_seen_time_seconds,
        )
        keep.last_seen_time_seconds = max(
            (r.last_seen_time_seconds for r in group if r.last_seen_time_seconds is not None),
            default=keep.last_seen_time_seconds,
        )
        keep.updated_at = datetime.utcnow()
        for record in group:
            if record.id != keep.id:
                _delete_file(record.best_snapshot_path)
                _delete_file(record.crop_path)
                db.delete(record)
                deleted += 1
    return deleted


def fuzzy_deduplicate_job_plates(db: Session, job_id: int) -> int:
    """Fuzzy-dedup all plates for a single analysis job. Returns deleted count."""
    plates = db.query(LicensePlate).filter(LicensePlate.analysis_job_id == job_id).all()
    deleted = _fuzzy_dedup_list(db, plates)
    if deleted > 0:
        db.commit()
    return deleted


def deduplicate_plates_global(db: Session) -> int:
    """Fuzzy-dedup all plates globally, partitioned by source (job or camera).

    Within each source, plates with fuzzy ratio >= 75 are merged:
    highest-confidence record is kept, seen_count is summed.
    """
    all_plates = db.query(LicensePlate).order_by(LicensePlate.confidence.desc()).all()
    source_buckets: dict[tuple, list[LicensePlate]] = {}
    for plate in all_plates:
        if plate.source_type == "video":
            key: tuple = ("video", plate.analysis_job_id)
        else:
            key = ("camera", plate.camera_id)
        source_buckets.setdefault(key, []).append(plate)

    deleted = 0
    for plates in source_buckets.values():
        deleted += _fuzzy_dedup_list(db, plates)
    db.commit()
    return deleted


def run_deduplicate_once_global() -> int:
    db = SessionLocal()
    try:
        return deduplicate_plates_global(db)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_recent_duplicate(
    db: Session,
    *,
    source_type: str,
    plate_text_normalized: str,
    camera_id: int | None,
    analysis_job_id: int | None,
    time_seconds: float | None,
    seen_at: datetime,
    window_seconds: int,
) -> LicensePlate | None:
    if not plate_text_normalized or plate_text_normalized == "UNREADABLE":
        return None
    query = db.query(LicensePlate).filter(
        LicensePlate.source_type == source_type,
        LicensePlate.plate_text_normalized == plate_text_normalized,
    )
    if source_type == "video":
        # One record per (normalized_text, job) — no time-window limit
        query = query.filter(LicensePlate.analysis_job_id == analysis_job_id)
    else:
        query = query.filter(LicensePlate.camera_id == camera_id)
        query = query.filter(LicensePlate.last_seen_at >= seen_at - timedelta(seconds=window_seconds))
    return query.order_by(LicensePlate.confidence.desc()).first()


def _delete_file(path: str | None) -> None:
    if not path:
        return
    try:
        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
    except OSError:
        pass
