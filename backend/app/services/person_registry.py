"""Canli akista per-ID kisi takip kayit defteri (60sn TTL) + anomalide DB'ye yukseltme.

Mantik (kullanici vizyonu):
  - Goruntudeki her track ID icin kisinin yakinlastirilmis kirpik fotografi (crop)
    yakalanir ve gecici bellekte ~60sn tutulur.
  - Kisi 60sn icinde bir anomaliye (KAVGA/OLASI_KAVGA/SUPHELI) karisirsa -> crop'u
    DB'ye KALICI yazilir (kullanici sonradan gorebilir).
  - Karismazsa 60sn sonra her yerden (bellek + disk) SILINIR.
  - O an takip edilen herkes canli olarak WS ile panele yayinlanir.

Tasarim: tek worker thread'i yazar; getter okur. Tum public metotlar savunmacidir
(asla istisna firlatmaz) -> analiz/akis dongusunu ASLA bozmaz.
"""
import logging
import threading
import time
from pathlib import Path

import cv2

from app.config import BASE_DIR
from app.utils.file_utils import public_static_path

logger = logging.getLogger("progoz.person_registry")

_CROP_DIR = BASE_DIR / "app" / "static" / "person_crops"


class _Person:
    __slots__ = (
        "track_id", "first_seen", "last_seen", "last_crop_at",
        "crop_path", "best_area", "flagged", "level", "score",
    )

    def __init__(self, track_id: int, now: float) -> None:
        self.track_id = track_id
        self.first_seen = now
        self.last_seen = now
        self.last_crop_at = 0.0
        self.crop_path: Path | None = None
        self.best_area = 0
        self.flagged = False
        self.level = "NORMAL"
        self.score = 0.0


class PersonRegistry:
    def __init__(self, camera_id: int, camera_name: str | None = None,
                 ttl: float = 60.0, crop_interval: float = 3.0) -> None:
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.ttl = ttl
        self.crop_interval = crop_interval
        self._persons: dict[int, _Person] = {}
        self._lock = threading.Lock()
        try:
            _CROP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # ── her analiz karesinde cagrilir: crop yakala/yenile + bayatlayanlari at ──
    def update(self, frame, detections) -> None:
        try:
            now = time.time()
            with self._lock:
                for d in detections or []:
                    tid = int(d.get("track_id") or -1)
                    if tid < 0:
                        continue
                    p = self._persons.get(tid)
                    if p is None:
                        p = _Person(tid, now)
                        self._persons[tid] = p
                    p.last_seen = now
                    bbox = [int(v) for v in d.get("bbox", [0, 0, 0, 0])]
                    area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])
                    # Crop yenile: araliği geçtiyse VEYA belirgin daha buyuk/net goruntu yakalandiysa
                    if now - p.last_crop_at >= self.crop_interval or area > p.best_area * 1.5:
                        path = self._save_crop(frame, bbox, tid)
                        if path is not None:
                            if p.crop_path is not None and not p.flagged:
                                self._safe_unlink(p.crop_path)
                            p.crop_path = path
                            p.last_crop_at = now
                            p.best_area = max(p.best_area, area)
                # TTL: 60sn gorulmeyenleri at (flag'liyse crop'u silme — DB'de zaten kalici)
                stale = [tid for tid, p in self._persons.items() if now - p.last_seen > self.ttl]
                for tid in stale:
                    p = self._persons.pop(tid, None)
                    if p and p.crop_path is not None and not p.flagged:
                        self._safe_unlink(p.crop_path)
        except Exception as exc:  # noqa: BLE001
            logger.debug("PersonRegistry.update hatasi: %s", exc)

    # ── anomali aninda: ilgili ID'leri isaretle ve DB'ye kalici yaz ──
    def flag_and_persist(self, track_ids, level: str, score: float, db_session_factory) -> None:
        try:
            ids = {int(t) for t in (track_ids or [])}
            if not ids:
                return
            to_save: list[_Person] = []
            with self._lock:
                for tid in ids:
                    p = self._persons.get(tid)
                    if p is None or p.flagged or p.crop_path is None:
                        continue
                    p.flagged = True
                    p.level = level
                    p.score = float(score)
                    to_save.append(p)
            for p in to_save:
                self._persist_one(p, db_session_factory)
        except Exception as exc:  # noqa: BLE001
            logger.debug("PersonRegistry.flag_and_persist hatasi: %s", exc)

    # ── canli panel icin o an takip edilen herkes ──
    def live_payload(self) -> list[dict]:
        try:
            now = time.time()
            with self._lock:
                persons = sorted(self._persons.values(), key=lambda x: x.first_seen)
                return [
                    {
                        "id": p.track_id,
                        "crop": public_static_path(p.crop_path) if p.crop_path else None,
                        "age_sec": round(now - p.first_seen, 1),
                        "flagged": p.flagged,
                        "level": p.level,
                    }
                    for p in persons
                ]
        except Exception:
            return []

    def stop(self) -> None:
        """Worker dururken: flag'lenmemis tum gecici crop'lari sil."""
        try:
            with self._lock:
                for p in self._persons.values():
                    if p.crop_path is not None and not p.flagged:
                        self._safe_unlink(p.crop_path)
                self._persons.clear()
        except Exception:
            pass

    # ── ic yardimcilar ──
    def _save_crop(self, frame, bbox, tid: int) -> Path | None:
        try:
            x1, y1, x2, y2 = bbox
            h, w = frame.shape[:2]
            pad_x = int((x2 - x1) * 0.18)
            pad_y = int((y2 - y1) * 0.18)
            cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
            cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
            if cx2 - cx1 < 8 or cy2 - cy1 < 8:
                return None
            crop = frame[cy1:cy2, cx1:cx2]
            fname = f"cam{self.camera_id}_id{tid}_{int(time.time() * 1000)}.jpg"
            fpath = _CROP_DIR / fname
            # cv2.imwrite, Windows'ta unicode (Turkce) yolda calismaz -> imencode + write_bytes.
            ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                fpath.write_bytes(buf.tobytes())
                return fpath
        except Exception:
            pass
        return None

    def _persist_one(self, p: _Person, db_session_factory) -> None:
        db = None
        try:
            from app.models.tracked_person import TrackedPerson

            db = db_session_factory()
            row = TrackedPerson(
                camera_id=self.camera_id,
                camera_name=self.camera_name,
                track_id=p.track_id,
                level=p.level,
                score=p.score,
                crop_path=str(p.crop_path) if p.crop_path else None,
            )
            db.add(row)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("TrackedPerson DB kayit hatasi: %s", exc)
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    @staticmethod
    def _safe_unlink(path) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass
