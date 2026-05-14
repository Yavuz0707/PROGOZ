from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.auth_service import get_password_hash, verify_password


def test_password_hash_roundtrip():
    hashed = get_password_hash("secret")
    assert hashed != "secret"
    assert verify_password("secret", hashed)

