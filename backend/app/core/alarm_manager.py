from collections import deque
from dataclasses import dataclass, field

from app.config import get_settings
from app.core.scoring import alarm_level, weighted_temporal_average

LEVEL_ORDER = {"NORMAL": 0, "SUPHELI": 1, "OLASI_KAVGA": 2, "KAVGA": 3}


@dataclass
class AlarmState:
    recent_scores: deque = field(default_factory=deque)
    consecutive: int = 0
    level: str = "NORMAL"


class AlarmManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.state = AlarmState(recent_scores=deque(maxlen=self.settings.smoothing_window))

    def update(self, raw_score: float) -> tuple[str, float, int]:
        self.state.recent_scores.append(raw_score)
        smoothed = weighted_temporal_average(self.state.recent_scores, self.settings.smoothing_window)
        suspect_threshold = self.settings.alarm_thresholds["SUPHELI"]
        self.state.consecutive = self.state.consecutive + 1 if smoothed >= suspect_threshold else 0
        next_level = alarm_level(smoothed, self.state.consecutive, self.settings.alarm_thresholds, self.settings.consecutive_frames)
        self.state.level = self._apply_hysteresis(self.state.level, next_level, smoothed)
        return self.state.level, smoothed, self.state.consecutive

    def _apply_hysteresis(self, current: str, candidate: str, score: float) -> str:
        if LEVEL_ORDER[candidate] >= LEVEL_ORDER[current]:
            return candidate
        if current == "KAVGA" and score >= self.settings.alarm_thresholds["OLASI_KAVGA"] - 4:
            return current
        if current == "OLASI_KAVGA" and score >= self.settings.alarm_thresholds["SUPHELI"] - 4:
            return current
        if current == "SUPHELI" and score >= self.settings.alarm_thresholds["SUPHELI"] - 6:
            return current
        return candidate


def cap_level(level: str, max_level: str) -> str:
    if LEVEL_ORDER.get(level, 0) <= LEVEL_ORDER.get(max_level, 0):
        return level
    return max_level
