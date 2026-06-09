from datetime import datetime, timedelta
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.plate_ocr import extract_ocr_candidates, normalize_turkish_plate, rank_ocr_candidates
from app.database import SessionLocal, init_db
from app.main import app
from app.models.license_plate import LicensePlate
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.plate_service import cleanup_old_plates, upsert_plate_detection


def test_plate_normalization():
    result = normalize_turkish_plate("07 abc 123")
    assert result.normalized_plate == "07 ABC 123"
    assert result.is_valid_format is True


def test_plate_ocr_confusion_postprocess():
    result = normalize_turkish_plate("O7 ABC I23")
    assert result.normalized_plate == "07 ABC 123"
    assert result.is_valid_format is True


def test_plate_candidate_selection_prefers_complete_plate_over_high_confidence_short_match():
    raw_results = [
        ("34FB 1907 Yochicrco", 0.98, "sharpened"),
        ("34 FB1907", 0.70, "original"),
        ("34FB1907", 0.60, "resized_3x"),
    ]
    candidates = []
    for raw_text, confidence, variant in raw_results:
        candidates.extend(extract_ocr_candidates(raw_text, confidence=confidence, variant_name=variant))
    ranked = rank_ocr_candidates(candidates)
    assert ranked[0].text.normalized_plate == "34 FB 1907"
    assert ranked[0].selected is True
    short_candidate = next(item for item in ranked if item.text.normalized_plate == "34 F 81")
    assert short_candidate.selected is False
    assert short_candidate.candidate_score < ranked[0].candidate_score


def test_plate_normalization_prefers_longest_candidate_inside_noisy_raw_text():
    result = normalize_turkish_plate("34FB 1907 Yochicrco")
    assert result.normalized_plate == "34 FB 1907"
    assert result.is_valid_format is True


def test_plate_normalization_common_tr_examples():
    examples = {
        "66 MA O19": "66 MA 019",
        "66MA019": "66 MA 019",
        "34 JEA 2O": "34 JEA 20",
        "34 JEA20": "34 JEA 20",
    }
    for raw_text, expected in examples.items():
        result = normalize_turkish_plate(raw_text)
        assert result.normalized_plate == expected
        assert result.is_valid_format is True


def test_plate_dedup_updates_existing_video_record():
    init_db()
    db = SessionLocal()
    try:
        first, created = upsert_plate_detection(
            db,
            source_type="video",
            analysis_job_id=999001,
            video_filename="test.mp4",
            plate_text_raw="07 abc 123",
            plate_text_normalized="07 ABC 123",
            is_valid_format=True,
            confidence=0.8,
            ocr_confidence=0.9,
            detection_confidence=0.8,
            time_seconds=3.0,
        )
        second, second_created = upsert_plate_detection(
            db,
            source_type="video",
            analysis_job_id=999001,
            video_filename="test.mp4",
            plate_text_raw="07 ABC 123",
            plate_text_normalized="07 ABC 123",
            is_valid_format=True,
            confidence=0.85,
            ocr_confidence=0.92,
            detection_confidence=0.85,
            time_seconds=8.0,
        )
        assert created is True
        assert second_created is False
        assert second.id == first.id
        assert second.seen_count == 2
        db.delete(second)
        db.commit()
    finally:
        db.close()


def test_plate_retention_cleanup_deletes_old_records():
    init_db()
    db = SessionLocal()
    try:
        old = LicensePlate(
            source_type="camera",
            camera_id=999002,
            plate_text_raw="34 AB 1234",
            plate_text_normalized="34 AB 1234",
            is_valid_format=True,
            confidence=0.9,
            ocr_confidence=0.9,
            detection_confidence=0.9,
            first_seen_at=datetime.utcnow() - timedelta(days=10),
            last_seen_at=datetime.utcnow() - timedelta(days=10),
            status="valid",
        )
        db.add(old)
        db.commit()
        deleted = cleanup_old_plates(db, retention_days=7)
        assert deleted >= 1
        assert db.get(LicensePlate, old.id) is None
    finally:
        db.close()


def test_plate_api_list_and_stats():
    init_db()
    user = User(id=1, username="tester", email="tester@example.com", role="admin", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    db = SessionLocal()
    try:
        record = LicensePlate(
            source_type="video",
            analysis_job_id=999003,
            video_filename="api-test.mp4",
            plate_text_raw="35 ABC 12",
            plate_text_normalized="35 ABC 12",
            is_valid_format=True,
            confidence=0.88,
            ocr_confidence=0.9,
            detection_confidence=0.88,
            first_seen_at=datetime.utcnow(),
            last_seen_at=datetime.utcnow(),
            first_seen_time_seconds=1.2,
            last_seen_time_seconds=1.2,
            status="valid",
        )
        db.add(record)
        db.commit()
        client = TestClient(app)
        list_response = client.get("/api/plates", params={"analysis_job_id": 999003})
        stats_response = client.get("/api/plates/stats")
        assert list_response.status_code == 200
        assert list_response.json()["success"] is True
        assert stats_response.status_code == 200
        assert stats_response.json()["data"]["total"] >= 1
        db.delete(record)
        db.commit()
    finally:
        app.dependency_overrides.clear()
        db.close()
