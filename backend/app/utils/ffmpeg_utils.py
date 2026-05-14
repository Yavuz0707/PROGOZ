import shutil
import subprocess
from pathlib import Path
import os


def ffmpeg_path() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates = [
        Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
    ]
    candidates.extend(Path(os.getenv("LOCALAPPDATA", "")).glob("Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin/ffmpeg.exe"))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def ffmpeg_available() -> bool:
    return ffmpeg_path() is not None


def convert_to_h264(input_path: Path, output_path: Path) -> Path:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg bulunamadi. Tarayici uyumlu MP4 icin FFmpeg kurun ve PATH'e ekleyin.")
    executable = ffmpeg_path() or "ffmpeg"
    cmd = [
        executable,
        "-y",
        "-i",
        str(input_path),
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        log_path = output_path.with_suffix(".ffmpeg.log")
        log_path.write_text(result.stderr or result.stdout or "FFmpeg failed without output.", encoding="utf-8")
        raise RuntimeError(f"FFmpeg basarisiz oldu. Log: {log_path}")
    return output_path
