import re
from pathlib import Path
from uuid import uuid4


def safe_filename(filename: str) -> str:
    path = Path(filename)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "video"
    return f"{stem}_{uuid4().hex[:8]}{path.suffix.lower()}"


def public_static_path(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    parts = list(p.parts)
    if "static" in parts:
        idx = parts.index("static")
        return "/" + "/".join(["static", *parts[idx + 1 :]]).replace("\\", "/")
    return str(p).replace("\\", "/")

