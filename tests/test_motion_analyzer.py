from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.motion_analyzer import MotionAnalyzer


def test_motion_analyzer_scores_moving_rois():
    analyzer = MotionAnalyzer()
    frame1 = np.zeros((120, 160, 3), dtype=np.uint8)
    frame2 = frame1.copy()
    cv2.rectangle(frame2, (40, 30), (80, 90), (255, 255, 255), -1)
    detections = [{"track_id": 1, "bbox": [35, 25, 85, 95], "confidence": 0.9}]
    analyzer.analyze(frame1, detections)
    motions, info = analyzer.analyze(frame2, detections)
    assert len(motions) == 1
    assert info["score"] > 0

