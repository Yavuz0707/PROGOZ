"""Eski OLASI_KAVGA / SUPHELI incident kayitlarini temizleme scripti.

Seviye bazli kayit politikasi (yalnizca KAVGA kaydedilir) devreye girmeden
once olusmus eski OLASI_KAVGA ve SUPHELI incident'lerini DB'den ve snapshot
dosyalarini diskten temizler. KAVGA seviyesindeki kayitlara DOKUNULMAZ.

Kullanim:
    python scripts/cleanup_old_incidents.py --dry-run   # sadece ne silinecegini goster
    python scripts/cleanup_old_incidents.py             # gercekten sil

Not: Bu script otomatik calistirilmaz; kullanici kontrolundedir.
"""

import argparse
import sys
from pathlib import Path

# backend/ dizinini import path'e ekle (script backend/scripts/ altindan calisir)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.incident import Incident  # noqa: E402

# Silinecek seviyeler (KAVGA korunur)
LEVELS_TO_DELETE = ("OLASI_KAVGA", "SUPHELI")


def _delete_file(path: str | None) -> bool:
    """Snapshot dosyasini diskten sil. Silindiyse True doner."""
    if not path:
        return False
    try:
        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
    except OSError as exc:
        print(f"  ! Dosya silinemedi: {path} ({exc})")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Eski OLASI_KAVGA/SUPHELI incident'lerini temizle.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hicbir sey silme, sadece ne silinecegini raporla.",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        total = db.query(Incident).count()
        kavga_count = db.query(Incident).filter(Incident.severity == "KAVGA").count()
        targets = (
            db.query(Incident)
            .filter(Incident.severity.in_(LEVELS_TO_DELETE))
            .all()
        )

        counts = {level: 0 for level in LEVELS_TO_DELETE}
        files_removed = 0

        mode = "DRY-RUN (silme yok)" if args.dry_run else "SILME"
        print(f"=== Incident temizleme — {mode} ===")
        print(f"Toplam incident: {total} | KAVGA: {kavga_count} | hedef (OLASI_KAVGA/SUPHELI): {len(targets)}")
        print("-" * 60)

        for incident in targets:
            counts[incident.severity] = counts.get(incident.severity, 0) + 1
            snapshot = incident.best_snapshot_path
            if args.dry_run:
                snap_note = f" [snapshot: {snapshot}]" if snapshot else ""
                print(f"  - id={incident.id} {incident.severity} score={incident.max_score}{snap_note}")
            else:
                if _delete_file(snapshot):
                    files_removed += 1
                db.delete(incident)

        if not args.dry_run:
            db.commit()

        print("-" * 60)
        action = "silinecek" if args.dry_run else "silindi"
        print(
            f"{counts.get('OLASI_KAVGA', 0)} OLASI_KAVGA, "
            f"{counts.get('SUPHELI', 0)} SUPHELI kaydi {action} "
            f"({files_removed} dosya diskten temizlendi). "
            f"{kavga_count} KAVGA kaydi korundu."
        )
        if args.dry_run:
            print("\nGercekten silmek icin --dry-run olmadan tekrar calistirin.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
