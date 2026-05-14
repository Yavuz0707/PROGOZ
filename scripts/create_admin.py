import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import get_password_hash  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="PROGOZ admin kullanicisi olusturur.")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--email", default="admin@progoz.app")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter((User.username == args.username) | (User.email == args.email)).first()
        if existing:
            existing.hashed_password = get_password_hash(args.password)
            existing.role = "admin"
            existing.is_active = True
            print(f"Admin kullanicisi guncellendi: {args.username}")
        else:
            user = User(
                username=args.username,
                email=args.email,
                hashed_password=get_password_hash(args.password),
                role="admin",
                is_active=True,
            )
            db.add(user)
            print(f"Admin kullanicisi olusturuldu: {args.username}")
        db.commit()
        print("Varsayilan sifreyi demo sonrasi mutlaka degistirin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
