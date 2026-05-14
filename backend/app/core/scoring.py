from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple
import math


DEFAULT_PAIR_WEIGHTS = {
    "mutual_energy": 0.25,
    "mutual_chaos": 0.25,
    "relative_motion": 0.15,
    "temporal_persistence": 0.15,
    "proximity": 0.10,
    "overlap": 0.05,
    "pose_contact": 0.05,
}


@dataclass
class ScoreBreakdown:
    raw_score: float
    final_score: float
    person_pair: Tuple[int, int] | None = None
    criteria: Dict[str, float] = field(default_factory=dict)
    penalties: Dict[str, float] = field(default_factory=dict)
    label: str = "NORMAL"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def clamp_score(value: float) -> float:
    return clamp(value, 0.0, 100.0)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return default if abs(denominator) < 1e-9 else numerator / denominator


def normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return clamp((value - low) / (high - low))


def smooth_score(scores: Iterable[float], window: int = 15) -> float:
    values = list(scores)[-window:]
    if not values:
        return 0.0
    weights = list(range(1, len(values) + 1))
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def weighted_temporal_average(scores: Iterable[float], window: int = 15) -> float:
    return smooth_score(scores, window)


def calibrated_score(raw_0_1: float) -> float:
    """Keep weak evidence low and separate true pair interaction more clearly."""
    x = clamp(raw_0_1)
    if x < 0.18:
        return x * 75.0
    if x < 0.55:
        return 13.5 + (x - 0.18) * 95.0
    return 48.65 + (1.0 - math.exp(-3.2 * (x - 0.55))) * 55.0


def weighted_score(criteria: Dict[str, float], weights: Dict[str, float] | None = None, sensitivity: float = 1.0) -> float:
    active_weights = weights or DEFAULT_PAIR_WEIGHTS
    total_weight = sum(active_weights.values()) or 1.0
    total = 0.0
    for name, weight in active_weights.items():
        value = criteria.get(name, 0.0)
        if value > 1.0:
            value = value / 100.0
        total += clamp(value) * weight
    return clamp_score(calibrated_score(total / total_weight) * sensitivity)


def alarm_level(score: float, consecutive: int, thresholds: dict[str, float] | None = None, consecutive_frames: dict[str, int] | None = None) -> str:
    thresholds = thresholds or {"SUPHELI": 35, "OLASI_KAVGA": 55, "KAVGA": 75}
    consecutive_frames = consecutive_frames or {"SUPHELI": 2, "OLASI_KAVGA": 3, "KAVGA": 5}
    if score >= thresholds["KAVGA"] and consecutive >= consecutive_frames["KAVGA"]:
        return "KAVGA"
    if score >= thresholds["OLASI_KAVGA"] and consecutive >= consecutive_frames["OLASI_KAVGA"]:
        return "OLASI_KAVGA"
    if score >= thresholds["SUPHELI"] and consecutive >= consecutive_frames["SUPHELI"]:
        return "SUPHELI"
    return "NORMAL"


def bbox_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return clamp(inter / min(area_a, area_b))
