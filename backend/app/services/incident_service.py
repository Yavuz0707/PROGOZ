import json
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
        if is_above and self.active is None:
            self.active = IncidentCandidate(
                source_type=self.source_type,
                start_frame=frame_index if self.source_type == "video" else None,
                start_time_seconds=time_seconds,
                started_at=now if self.source_type == "camera" else None,
            )
        if self.active is None:
            return None

        if is_above:
            self._add_sample(self.active, frame_index, time_seconds, now, score, severity, score_info, frame)
            return None

        grace = self._grace_expired(self.active, time_seconds, now)
        if grace:
            return self.close()
        return None

    def close(self) -> Incident | None:
        if self.active is None:
            return None
        candidate = self.active
        self.active = None
        if not self._is_confirmed(candidate):
            return None
        incident = self._create_incident(candidate)
        self.created.append(incident)
        return incident

    def finalize(self) -> Incident | None:
        return self.close()

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

    def _grace_expired(self, candidate: IncidentCandidate, time_seconds: float | None, now: datetime) -> bool:
        if self.source_type == "video":
            if candidate.last_above_time is None or time_seconds is None:
                return False
            return time_seconds - candidate.last_above_time >= self.settings.incident_end_grace_seconds
        if candidate.last_above_at is None:
            return False
        return (now - candidate.last_above_at).total_seconds() >= self.settings.incident_end_grace_seconds

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

    def _save_best_snapshot(self, candidate: IncidentCandidate) -> Path | None:
        if not self.settings.save_best_snapshot or candidate.best_frame is None:
            return None
        prefix = "job" if self.source_type == "video" else "camera"
        ident = self.analysis_job_id if self.source_type == "video" else self.camera_id
        frame = candidate.end_frame or candidate.start_frame or 0
        path = self.settings.snapshot_dir / f"incident_{prefix}_{ident}_{frame}_{int(candidate.max_score * 10)}.jpg"
        cv2.imwrite(str(path), candidate.best_frame)
        return path


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
