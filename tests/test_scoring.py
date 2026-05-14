from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.alarm_manager import AlarmManager
from app.core.motion_analyzer import MotionAnalyzer, TrackMotion
from app.core.scoring import alarm_level, bbox_overlap_ratio, weighted_score


def motion(track_id: int, x1: int, y1: int, x2: int, y2: int, *, energy: float, chaos: float, speed: float = 0.3) -> TrackMotion:
    return TrackMotion(
        track_id=track_id,
        bbox=(x1, y1, x2, y2),
        center=((x1 + x2) / 2, (y1 + y2) / 2),
        area=float((x2 - x1) * (y2 - y1)),
        energy=energy * 40,
        flow_mean=chaos,
        flow_std=chaos,
        speed=speed * 40,
        size_variation=0.2,
        center_movement=speed * 40,
        direction_change=0.6,
        activity={
            "motion_energy": energy,
            "optical_flow_mean": chaos,
            "chaos": chaos,
            "speed": speed,
            "bbox_area_variation": 0.25,
            "center_movement": speed,
            "direction_change": 0.35,
        },
    )


def keypoints(points: dict[int, tuple[float, float, float]]) -> list[dict[str, float]]:
    data = [{"x": 0.0, "y": 0.0, "confidence": 0.0} for _ in range(17)]
    for index, (x, y, confidence) in points.items():
        data[index] = {"x": x, "y": y, "confidence": confidence}
    return data


def test_weighted_pair_score_high_when_mutual_evidence_is_high():
    score = weighted_score(
        {
            "mutual_energy": 0.88,
            "mutual_chaos": 0.82,
            "relative_motion": 0.70,
            "temporal_persistence": 0.70,
            "proximity": 0.75,
            "overlap": 0.35,
            "pose_contact": 0.65,
        }
    )
    assert score >= 75


def test_single_person_high_motion_stays_below_alarm_range():
    analyzer = MotionAnalyzer(debug_scoring=False)
    info = analyzer._single_person_score([motion(1, 10, 10, 80, 150, energy=1.0, chaos=0.9, speed=1.0)])
    assert info["score"] <= 18
    assert alarm_level(info["score"], 10) == "NORMAL"


def test_two_people_far_apart_score_low_even_if_active():
    analyzer = MotionAnalyzer(debug_scoring=False)
    a = motion(1, 10, 10, 80, 150, energy=0.9, chaos=0.8)
    b = motion(2, 520, 10, 590, 150, energy=0.9, chaos=0.8)
    analyzer.history[1].append(a)
    analyzer.history[2].append(b)
    info = analyzer._score_pair(a, b, diagonal=720, frame_index=1)
    assert info["score"] < 25
    assert "far_pair" in info["penalties"]


def test_two_people_near_but_calm_score_low():
    analyzer = MotionAnalyzer(debug_scoring=False)
    a = motion(1, 100, 100, 180, 250, energy=0.08, chaos=0.05, speed=0.04)
    b = motion(2, 170, 105, 250, 255, energy=0.08, chaos=0.05, speed=0.04)
    analyzer.history[1].append(a)
    analyzer.history[2].append(b)
    info = analyzer._score_pair(a, b, diagonal=720, frame_index=1)
    assert info["score"] < 20
    assert "low_mutual_energy" in info["penalties"]


def test_close_mutual_chaotic_pair_scores_high_after_duration():
    analyzer = MotionAnalyzer(debug_scoring=False)
    a = motion(1, 100, 100, 190, 260, energy=0.92, chaos=0.88, speed=0.75)
    b = motion(2, 170, 105, 260, 265, energy=0.90, chaos=0.86, speed=0.70)
    analyzer.history[1].extend([a, a])
    analyzer.history[2].extend([b, b])
    info = {}
    for frame in range(1, 6):
        info = analyzer._score_pair(a, b, diagonal=720, frame_index=frame)
    assert info["score"] >= 45
    assert info["label"] in {"OLASI_KAVGA", "KAVGA"}


def test_low_motion_persistent_close_overlap_is_not_normal():
    analyzer = MotionAnalyzer(debug_scoring=False)
    a = motion(1, 100, 100, 205, 270, energy=0.12, chaos=0.08, speed=0.05)
    b = motion(2, 150, 105, 255, 275, energy=0.10, chaos=0.07, speed=0.04)
    analyzer.history[1].extend([a, a])
    analyzer.history[2].extend([b, b])
    info = {}
    for frame in range(1, 7):
        info = analyzer._score_pair(a, b, diagonal=720, frame_index=frame)
    assert info["score"] < 35
    assert info["label"] != "KAVGA"


def test_pose_neck_contact_raises_low_motion_attack_candidate():
    analyzer = MotionAnalyzer(debug_scoring=False)
    attacker = motion(1, 100, 100, 200, 280, energy=0.14, chaos=0.08, speed=0.08)
    target = motion(2, 160, 105, 260, 285, energy=0.10, chaos=0.06, speed=0.03)
    attacker.keypoints = keypoints({9: (205, 150, 0.95), 10: (210, 158, 0.90), 5: (145, 155, 0.8), 6: (180, 155, 0.8)})
    target.keypoints = keypoints({0: (210, 128, 0.9), 5: (190, 162, 0.9), 6: (230, 162, 0.9)})
    analyzer.history[1].extend([attacker, attacker])
    analyzer.history[2].extend([target, target])
    info = {}
    for frame in range(1, 5):
        info = analyzer._score_pair(attacker, target, diagonal=720, frame_index=frame)
    assert info["score"] >= 40
    assert "pose_contact" in info["reasons"]


def test_persistent_pose_contact_with_restraint_reaches_fight_range():
    analyzer = MotionAnalyzer(debug_scoring=False)
    attacker = motion(1, 100, 100, 205, 285, energy=0.32, chaos=0.26, speed=0.30)
    target = motion(2, 155, 105, 260, 290, energy=0.06, chaos=0.05, speed=0.02)
    attacker.keypoints = keypoints({9: (208, 150, 0.95), 10: (212, 156, 0.95), 5: (145, 158, 0.8), 6: (188, 158, 0.8)})
    target.keypoints = keypoints({0: (211, 128, 0.9), 5: (192, 164, 0.9), 6: (232, 164, 0.9)})
    analyzer.history[1].extend([attacker, attacker])
    analyzer.history[2].extend([target, target])
    info = {}
    for frame in range(1, 7):
        info = analyzer._score_pair(attacker, target, diagonal=720, frame_index=frame)
    assert info["score"] >= 55
    assert info["label"] in {"OLASI_KAVGA", "KAVGA"}


def test_group_pressure_raises_surrounded_low_motion_case():
    analyzer = MotionAnalyzer(debug_scoring=False)
    victim = motion(1, 180, 110, 270, 285, energy=0.08, chaos=0.05, speed=0.02)
    p2 = motion(2, 120, 105, 210, 280, energy=0.18, chaos=0.12, speed=0.18)
    p3 = motion(3, 245, 112, 335, 288, energy=0.16, chaos=0.10, speed=0.15)
    for m in [victim, p2, p3]:
        analyzer.history[m.track_id].extend([m, m])
    info = {}
    for frame in range(1, 5):
        info = analyzer._score_pair(victim, p2, diagonal=720, frame_index=frame, all_motions=[victim, p2, p3], frame_shape=(360, 640, 3))
    assert info["score"] < 55
    assert info["label"] != "KAVGA"
    assert "group_pressure" in info["reasons"]


def test_strong_group_pressure_reaches_fight_range():
    analyzer = MotionAnalyzer(debug_scoring=False)
    victim = motion(1, 180, 110, 270, 285, energy=0.04, chaos=0.04, speed=0.01)
    p2 = motion(2, 120, 105, 210, 280, energy=0.30, chaos=0.22, speed=0.24)
    p3 = motion(3, 235, 112, 325, 288, energy=0.28, chaos=0.24, speed=0.22)
    for m in [victim, p2, p3]:
        analyzer.history[m.track_id].extend([m, m])
    info = {}
    for frame in range(1, 6):
        info = analyzer._score_pair(victim, p2, diagonal=720, frame_index=frame, all_motions=[victim, p2, p3], frame_shape=(360, 640, 3))
    assert info["score"] >= 55
    assert info["label"] in {"OLASI_KAVGA", "KAVGA"}


def test_single_frame_spike_does_not_raise_alarm():
    alarm = AlarmManager()
    level, smoothed, consecutive = alarm.update(85)
    assert level == "NORMAL"
    assert consecutive == 1
    assert smoothed > 0


def test_alarm_thresholds_need_consecutive_frames():
    assert alarm_level(72, 1) == "NORMAL"
    assert alarm_level(35, 2) == "SUPHELI"
    assert alarm_level(56, 3) == "OLASI_KAVGA"
    assert alarm_level(76, 5) == "KAVGA"


def test_crowded_close_overlap_without_motion_cannot_be_fight():
    analyzer = MotionAnalyzer(debug_scoring=False)
    people = [
        motion(1, 100, 100, 190, 270, energy=0.06, chaos=0.04, speed=0.02),
        motion(2, 150, 105, 240, 275, energy=0.06, chaos=0.04, speed=0.02),
        motion(3, 210, 100, 300, 270, energy=0.05, chaos=0.04, speed=0.02),
        motion(4, 270, 105, 360, 275, energy=0.05, chaos=0.04, speed=0.02),
        motion(5, 330, 100, 420, 270, energy=0.05, chaos=0.04, speed=0.02),
    ]
    for person in people:
        analyzer.history[person.track_id].extend([person, person])
    info = {}
    for frame in range(1, 7):
        info = analyzer._score_pair(people[0], people[1], diagonal=720, frame_index=frame, all_motions=people, frame_shape=(360, 640, 3))
    assert info["score"] < 55
    assert info["label"] != "KAVGA"
    assert "crowd_penalty_applied" in info["penalties"] or "normal_close_contact_penalty_applied" in info["penalties"]


def test_bbox_overlap_ratio():
    assert bbox_overlap_ratio((0, 0, 10, 10), (5, 5, 15, 15)) == 0.25
