from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.config import BASE_DIR, get_settings


class FightClassifierRuntime:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        self.device = "cpu"
        self.load_error: str | None = None
        self.clip_len = self.settings.fight_classifier_clip_len
        self.frame_size = self.settings.fight_classifier_frame_size
        self._load()

    @property
    def available(self) -> bool:
        return self.model is not None

    def _load(self) -> None:
        if not self.settings.fight_classifier_enabled:
            self.load_error = "Fight classifier disabled."
            return
        model_path = Path(self.settings.fight_classifier_model_path)
        if not model_path.is_absolute():
            model_path = BASE_DIR / model_path
        if not model_path.exists():
            self.load_error = f"Fight classifier model not found, using heuristic scoring only: {model_path}"
            return
        try:
            import torch
            from ml.training.fight.model import FightCNNLSTM

            checkpoint = torch.load(model_path, map_location="cpu")
            self.clip_len = int(checkpoint.get("clip_len", self.clip_len))
            self.frame_size = int(checkpoint.get("frame_size", self.frame_size))
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = FightCNNLSTM().to(self.device)
            self.model.load_state_dict(checkpoint["model_state"])
            self.model.eval()
            self.load_error = None
        except Exception as exc:
            self.model = None
            self.load_error = str(exc)

    def predict(self, frames: list[np.ndarray]) -> float | None:
        if self.model is None or len(frames) < self.clip_len:
            return None
        try:
            import torch

            selected = frames[-self.clip_len :]
            tensor = self._frames_to_tensor(selected).unsqueeze(0).to(self.device)
            with torch.no_grad():
                prob = torch.sigmoid(self.model(tensor)).item()
            return float(prob)
        except Exception as exc:
            self.load_error = str(exc)
            return None

    def _frames_to_tensor(self, frames: list[np.ndarray]):
        import torch

        items = []
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        for frame in frames:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (self.frame_size, self.frame_size), interpolation=cv2.INTER_AREA)
            arr = resized.astype(np.float32) / 255.0
            arr = (arr - mean) / std
            items.append(torch.from_numpy(arr).permute(2, 0, 1))
        return torch.stack(items)


class FightClipBuffer:
    def __init__(self, maxlen: int) -> None:
        self.frames: deque[np.ndarray] = deque(maxlen=maxlen)

    def append(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def ready(self, clip_len: int) -> bool:
        return len(self.frames) >= clip_len

    def latest(self, clip_len: int) -> list[np.ndarray]:
        return list(self.frames)[-clip_len:]


def fuse_classifier_score(score_info: dict[str, Any], classifier_probability: float | None) -> dict[str, Any]:
    if classifier_probability is None:
        return score_info
    criteria = score_info.get("criteria", {})
    interaction_score = float(score_info.get("score", 0.0))
    optical_flow_score = float(criteria.get("mutual_chaos", criteria.get("chaos", 0.0))) * 100.0
    pose_contact_score = float(criteria.get("pose_contact", 0.0)) * 100.0
    final_score = (
        0.60 * classifier_probability * 100.0
        + 0.20 * interaction_score
        + 0.10 * optical_flow_score
        + 0.10 * pose_contact_score
    )
    updated = dict(score_info)
    updated["heuristic_score"] = interaction_score
    updated["classifier_score"] = round(classifier_probability * 100.0, 3)
    updated["score"] = max(interaction_score, min(final_score, 100.0))
    updated["reasons"] = list(score_info.get("reasons", [])) + ["fight_classifier"]
    return updated


@lru_cache(maxsize=1)
def get_fight_classifier() -> FightClassifierRuntime:
    return FightClassifierRuntime()
