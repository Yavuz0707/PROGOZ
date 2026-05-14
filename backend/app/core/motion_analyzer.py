from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import combinations
from logging import FileHandler, Formatter, getLogger
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from app.config import BASE_DIR, get_settings
from app.core.scoring import bbox_overlap_ratio, clamp, normalize, weighted_score


@dataclass
class TrackMotion:
    track_id: int
    bbox: tuple[int, int, int, int]
    center: tuple[float, float]
    area: float
    energy: float
    flow_mean: float
    flow_std: float
    speed: float
    size_variation: float
    center_movement: float
    direction_change: float
    activity: dict[str, float] = field(default_factory=dict)
    keypoints: list[dict[str, float]] = field(default_factory=list)


class MotionAnalyzer:
    def __init__(
        self,
        baseline_frames: int | None = None,
        history_size: int = 30,
        sensitivity: float | None = None,
        debug_scoring: bool | None = None,
    ) -> None:
        self.settings = get_settings()
        self.prev_gray: np.ndarray | None = None
        self.history: dict[int, deque[TrackMotion]] = defaultdict(lambda: deque(maxlen=history_size))
        self.pair_duration: dict[tuple[int, int], int] = defaultdict(int)
        self.contact_duration: dict[tuple[int, int], int] = defaultdict(int)
        self.baseline_frames = baseline_frames or self.settings.baseline_frame_count
        self.energy_baseline: deque[float] = deque(maxlen=self.baseline_frames)
        self.flow_cache: dict[int, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
        self.last_optical_flow_ms = 0.0
        self.sensitivity = self.settings.sensitivity if sensitivity is None else sensitivity
        self.debug_scoring = self.settings.debug_scoring if debug_scoring is None else debug_scoring
        self.logger = self._create_debug_logger()

    def _create_debug_logger(self):
        logger = getLogger("progoz.scoring")
        if self.debug_scoring and not logger.handlers:
            handler = FileHandler(BASE_DIR / "logs" / "scoring_debug.log", encoding="utf-8")
            handler.setFormatter(Formatter("%(asctime)s %(message)s"))
            logger.addHandler(handler)
            logger.setLevel("INFO")
            logger.propagate = False
        return logger

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (5, 5), 0)

    def analyze(
        self,
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        frame_index: int | None = None,
        optical_flow_enabled: bool = True,
    ) -> tuple[list[TrackMotion], dict[str, Any]]:
        gray = self.preprocess(frame)
        if self.prev_gray is None:
            self.prev_gray = gray
            return [], {"score": 0.0, "raw_score": 0.0, "criteria": {}, "penalties": {}, "pair": None, "label": "NORMAL"}

        motions: list[TrackMotion] = []
        frame_energies: list[float] = []
        flow_start = perf_counter()
        flow_count = 0
        h, w = gray.shape[:2]

        for det in detections:
            track_id = int(det.get("track_id") or det.get("id") or len(motions) + 1)
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            roi_now = gray[y1:y2, x1:x2]
            roi_prev = self.prev_gray[y1:y2, x1:x2]
            diff = cv2.absdiff(roi_prev, roi_now)
            energy = float(np.mean(diff))
            frame_energies.append(energy)

            flow_mean = 0.0
            flow_std = 0.0
            if optical_flow_enabled and roi_now.size > 0 and min(roi_now.shape[:2]) >= 8:
                small_now = cv2.resize(roi_now, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
                small_prev = cv2.resize(roi_prev, small_now.shape[::-1], interpolation=cv2.INTER_AREA)
                flow = cv2.calcOpticalFlowFarneback(small_prev, small_now, None, 0.5, 2, 11, 2, 5, 1.1, 0)
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                flow_mean = float(np.mean(mag))
                flow_std = float(np.std(mag))
                self.flow_cache[track_id] = (flow_mean, flow_std)
                flow_count += 1
            else:
                flow_mean, flow_std = self.flow_cache[track_id]

            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            area = float((x2 - x1) * (y2 - y1))
            previous = self.history[track_id][-1] if self.history[track_id] else None
            speed = float(np.linalg.norm(np.array(center) - np.array(previous.center))) if previous else 0.0
            size_variation = abs(area - previous.area) / max(previous.area, 1.0) if previous else 0.0
            direction_change = self._direction_change(track_id, center)
            activity = self._activity_scores(energy, flow_mean, flow_std, speed, size_variation, direction_change)
            motion = TrackMotion(
                track_id,
                (x1, y1, x2, y2),
                center,
                area,
                energy,
                flow_mean,
                flow_std,
                speed,
                size_variation,
                speed,
                direction_change,
                activity,
                det.get("keypoints") or [],
            )
            self.history[track_id].append(motion)
            motions.append(motion)

        if frame_energies:
            self.energy_baseline.append(float(np.mean(frame_energies)))
        self.last_optical_flow_ms = ((perf_counter() - flow_start) * 1000) if flow_count else 0.0
        score_info = self._score_pairs(motions, frame.shape, frame_index)
        self.prev_gray = gray
        return motions, score_info

    def _activity_scores(self, energy: float, flow_mean: float, flow_std: float, speed: float, size_variation: float, direction_change: float) -> dict[str, float]:
        baseline = self._energy_baseline()
        energy_score = normalize(energy, baseline * 0.75, baseline * self.settings.energy_active_multiplier)
        return {
            "motion_energy": energy_score,
            "optical_flow_mean": normalize(flow_mean, 0.05, self.settings.chaos_active_high),
            "chaos": normalize(flow_std, 0.05, self.settings.chaos_active_high),
            "speed": normalize(speed, 2.0, self.settings.speed_active_high_px),
            "bbox_area_variation": normalize(size_variation, 0.04, self.settings.size_variation_high),
            "center_movement": normalize(speed, 2.0, self.settings.speed_active_high_px),
            "direction_change": normalize(direction_change, 0.15, 2.4),
        }

    def _score_pairs(self, motions: list[TrackMotion], frame_shape: tuple[int, ...], frame_index: int | None) -> dict[str, Any]:
        if len(motions) < 2:
            return self._single_person_score(motions)

        best = {"score": 0.0, "raw_score": 0.0, "criteria": {}, "penalties": {}, "pair": None, "label": "NORMAL"}
        diagonal = float(np.linalg.norm(frame_shape[:2]))
        for a, b in combinations(motions, 2):
            info = self._score_pair(a, b, diagonal, frame_index, motions, frame_shape)
            if info["score"] > best["score"]:
                best = info
        return best

    def _single_person_score(self, motions: list[TrackMotion]) -> dict[str, Any]:
        if not motions:
            return {"score": 0.0, "raw_score": 0.0, "criteria": {}, "penalties": {}, "pair": None, "label": "NORMAL"}
        m = motions[0]
        activity_score = (
            m.activity["motion_energy"] * 0.35
            + m.activity["chaos"] * 0.20
            + m.activity["speed"] * 0.25
            + m.activity["bbox_area_variation"] * 0.20
        )
        score = min(18.0, activity_score * 22.0 * self.sensitivity)
        criteria = {"single_person_activity": round(activity_score, 3), **m.activity}
        return {"score": score, "raw_score": score, "criteria": criteria, "penalties": {"single_person_cap": 18.0}, "pair": (m.track_id,), "label": "NORMAL"}

    def _score_pair(
        self,
        a: TrackMotion,
        b: TrackMotion,
        diagonal: float,
        frame_index: int | None,
        all_motions: list[TrackMotion] | None = None,
        frame_shape: tuple[int, ...] | None = None,
    ) -> dict[str, Any]:
        pair = tuple(sorted((a.track_id, b.track_id)))
        distance = float(np.linalg.norm(np.array(a.center) - np.array(b.center)))
        proximity = clamp(1.0 - distance / max(diagonal * self.settings.pair_distance_scale, 1.0))
        overlap = bbox_overlap_ratio(a.bbox, b.bbox)
        mutual_energy = min(a.activity["motion_energy"], b.activity["motion_energy"])
        mutual_chaos = min(a.activity["chaos"], b.activity["chaos"])
        motion_asymmetry = max(
            abs(a.activity["motion_energy"] - b.activity["motion_energy"]),
            abs(a.activity["speed"] - b.activity["speed"]),
        )
        relative_speed = self._relative_speed_score(a, b)
        pose_contact = self._pose_contact_score(a, b) if self.settings.use_pose_contact_cues else 0.0
        persistent_contact_now = proximity >= max(0.48, self.settings.min_pair_proximity) or overlap >= self.settings.high_overlap_contact_threshold or pose_contact >= 0.38
        self.contact_duration[pair] = self.contact_duration[pair] + 1 if persistent_contact_now else max(0, self.contact_duration[pair] - 1)
        contact_persistence = normalize(float(self.contact_duration[pair]), 1.0, float(self.settings.contact_persistence_min_frames + 4))
        restraint = self._restraint_score(a, b, proximity, overlap, pose_contact, contact_persistence)
        pinned = self._pinned_against_surface_score(a, b, frame_shape, proximity, overlap)
        group_info = self._group_pressure_score(a, b, all_motions or [], diagonal, frame_shape) if self.settings.use_group_interaction_scoring else {}
        direction_or_size = max(
            min(a.activity["direction_change"], b.activity["direction_change"]),
            min(a.activity["bbox_area_variation"], b.activity["bbox_area_variation"]),
            pinned,
            group_info.get("group_density", 0.0) * 0.65,
        )
        contact_evidence = max(overlap, pose_contact, restraint, pinned, group_info.get("multi_person_contact", 0.0))
        interacting_now = (
            (proximity >= self.settings.min_pair_proximity or overlap >= self.settings.min_pair_overlap)
            and (mutual_energy >= self.settings.min_mutual_energy or contact_evidence >= 0.35)
        )
        self.pair_duration[pair] = self.pair_duration[pair] + 1 if interacting_now else max(0, self.pair_duration[pair] - 1)
        pair_duration_frames = self.pair_duration[pair]
        duration_score = normalize(float(self.pair_duration[pair]), 1.0, float(self.settings.min_interaction_frames + 3))
        person_count = len(all_motions or [])

        criteria = {
            "proximity": proximity,
            "mutual_energy": mutual_energy,
            "mutual_chaos": mutual_chaos,
            "overlap": overlap,
            "relative_speed": relative_speed,
            "motion_asymmetry": motion_asymmetry,
            "direction_or_size": direction_or_size,
            "interaction_duration": duration_score,
            "persistence_frames": float(pair_duration_frames),
            "person_count": float(person_count),
            "pose_contact": pose_contact,
            "contact_persistence": contact_persistence,
            "restraint": restraint,
            "pinned": pinned,
            "group_density": group_info.get("group_density", 0.0),
            "surrounded_person": group_info.get("surrounded_person", 0.0),
            "multi_person_contact": group_info.get("multi_person_contact", 0.0),
        }
        weighted_criteria = {
            "mutual_energy": mutual_energy,
            "mutual_chaos": mutual_chaos,
            "relative_motion": max(relative_speed, direction_or_size * 0.55),
            "temporal_persistence": max(contact_persistence, duration_score),
            "proximity": proximity,
            "overlap": overlap,
            "pose_contact": pose_contact,
        }
        raw_score = weighted_score(weighted_criteria, self.settings.scoring_weights, self.sensitivity)
        final_score, penalties = self._apply_pair_gates(raw_score, criteria, a, b)
        final_score = self._apply_contact_floors(final_score, criteria)
        final_score, evidence_penalties = self._apply_mandatory_fight_evidence(final_score, criteria)
        penalties.update(evidence_penalties)
        label = self._score_label(final_score)
        rounded_criteria = {key: round(value, 3) for key, value in criteria.items()}
        reasons = self._reason_codes(criteria, penalties)
        info = {
            "score": final_score,
            "raw_score": raw_score,
            "criteria": rounded_criteria,
            "penalties": penalties,
            "pair": pair,
            "label": label,
            "reasons": reasons,
        }
        self._debug_pair(frame_index, a.track_id, b.track_id, info)
        return info

    def _apply_pair_gates(self, raw_score: float, criteria: dict[str, float], a: TrackMotion, b: TrackMotion) -> tuple[float, dict[str, float]]:
        score = raw_score
        penalties: dict[str, float] = {}

        if criteria["proximity"] < self.settings.min_pair_proximity and criteria["overlap"] < self.settings.min_pair_overlap:
            penalties["far_pair"] = 0.25
            score *= penalties["far_pair"]
        strong_contact = max(
            criteria.get("pose_contact", 0.0),
            criteria.get("restraint", 0.0),
            criteria.get("pinned", 0.0),
            criteria.get("multi_person_contact", 0.0),
        )
        if criteria["mutual_energy"] < self.settings.min_mutual_energy and strong_contact < 0.60:
            penalties["low_mutual_energy"] = 0.50
            score *= penalties["low_mutual_energy"]
        one_sided = max(a.activity["motion_energy"], b.activity["motion_energy"]) > 0.55 and min(a.activity["motion_energy"], b.activity["motion_energy"]) < 0.22
        if self.settings.single_sided_motion_filter_enabled and one_sided:
            factor = 0.72 if criteria["pose_contact"] >= 0.60 else self.settings.single_sided_motion_penalty_factor
            penalties["single_sided_motion_penalty_applied"] = factor
            score *= factor
        if self.pair_duration[tuple(sorted((a.track_id, b.track_id)))] < self.settings.min_interaction_frames and strong_contact < 0.50:
            penalties["short_interaction"] = 0.55
            score *= penalties["short_interaction"]
        if criteria["overlap"] > self.settings.min_pair_overlap and criteria["mutual_energy"] < self.settings.min_mutual_energy and strong_contact < 0.38:
            penalties["passive_overlap"] = 0.55
            score *= penalties["passive_overlap"]
        if (
            self.settings.normal_close_contact_filter_enabled
            and criteria["proximity"] > 0.55
            and criteria["overlap"] >= self.settings.min_pair_overlap
            and criteria["mutual_energy"] < 0.24
            and criteria["mutual_chaos"] < 0.24
            and strong_contact < 0.60
        ):
            penalties["normal_close_contact_penalty_applied"] = self.settings.normal_close_contact_penalty_factor
            score *= self.settings.normal_close_contact_penalty_factor
        if (
            self.settings.crowd_penalty_enabled
            and criteria.get("person_count", 0.0) >= self.settings.crowd_person_count_threshold
            and criteria["mutual_chaos"] < 0.38
            and criteria["pose_contact"] < 0.60
        ):
            penalties["crowd_penalty_applied"] = self.settings.crowd_penalty_factor
            score *= self.settings.crowd_penalty_factor

        return clamp(score / 100.0, 0.0, 1.0) * 100.0, penalties

    def _apply_contact_floors(self, score: float, criteria: dict[str, float]) -> float:
        contact_persistent = criteria["contact_persistence"] >= 0.45 or criteria["interaction_duration"] >= 0.45
        high_close_overlap = criteria["proximity"] >= 0.55 and criteria["overlap"] >= self.settings.high_overlap_contact_threshold
        dynamic_contact = max(criteria["mutual_energy"], criteria["mutual_chaos"], criteria["relative_speed"], criteria["pose_contact"])
        if high_close_overlap and contact_persistent and dynamic_contact >= 0.32:
            score = max(score, self.settings.close_contact_low_motion_floor)
        if criteria["pose_contact"] >= 0.38 and criteria["proximity"] >= self.settings.min_pair_proximity and criteria["contact_persistence"] >= 0.30:
            score = max(score, self.settings.pose_contact_floor)
        if criteria["restraint"] >= self.settings.restraint_threshold and contact_persistent and dynamic_contact >= 0.32:
            score = max(score, self.settings.pose_contact_floor)
        if max(criteria["surrounded_person"], criteria["multi_person_contact"]) >= self.settings.group_density_threshold and dynamic_contact >= 0.32:
            score = max(score, self.settings.group_pressure_floor)
        fight_persistent = (
            criteria["contact_persistence"] >= self.settings.min_fight_contact_persistence
            or criteria["interaction_duration"] >= self.settings.min_fight_contact_persistence
        )
        violent_contact = (
            criteria["pose_contact"] >= 0.55
            and criteria["proximity"] >= self.settings.min_pair_proximity
            and criteria["restraint"] >= max(0.36, self.settings.restraint_threshold * 0.8)
            and fight_persistent
        )
        overlap_assault = (
            criteria["proximity"] >= 0.62
            and criteria["overlap"] >= max(self.settings.high_overlap_contact_threshold, 0.24)
            and fight_persistent
            and criteria["restraint"] >= max(0.48, self.settings.restraint_threshold)
            and max(criteria["mutual_chaos"], criteria["relative_speed"], criteria["pose_contact"], criteria.get("motion_asymmetry", 0.0)) >= 0.24
        )
        group_assault = (
            max(criteria["surrounded_person"], criteria["multi_person_contact"]) >= self.settings.group_density_threshold
            and (criteria["contact_persistence"] >= 0.34 or criteria["interaction_duration"] >= 0.34)
            and criteria["proximity"] >= self.settings.min_pair_proximity
            and max(criteria["mutual_energy"], criteria["mutual_chaos"], criteria["relative_speed"], criteria["pose_contact"]) >= 0.45
        )
        if overlap_assault:
            score = max(score, self.settings.high_overlap_fight_floor)
        if violent_contact:
            score = max(score, self.settings.contact_fight_floor)
        if group_assault:
            score = max(score, self.settings.group_fight_floor)
        score += max(criteria["pose_contact"] - 0.38, 0.0) * self.settings.contact_score_boost
        score += max(criteria["multi_person_contact"] - 0.45, 0.0) * self.settings.group_score_boost
        return min(score, 100.0)

    def _apply_mandatory_fight_evidence(self, score: float, criteria: dict[str, float]) -> tuple[float, dict[str, float]]:
        if not self.settings.mandatory_fight_evidence_enabled:
            return score, {}
        penalties: dict[str, float] = {}
        fight_threshold = self.settings.alarm_thresholds["KAVGA"]
        if score < fight_threshold:
            return score, penalties
        has_proximity = criteria["proximity"] > 0.55
        has_persistence = criteria.get("persistence_frames", 0.0) >= 4
        has_dynamic_evidence = (
            criteria["mutual_chaos"] > 0.50
            or criteria["mutual_energy"] > 0.55
            or criteria["pose_contact"] > 0.60
            or criteria["relative_speed"] > 0.55
        )
        if not (has_proximity and has_persistence and has_dynamic_evidence):
            penalties["mandatory_fight_evidence_blocked"] = 1.0
            score = min(score, self.settings.alarm_thresholds["KAVGA"] - 1.0)
        return score, penalties

    def _pose_contact_score(self, a: TrackMotion, b: TrackMotion) -> float:
        if not a.keypoints and not b.keypoints:
            return self._upper_body_overlap_contact(a, b) * 0.45
        return max(self._limb_to_upper_body_score(a, b), self._limb_to_upper_body_score(b, a), self._upper_body_overlap_contact(a, b) * 0.6)

    def _limb_to_upper_body_score(self, attacker: TrackMotion, target: TrackMotion) -> float:
        limb_points = self._valid_keypoints(attacker, [7, 8, 9, 10])
        if not limb_points:
            return 0.0
        targets = self._target_upper_body_points(target)
        if not targets:
            return 0.0
        bbox_h = max(1.0, float(target.bbox[3] - target.bbox[1]))
        best = 0.0
        for limb in limb_points:
            for target_point in targets:
                distance_ratio = float(np.linalg.norm(np.array(limb) - np.array(target_point))) / bbox_h
                best = max(best, 1.0 - distance_ratio / max(self.settings.neck_proximity_threshold, 1e-6))
        return clamp(best)

    def _target_upper_body_points(self, motion: TrackMotion) -> list[tuple[float, float]]:
        points = self._valid_keypoints(motion, [0, 1, 2, 3, 4, 5, 6])
        if points:
            return points
        x1, y1, x2, y2 = motion.bbox
        width = x2 - x1
        height = y2 - y1
        return [
            (x1 + width * 0.50, y1 + height * 0.16),
            (x1 + width * 0.50, y1 + height * 0.30),
            (x1 + width * 0.32, y1 + height * 0.34),
            (x1 + width * 0.68, y1 + height * 0.34),
        ]

    def _valid_keypoints(self, motion: TrackMotion, indices: list[int], min_confidence: float = 0.20) -> list[tuple[float, float]]:
        points = []
        for index in indices:
            if index >= len(motion.keypoints):
                continue
            point = motion.keypoints[index]
            if point.get("confidence", 1.0) >= min_confidence and point.get("x", 0.0) > 0 and point.get("y", 0.0) > 0:
                points.append((float(point["x"]), float(point["y"])))
        return points

    def _upper_body_overlap_contact(self, a: TrackMotion, b: TrackMotion) -> float:
        return bbox_overlap_ratio(self._upper_body_box(a), self._upper_body_box(b))

    def _upper_body_box(self, motion: TrackMotion) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = motion.bbox
        return (x1, y1, x2, int(y1 + (y2 - y1) * 0.48))

    def _restraint_score(self, a: TrackMotion, b: TrackMotion, proximity: float, overlap: float, pose_contact: float, contact_persistence: float) -> float:
        movement_a = max(a.activity["center_movement"], a.activity["motion_energy"] * 0.55)
        movement_b = max(b.activity["center_movement"], b.activity["motion_energy"] * 0.55)
        lower_motion = min(movement_a, movement_b)
        higher_motion = max(movement_a, movement_b)
        immobilized = clamp(1.0 - lower_motion / 0.32)
        pressure = max(proximity, overlap * 1.4, pose_contact)
        asymmetry = clamp(higher_motion - lower_motion)
        return clamp((immobilized * 0.42 + pressure * 0.38 + asymmetry * 0.20) * max(0.55, contact_persistence))

    def _pinned_against_surface_score(
        self,
        a: TrackMotion,
        b: TrackMotion,
        frame_shape: tuple[int, ...] | None,
        proximity: float,
        overlap: float,
    ) -> float:
        if not frame_shape:
            return 0.0
        height, width = frame_shape[:2]
        margin_x = width * self.settings.pinned_edge_margin_ratio
        margin_y = height * self.settings.pinned_edge_margin_ratio
        edge_a = self._edge_pressure(a, width, height, margin_x, margin_y)
        edge_b = self._edge_pressure(b, width, height, margin_x, margin_y)
        pressure = max(proximity, overlap)
        return max(edge_a, edge_b) * pressure

    def _edge_pressure(self, motion: TrackMotion, width: int, height: int, margin_x: float, margin_y: float) -> float:
        x1, y1, x2, y2 = motion.bbox
        near_edge = x1 <= margin_x or y1 <= margin_y or width - x2 <= margin_x or height - y2 <= margin_y
        low_mobility = 1.0 - max(motion.activity["center_movement"], motion.activity["speed"])
        return clamp(low_mobility if near_edge else 0.0)

    def _group_pressure_score(
        self,
        a: TrackMotion,
        b: TrackMotion,
        all_motions: list[TrackMotion],
        diagonal: float,
        frame_shape: tuple[int, ...] | None,
    ) -> dict[str, float]:
        if len(all_motions) < 3:
            return {"group_density": 0.0, "surrounded_person": 0.0, "multi_person_contact": 0.0}
        cluster = []
        for candidate in all_motions:
            distance_to_a = float(np.linalg.norm(np.array(candidate.center) - np.array(a.center)))
            distance_to_b = float(np.linalg.norm(np.array(candidate.center) - np.array(b.center)))
            close_to_pair = min(distance_to_a, distance_to_b) <= diagonal * self.settings.pair_distance_scale
            has_overlap = bbox_overlap_ratio(candidate.bbox, a.bbox) >= self.settings.min_pair_overlap or bbox_overlap_ratio(candidate.bbox, b.bbox) >= self.settings.min_pair_overlap
            if close_to_pair or has_overlap:
                cluster.append(candidate)
        if len(cluster) < 3:
            return {"group_density": 0.0, "surrounded_person": 0.0, "multi_person_contact": 0.0}
        centers = np.array([m.center for m in cluster])
        spread = float(np.mean(np.linalg.norm(centers - centers.mean(axis=0), axis=1)))
        density = clamp(1.0 - spread / max(diagonal * 0.18, 1.0))
        surrounded = 0.0
        multi_contact = 0.0
        for target in cluster:
            contacts = 0
            for other in cluster:
                if other.track_id == target.track_id:
                    continue
                proximity = clamp(1.0 - float(np.linalg.norm(np.array(target.center) - np.array(other.center))) / max(diagonal * self.settings.pair_distance_scale, 1.0))
                overlap = bbox_overlap_ratio(target.bbox, other.bbox)
                pose_contact = self._pose_contact_score(other, target) if self.settings.use_pose_contact_cues else 0.0
                if proximity >= 0.45 or overlap >= self.settings.min_pair_overlap or pose_contact >= 0.35:
                    contacts += 1
                    multi_contact = max(multi_contact, max(proximity, overlap, pose_contact))
            if contacts >= 2:
                low_mobility = 1.0 - max(target.activity["center_movement"], target.activity["speed"])
                edge_bonus = self._edge_pressure(target, frame_shape[1], frame_shape[0], frame_shape[1] * self.settings.pinned_edge_margin_ratio, frame_shape[0] * self.settings.pinned_edge_margin_ratio) if frame_shape else 0.0
                surrounded = max(surrounded, clamp(0.55 + low_mobility * 0.30 + edge_bonus * 0.15))
        return {
            "group_density": density,
            "surrounded_person": surrounded,
            "multi_person_contact": clamp(multi_contact * max(density, 0.45)),
        }

    def _reason_codes(self, criteria: dict[str, float], penalties: dict[str, float]) -> list[str]:
        reasons = []
        if criteria.get("pose_contact", 0.0) >= 0.38:
            reasons.append("pose_contact")
        if criteria.get("contact_persistence", 0.0) >= 0.45:
            reasons.append("persistent_contact")
        if criteria.get("overlap", 0.0) >= self.settings.high_overlap_contact_threshold:
            reasons.append("high_overlap")
        if criteria.get("restraint", 0.0) >= self.settings.restraint_threshold:
            reasons.append("restraint")
        if criteria.get("pinned", 0.0) >= 0.35:
            reasons.append("pinned")
        if criteria.get("multi_person_contact", 0.0) >= 0.45 or criteria.get("surrounded_person", 0.0) >= 0.45:
            reasons.append("group_pressure")
        if "mandatory_fight_evidence_blocked" in penalties:
            reasons.append("fight_evidence_blocked")
        if penalties:
            reasons.extend(f"penalty:{name}" for name in penalties)
        return reasons[:5]

    def _relative_speed_score(self, a: TrackMotion, b: TrackMotion) -> float:
        pair = tuple(sorted((a.track_id, b.track_id)))
        history_a = self.history[a.track_id]
        history_b = self.history[b.track_id]
        closing_speed = 0.0
        if len(history_a) >= 2 and len(history_b) >= 2:
            prev_distance = float(np.linalg.norm(np.array(history_a[-2].center) - np.array(history_b[-2].center)))
            curr_distance = float(np.linalg.norm(np.array(a.center) - np.array(b.center)))
            closing_speed = max(0.0, prev_distance - curr_distance)
        avg_speed = (a.speed + b.speed) / 2.0
        return max(
            normalize(closing_speed, 1.0, self.settings.speed_active_high_px * 0.55),
            normalize(avg_speed, 3.0, self.settings.speed_active_high_px),
        )

    def _direction_change(self, track_id: int, center: tuple[float, float]) -> float:
        history = self.history[track_id]
        if len(history) < 2:
            return 0.0
        p2 = np.array(history[-1].center)
        p1 = np.array(history[-2].center)
        p3 = np.array(center)
        v1 = p2 - p1
        v2 = p3 - p2
        if np.linalg.norm(v1) < 1e-6 or np.linalg.norm(v2) < 1e-6:
            return 0.0
        cosine = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        return float(np.arccos(np.clip(cosine, -1.0, 1.0)))

    def _energy_baseline(self) -> float:
        if len(self.energy_baseline) >= max(3, min(self.baseline_frames, 8)):
            return float(np.mean(self.energy_baseline))
        return self.settings.energy_baseline_default

    def _score_label(self, score: float) -> str:
        if score >= self.settings.alarm_thresholds["KAVGA"]:
            return "KAVGA"
        if score >= self.settings.alarm_thresholds["OLASI_KAVGA"]:
            return "OLASI_KAVGA"
        if score >= self.settings.alarm_thresholds["SUPHELI"]:
            return "SUPHELI"
        return "NORMAL"

    def _debug_pair(self, frame_index: int | None, person_id_1: int, person_id_2: int, info: dict[str, Any]) -> None:
        if not self.debug_scoring:
            return
        c = info["criteria"]
        self.logger.info(
            "frame_index=%s pair_ids=(%s,%s) proximity_score=%.3f overlap_score=%.3f "
            "mutual_energy_score=%.3f mutual_chaos_score=%.3f relative_motion_score=%.3f "
            "pose_contact_score=%.3f persistence_frames=%s crowd_penalty_applied=%s "
            "normal_close_contact_penalty_applied=%s single_sided_motion_penalty_applied=%s "
            "raw_score=%.2f final_score=%.2f final_label=%s reasons=%s penalties=%s",
            frame_index,
            person_id_1,
            person_id_2,
            c.get("proximity", 0.0),
            c.get("overlap", 0.0),
            c.get("mutual_energy", 0.0),
            c.get("mutual_chaos", 0.0),
            c.get("relative_speed", 0.0),
            c.get("pose_contact", 0.0),
            int(c.get("persistence_frames", 0.0)),
            "crowd_penalty_applied" in info["penalties"],
            "normal_close_contact_penalty_applied" in info["penalties"],
            "single_sided_motion_penalty_applied" in info["penalties"],
            info["raw_score"],
            info["score"],
            info["label"],
            info.get("reasons", []),
            info["penalties"],
        )
