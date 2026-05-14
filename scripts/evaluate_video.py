import argparse
import sys
from pathlib import Path

import cv2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.core.alarm_manager import AlarmManager, cap_level  # noqa: E402
from app.core.detector import PersonDetector  # noqa: E402
from app.core.motion_analyzer import MotionAnalyzer  # noqa: E402


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
LEVEL_ORDER = {"NORMAL": 0, "SUPHELI": 1, "OLASI_KAVGA": 2, "KAVGA": 3}


def expected_from_path(path: Path) -> str:
    tokens = [path.parent.name.lower(), path.stem.lower()]
    joined = " ".join(tokens)
    if any(word in joined for word in ["fight", "kavga", "violence", "violent"]):
        return "KAVGA"
    if any(word in joined for word in ["olasi", "possible"]):
        return "OLASI_KAVGA"
    if any(word in joined for word in ["suspicious", "supheli", "şüpheli"]):
        return "SUPHELI"
    return "NORMAL"


def collect_videos(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() in VIDEO_EXTENSIONS:
        return [root]
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in VIDEO_EXTENSIONS)


def is_correct(expected: str, predicted: str) -> bool:
    if expected == "NORMAL":
        return predicted == "NORMAL"
    if expected == "KAVGA":
        return predicted == "KAVGA"
    return LEVEL_ORDER[predicted] >= LEVEL_ORDER[expected]


def evaluate_video(path: Path, detector: PersonDetector) -> dict[str, object]:
    settings = get_settings()
    analyzer = MotionAnalyzer(sensitivity=settings.sensitivity)
    alarm = AlarmManager()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"file": path.name, "expected_label": expected_from_path(path), "predicted_label": "ERROR", "max_score": 0.0, "avg_score": 0.0, "correct": False}

    scores: list[float] = []
    predicted = "NORMAL"
    frame_index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % max(1, settings.frame_skip) != 0:
                continue
            detections = detector.detect_and_track(frame)
            _, score_info = analyzer.analyze(frame, detections, frame_index)
            level, smoothed, _ = alarm.update(score_info["score"])
            level = cap_level(level, score_info.get("label", "NORMAL"))
            scores.append(smoothed)
            if LEVEL_ORDER[level] > LEVEL_ORDER[predicted]:
                predicted = level
    finally:
        cap.release()

    expected = expected_from_path(path)
    max_score = max(scores, default=0.0)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    return {
        "file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
        "expected_label": expected,
        "predicted_label": predicted,
        "max_score": max_score,
        "avg_score": avg_score,
        "correct": is_correct(expected, predicted),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PROGOZ scoring on test_videos normal/suspicious/fight folders.")
    parser.add_argument("paths", nargs="*", default=[str(ROOT / "test_videos")], help="Video files or folders. Default: test_videos")
    args = parser.parse_args()

    detector = PersonDetector()
    if not detector.available:
        raise SystemExit(f"Detector could not be loaded: {detector.load_error}")

    videos: list[Path] = []
    for item in args.paths:
        videos.extend(collect_videos(Path(item).resolve()))

    print("| file | expected_label | predicted_label | max_score | avg_score | correct |")
    print("| --- | --- | --- | ---: | ---: | --- |")
    for video in videos:
        result = evaluate_video(video, detector)
        print(
            f"| {result['file']} | {result['expected_label']} | {result['predicted_label']} | "
            f"{result['max_score']:.1f} | {result['avg_score']:.1f} | {result['correct']} |"
        )


if __name__ == "__main__":
    main()
