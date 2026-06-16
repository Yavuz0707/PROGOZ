import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.incident import Incident
from app.utils.file_utils import public_static_path


SEVERITY_ORDER = {"NORMAL": 0, "SUPHELI": 1, "OLASI_KAVGA": 2, "KAVGA": 3}


def _merge_window_seconds() -> float:
    """Ayni kaynaktan kisa araliklarla gelen tespitleri tek incident'te birlestirme penceresi."""
    try:
        return float(os.getenv("INCIDENT_MERGE_WINDOW_SECONDS", "60"))
    except (TypeError, ValueError):
        return 60.0


def _recorded_levels() -> set[str]:
    """DB'ye yazilacak (Olaylar listesinde gorunecek) seviyeler.

    Varsayilan: sadece KAVGA. OLASI_KAVGA/SUPHELI yalnizca bildirim olarak
    iletilir, incident kaydi olusturulmaz. INCIDENT_RECORD_LEVELS ile genisletilebilir
    (ornek: "KAVGA,OLASI_KAVGA").
    """
    raw = os.getenv("INCIDENT_RECORD_LEVELS", "KAVGA")
    levels = {item.strip().upper() for item in raw.split(",") if item.strip()}
    return levels or {"KAVGA"}


def should_persist_incident(level: str) -> bool:
    """Bu seviyedeki tespit DB'ye yazilmali (ve snapshot kaydedilmeli) mi?"""
    return (level or "").upper() in _recorded_levels()


@dataclass
class IncidentCandidate:
    source_type: str
    start_frame: int | None
    start_time_seconds: float | None
    started_at: datetime | None
    end_frame: int | None = None
    end_time_seconds: float | None = None
    ended_at: datetime | None = None
    scores: list[float] = field(default_factory=list)
    timeline: list[dict[str, float]] = field(default_factory=list)
    max_score: float = 0.0
    best_frame: np.ndarray | None = None
    best_snapshot_score: float = 0.0
    severity: str = "SUPHELI"
    involved_ids: set[int] = field(default_factory=set)
    details: dict[str, Any] = field(default_factory=dict)
    last_above_time: float | None = None
    last_above_at: datetime | None = None


class IncidentTracker:
    def __init__(
        self,
        db: Session,
        source_type: str,
        camera_id: int | None = None,
        analysis_job_id: int | None = None,
        video_filename: str | None = None,
        fps: float = 25.0,
    ) -> None:
        self.settings = get_settings()
        self.db = db
        self.source_type = source_type
        self.camera_id = camera_id
        self.analysis_job_id = analysis_job_id
        self.video_filename = video_filename
        self.fps = fps or 25.0
        self.active: IncidentCandidate | None = None
        # DB row for the currently open candidate (once confirmed + persisted).
        # While the merge window is open, new detections update this same row
        # instead of creating new incidents.
        self.active_incident: Incident | None = None
        self.merge_window_seconds = _merge_window_seconds()
        self.created: list[Incident] = []

    def update(
        self,
        frame_index: int,
        score: float,
        severity: str,
        score_info: dict[str, Any],
        frame: np.ndarray | None = None,
        timestamp: datetime | None = None,
    ) -> Incident | None:
        time_seconds = frame_index / self.fps if self.source_type == "video" else None
        now = timestamp or datetime.utcnow()
        is_above = score >= self.settings.incident_min_score_to_start and severity != "NORMAL"

        result: Incident | None = None

        # Merge penceresi dolduysa acik incident'i kapat (artik guncellenemez).
        if self.active is not None and self._merge_window_expired(self.active, time_seconds, now):
            result = self._close_active()

        if not is_above:
            return result

        # Acik bir incident yoksa (veya yeni kapandiysa) yeni aday baslat.
        if self.active is None:
            self.active = IncidentCandidate(
                source_type=self.source_type,
                start_frame=frame_index if self.source_type == "video" else None,
                start_time_seconds=time_seconds,
                started_at=now if self.source_type == "camera" else None,
            )

        self._add_sample(self.active, frame_index, time_seconds, now, score, severity, score_info, frame)
        persisted = self._persist_or_update_active()
        if persisted is not None and result is None:
            result = persisted
        return result

    def close(self) -> Incident | None:
        """Acik incident'i kapat; henuz kaydedilmediyse (ama onaylandiysa) kaydet."""
        return self._close_active()

    def finalize(self) -> Incident | None:
        return self._close_active()

    def _persist_or_update_active(self) -> Incident | None:
        """Aday onaylandiysa ilk kez DB'ye yaz, sonraki tespitlerde ayni satiri guncelle.

        Returns the incident only when it is first created (so the caller can
        broadcast it once); subsequent in-place updates return None.
        """
        candidate = self.active
        if candidate is None:
            return None
        if self.active_incident is None:
            if not self._is_confirmed(candidate):
                return None
            # Seviye bazli kayit politikasi: yalnizca RECORDED_LEVELS (orn. KAVGA)
            # DB'ye yazilir. Aday SUPHELI/OLASI_KAVGA olarak baslayip KAVGA'ya
            # yukseldiginde, o ana kadar birikmis timeline ile birlikte kaydedilir.
            if not should_persist_incident(candidate.severity):
                return None
            incident = self._create_incident(candidate)
            self.active_incident = incident
            self.created.append(incident)
            return incident
        self._update_incident_row(candidate)
        return None

    def _close_active(self) -> Incident | None:
        candidate = self.active
        self.active = None
        incident_to_return: Incident | None = None
        if candidate is not None:
            if self.active_incident is None:
                # Hic kaydedilmemis; onaylandiysa VE kaydedilebilir seviyedeyse simdi kaydet.
                if self._is_confirmed(candidate) and should_persist_incident(candidate.severity):
                    incident = self._create_incident(candidate)
                    self.created.append(incident)
                    incident_to_return = incident
            else:
                # Zaten kaydedilmis ve canli guncellenmis; son durumu yaz.
                self._update_incident_row(candidate)
        self.active_incident = None
        return incident_to_return

    def _add_sample(
        self,
        candidate: IncidentCandidate,
        frame_index: int,
        time_seconds: float | None,
        now: datetime,
        score: float,
        severity: str,
        score_info: dict[str, Any],
        frame: np.ndarray | None,
    ) -> None:
        candidate.end_frame = frame_index if self.source_type == "video" else None
        candidate.end_time_seconds = time_seconds
        candidate.ended_at = now if self.source_type == "camera" else None
        candidate.last_above_time = time_seconds
        candidate.last_above_at = now
        candidate.scores.append(float(score))
        if self.settings.save_score_timeline:
            candidate.timeline.append({"t": round(time_seconds or len(candidate.scores), 3), "score": round(float(score), 2)})
        if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(candidate.severity, 0):
            candidate.severity = severity
        pair = score_info.get("pair") or []
        candidate.involved_ids.update(int(item) for item in pair if isinstance(item, int))
        candidate.details = {
            "criteria": score_info.get("criteria", {}),
            "penalties": score_info.get("penalties", {}),
            "reasons": score_info.get("reasons", []),
        }
        if score >= candidate.max_score:
            candidate.max_score = float(score)
            candidate.best_snapshot_score = float(score)
            candidate.best_frame = frame.copy() if frame is not None else None

    def _merge_window_expired(self, candidate: IncidentCandidate, time_seconds: float | None, now: datetime) -> bool:
        """Son tespitten bu yana merge penceresi kadar sure gectiyse True.

        Pencere dolmadigi surece yeni tespitler ayni incident'e birlesir.
        """
        if self.source_type == "video":
            if candidate.last_above_time is None or time_seconds is None:
                return False
            return time_seconds - candidate.last_above_time >= self.merge_window_seconds
        if candidate.last_above_at is None:
            return False
        return (now - candidate.last_above_at).total_seconds() >= self.merge_window_seconds

    def _is_confirmed(self, candidate: IncidentCandidate) -> bool:
        frames = len(candidate.scores)
        duration = self._duration(candidate)
        severity = candidate.severity
        if severity == "KAVGA":
            return frames >= self.settings.incident_min_frames_fight or duration >= self.settings.incident_min_duration_fight
        if severity == "OLASI_KAVGA":
            return frames >= self.settings.incident_min_frames_possible_fight or duration >= self.settings.incident_min_duration_possible_fight
        return frames >= self.settings.incident_min_frames_suspicious or duration >= self.settings.incident_min_duration_suspicious

    def _duration(self, candidate: IncidentCandidate) -> float:
        if self.source_type == "video":
            start = candidate.start_time_seconds or 0.0
            end = candidate.end_time_seconds if candidate.end_time_seconds is not None else start
            return max(0.0, end - start)
        if candidate.started_at and candidate.ended_at:
            return max(0.0, (candidate.ended_at - candidate.started_at).total_seconds())
        return 0.0

    def _create_incident(self, candidate: IncidentCandidate) -> Incident:
        snapshot_path = self._save_best_snapshot(candidate)
        incident = Incident(
            source_type=self.source_type,
            camera_id=self.camera_id,
            analysis_job_id=self.analysis_job_id,
            video_filename=self.video_filename,
            severity=candidate.severity,
            status="confirmed",
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
            start_time_seconds=candidate.start_time_seconds,
            end_time_seconds=candidate.end_time_seconds,
            duration_seconds=round(self._duration(candidate), 3),
            started_at=candidate.started_at,
            ended_at=candidate.ended_at,
            max_score=round(candidate.max_score, 3),
            avg_score=round(sum(candidate.scores) / max(len(candidate.scores), 1), 3),
            best_snapshot_path=str(snapshot_path) if snapshot_path else None,
            best_snapshot_score=round(candidate.best_snapshot_score, 3),
            involved_track_ids_json=json.dumps(sorted(candidate.involved_ids)),
            score_timeline_json=json.dumps(candidate.timeline),
            details_json=json.dumps(candidate.details),
        )
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def _update_incident_row(self, candidate: IncidentCandidate) -> None:
        """Acik incident satirini birlesen tespitlere gore yerinde guncelle."""
        incident = self.active_incident
        if incident is None:
            return
        incident.severity = candidate.severity
        incident.end_frame = candidate.end_frame
        incident.end_time_seconds = candidate.end_time_seconds
        incident.ended_at = candidate.ended_at
        incident.duration_seconds = round(self._duration(candidate), 3)
        incident.max_score = round(candidate.max_score, 3)
        incident.avg_score = round(sum(candidate.scores) / max(len(candidate.scores), 1), 3)
        incident.involved_track_ids_json = json.dumps(sorted(candidate.involved_ids))
        incident.score_timeline_json = json.dumps(candidate.timeline)
        incident.details_json = json.dumps(candidate.details)
        # Daha yuksek skorlu kare geldiyse snapshot'i degistir, eskisini diskten sil.
        if (
            self.settings.save_best_snapshot
            and candidate.best_frame is not None
            and round(candidate.best_snapshot_score, 3) > round(incident.best_snapshot_score or 0.0, 3)
        ):
            new_path = self._save_best_snapshot(candidate)
            if new_path is not None:
                self._delete_snapshot_file(incident.best_snapshot_path)
                incident.best_snapshot_path = str(new_path)
                incident.best_snapshot_score = round(candidate.best_snapshot_score, 3)
        self.db.commit()
        self.db.refresh(incident)

    def _save_best_snapshot(self, candidate: IncidentCandidate) -> Path | None:
        if not self.settings.save_best_snapshot or candidate.best_frame is None:
            return None
        prefix = "job" if self.source_type == "video" else "camera"
        ident = self.analysis_job_id if self.source_type == "video" else self.camera_id
        frame = candidate.end_frame or candidate.start_frame or 0
        path = self.settings.snapshot_dir / f"incident_{prefix}_{ident}_{frame}_{int(candidate.max_score * 10)}.jpg"
        cv2.imwrite(str(path), candidate.best_frame)
        return path

    def _delete_snapshot_file(self, path: str | None) -> None:
        if not path:
            return
        try:
            file_path = Path(path)
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
        except OSError:
            pass


def incident_payload(incident: Incident) -> dict:
    return {
        "id": incident.id,
        "source_type": incident.source_type,
        "camera_id": incident.camera_id,
        "analysis_job_id": incident.analysis_job_id,
        "video_filename": incident.video_filename,
        "severity": incident.severity,
        "status": incident.status,
        "start_frame": incident.start_frame,
        "end_frame": incident.end_frame,
        "start_time_seconds": incident.start_time_seconds,
        "end_time_seconds": incident.end_time_seconds,
        "duration_seconds": incident.duration_seconds,
        "started_at": incident.started_at.isoformat() if incident.started_at else None,
        "ended_at": incident.ended_at.isoformat() if incident.ended_at else None,
        "max_score": incident.max_score,
        "avg_score": incident.avg_score,
        "best_snapshot_url": public_static_path(incident.best_snapshot_path),
        "best_snapshot_score": incident.best_snapshot_score,
        "clip_url": public_static_path(incident.clip_path),
        "involved_track_ids": json.loads(incident.involved_track_ids_json or "[]"),
        "score_timeline": json.loads(incident.score_timeline_json or "[]"),
        "details": json.loads(incident.details_json or "{}"),
        "created_at": incident.created_at.isoformat(),
    }
