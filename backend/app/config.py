from functools import lru_cache
from pathlib import Path
from typing import List
import os
import json

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    app_name: str = "PROGOZ - Proaktif Gozetim Sistemi"
    api_prefix: str = "/api"
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'progoz.db'}")
    secret_key: str = os.getenv("SECRET_KEY", "change-this-secret-before-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    cors_origins: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ]
    static_dir: Path = BASE_DIR / "app" / "static"
    upload_dir: Path = static_dir / "uploads"
    processed_dir: Path = static_dir / "processed"
    snapshot_dir: Path = static_dir / "snapshots"
    clip_dir: Path = static_dir / "clips"
    plate_snapshot_dir: Path = static_dir / "plates"
    plate_crop_dir: Path = static_dir / "plate_crops"
    plate_debug_dir: Path = static_dir / "plate_debug"
    yolo_model: str = os.getenv("YOLO_MODEL", "yolov8n-pose.pt")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    frame_skip: int = int(os.getenv("FRAME_SKIP", "2"))
    input_size: int = int(os.getenv("INPUT_SIZE", "640"))
    analysis_mode: str = os.getenv("ANALYSIS_MODE", "fast").lower()
    analysis_modes: dict[str, dict] = json.loads(
        os.getenv(
            "ANALYSIS_MODES",
            '{"realtime":{"input_size":640,"frame_skip":3,"yolo_interval":3,"optical_flow_interval":5,"max_fps":15,"save_processed_video":false,"drop_old_frames":true,"output_fps":15},'
            '"fast":{"input_size":640,"frame_skip":3,"yolo_interval":3,"optical_flow_interval":3,"max_fps":0,"save_processed_video":true,"drop_old_frames":true,"output_fps":10},'
            '"balanced":{"input_size":720,"frame_skip":2,"yolo_interval":2,"optical_flow_interval":2,"max_fps":0,"save_processed_video":true,"drop_old_frames":true,"output_fps":15},'
            '"accurate":{"input_size":960,"frame_skip":1,"yolo_interval":1,"optical_flow_interval":1,"max_fps":0,"save_processed_video":true,"drop_old_frames":false,"output_fps":0}}',
        )
    )
    sensitivity: float = float(os.getenv("SENSITIVITY", "1.0"))
    baseline_frame_count: int = int(os.getenv("BASELINE_FRAME_COUNT", "30"))
    smoothing_window: int = int(os.getenv("SMOOTHING_WINDOW", "15"))
    min_pair_proximity: float = float(os.getenv("MIN_PAIR_PROXIMITY", "0.28"))
    min_pair_overlap: float = float(os.getenv("MIN_PAIR_OVERLAP", "0.03"))
    min_mutual_energy: float = float(os.getenv("MIN_MUTUAL_ENERGY", "0.22"))
    min_interaction_frames: int = int(os.getenv("MIN_INTERACTION_FRAMES", "3"))
    pair_distance_scale: float = float(os.getenv("PAIR_DISTANCE_SCALE", "0.34"))
    energy_baseline_default: float = float(os.getenv("ENERGY_BASELINE_DEFAULT", "12.0"))
    energy_active_multiplier: float = float(os.getenv("ENERGY_ACTIVE_MULTIPLIER", "3.0"))
    chaos_active_high: float = float(os.getenv("CHAOS_ACTIVE_HIGH", "2.5"))
    speed_active_high_px: float = float(os.getenv("SPEED_ACTIVE_HIGH_PX", "42.0"))
    size_variation_high: float = float(os.getenv("SIZE_VARIATION_HIGH", "0.65"))
    cooldown_seconds: float = float(os.getenv("COOLDOWN_SECONDS", "8.0"))
    incident_enabled: bool = os.getenv("INCIDENT_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    incident_min_frames_suspicious: int = int(os.getenv("INCIDENT_MIN_FRAMES_SUSPICIOUS", "5"))
    incident_min_frames_possible_fight: int = int(os.getenv("INCIDENT_MIN_FRAMES_POSSIBLE_FIGHT", "8"))
    incident_min_frames_fight: int = int(os.getenv("INCIDENT_MIN_FRAMES_FIGHT", "12"))
    incident_min_duration_suspicious: float = float(os.getenv("INCIDENT_MIN_DURATION_SUSPICIOUS", "0.5"))
    incident_min_duration_possible_fight: float = float(os.getenv("INCIDENT_MIN_DURATION_POSSIBLE_FIGHT", "0.8"))
    incident_min_duration_fight: float = float(os.getenv("INCIDENT_MIN_DURATION_FIGHT", "1.2"))
    incident_merge_gap_seconds: float = float(os.getenv("INCIDENT_MERGE_GAP_SECONDS", "3.0"))
    incident_end_grace_seconds: float = float(os.getenv("INCIDENT_END_GRACE_SECONDS", "1.0"))
    incident_min_score_to_start: float = float(os.getenv("INCIDENT_MIN_SCORE_TO_START", "35.0"))
    save_frame_level_events: bool = os.getenv("SAVE_FRAME_LEVEL_EVENTS", "false").lower() in {"1", "true", "yes", "on"}
    save_processed_video_default: bool = os.getenv("SAVE_PROCESSED_VIDEO_DEFAULT", "false").lower() in {"1", "true", "yes", "on"}
    save_best_snapshot: bool = os.getenv("SAVE_BEST_SNAPSHOT", "true").lower() in {"1", "true", "yes", "on"}
    save_score_timeline: bool = os.getenv("SAVE_SCORE_TIMELINE", "true").lower() in {"1", "true", "yes", "on"}
    events_page_show_incidents_only: bool = os.getenv("EVENTS_PAGE_SHOW_INCIDENTS_ONLY", "true").lower() in {"1", "true", "yes", "on"}
    debug_scoring: bool = os.getenv("DEBUG_SCORING", "false").lower() in {"1", "true", "yes", "on"}
    detection_mode: str = os.getenv("DETECTION_MODE", "balanced").lower()
    fight_thresholds: dict[str, dict[str, float]] = json.loads(
        os.getenv(
            "FIGHT_THRESHOLDS",
            '{"balanced":{"SUPHELI":35,"OLASI_KAVGA":55,"KAVGA":75},"high_sensitivity":{"SUPHELI":30,"OLASI_KAVGA":45,"KAVGA":65}}',
        )
    )
    scoring_weights: dict[str, float] = json.loads(
        os.getenv(
            "SCORING_WEIGHTS",
            '{"mutual_energy":0.25,"mutual_chaos":0.25,"relative_motion":0.15,"temporal_persistence":0.15,"proximity":0.10,"overlap":0.05,"pose_contact":0.05}',
        )
    )
    crowd_penalty_enabled: bool = os.getenv("CROWD_PENALTY_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    crowd_person_count_threshold: int = int(os.getenv("CROWD_PERSON_COUNT_THRESHOLD", "5"))
    normal_close_contact_filter_enabled: bool = os.getenv("NORMAL_CLOSE_CONTACT_FILTER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    mandatory_fight_evidence_enabled: bool = os.getenv("MANDATORY_FIGHT_EVIDENCE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    single_sided_motion_filter_enabled: bool = os.getenv("SINGLE_SIDED_MOTION_FILTER_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    only_highlight_involved_persons: bool = os.getenv("ONLY_HIGHLIGHT_INVOLVED_PERSONS", "true").lower() in {"1", "true", "yes", "on"}
    crowd_penalty_factor: float = float(os.getenv("CROWD_PENALTY_FACTOR", "0.55"))
    normal_close_contact_penalty_factor: float = float(os.getenv("NORMAL_CLOSE_CONTACT_PENALTY_FACTOR", "0.35"))
    single_sided_motion_penalty_factor: float = float(os.getenv("SINGLE_SIDED_MOTION_PENALTY_FACTOR", "0.45"))
    use_pose_contact_cues: bool = os.getenv("USE_POSE_CONTACT_CUES", "true").lower() in {"1", "true", "yes", "on"}
    use_group_interaction_scoring: bool = os.getenv("USE_GROUP_INTERACTION_SCORING", "true").lower() in {"1", "true", "yes", "on"}
    fight_classifier_enabled: bool = os.getenv("FIGHT_CLASSIFIER_ENABLED", os.getenv("USE_VIOLENCE_CLASSIFIER", "false")).lower() in {"1", "true", "yes", "on"}
    fight_classifier_model_path: str = os.getenv("FIGHT_CLASSIFIER_MODEL_PATH", os.getenv("CLASSIFIER_MODEL_PATH", "ml/models/fight/fight_classifier.pt"))
    fight_classifier_clip_len: int = int(os.getenv("FIGHT_CLASSIFIER_CLIP_LEN", os.getenv("CLASSIFIER_INPUT_FRAMES", "16")))
    fight_classifier_frame_size: int = int(os.getenv("FIGHT_CLASSIFIER_FRAME_SIZE", "224"))
    fight_classifier_interval: int = int(os.getenv("FIGHT_CLASSIFIER_INTERVAL", os.getenv("CLASSIFIER_STRIDE", "5")))
    use_violence_classifier: bool = fight_classifier_enabled
    classifier_model_path: str = fight_classifier_model_path
    classifier_input_frames: int = fight_classifier_clip_len
    classifier_stride: int = fight_classifier_interval
    contact_persistence_min_frames: int = int(os.getenv("CONTACT_PERSISTENCE_MIN_FRAMES", "3"))
    neck_proximity_threshold: float = float(os.getenv("NECK_PROXIMITY_THRESHOLD", "0.18"))
    upper_body_contact_threshold: float = float(os.getenv("UPPER_BODY_CONTACT_THRESHOLD", "0.10"))
    high_overlap_contact_threshold: float = float(os.getenv("HIGH_OVERLAP_CONTACT_THRESHOLD", "0.18"))
    group_density_threshold: float = float(os.getenv("GROUP_DENSITY_THRESHOLD", "0.55"))
    restraint_threshold: float = float(os.getenv("RESTRAINT_THRESHOLD", "0.45"))
    pinned_edge_margin_ratio: float = float(os.getenv("PINNED_EDGE_MARGIN_RATIO", "0.06"))
    contact_score_boost: float = float(os.getenv("CONTACT_SCORE_BOOST", "18.0"))
    group_score_boost: float = float(os.getenv("GROUP_SCORE_BOOST", "14.0"))
    close_contact_low_motion_floor: float = float(os.getenv("CLOSE_CONTACT_LOW_MOTION_FLOOR", "34.0"))
    pose_contact_floor: float = float(os.getenv("POSE_CONTACT_FLOOR", "42.0"))
    group_pressure_floor: float = float(os.getenv("GROUP_PRESSURE_FLOOR", "40.0"))
    high_overlap_fight_floor: float = float(os.getenv("HIGH_OVERLAP_FIGHT_FLOOR", "58.0"))
    contact_fight_floor: float = float(os.getenv("CONTACT_FIGHT_FLOOR", "76.0"))
    group_fight_floor: float = float(os.getenv("GROUP_FIGHT_FLOOR", "58.0"))
    min_fight_contact_persistence: float = float(os.getenv("MIN_FIGHT_CONTACT_PERSISTENCE", "0.42"))
    alarm_thresholds: dict[str, float] = json.loads(os.getenv("ALARM_THRESHOLDS", json.dumps(fight_thresholds.get(detection_mode, fight_thresholds["balanced"]))))
    consecutive_frames: dict[str, int] = json.loads(os.getenv("CONSECUTIVE_FRAMES", '{"SUPHELI":2,"OLASI_KAVGA":3,"KAVGA":5}'))
    overlay_font_scale: float = float(os.getenv("OVERLAY_FONT_SCALE", "0.52"))
    overlay_font_thickness: int = int(os.getenv("OVERLAY_FONT_THICKNESS", "1"))
    overlay_small_font_scale: float = float(os.getenv("OVERLAY_SMALL_FONT_SCALE", "0.42"))
    overlay_banner_height_ratio: float = float(os.getenv("OVERLAY_BANNER_HEIGHT_RATIO", "0.055"))
    overlay_padding: int = int(os.getenv("OVERLAY_PADDING", "8"))
    overlay_compact_mode: bool = os.getenv("OVERLAY_COMPACT_MODE", "true").lower() in {"1", "true", "yes", "on"}
    plate_recognition_enabled: bool = os.getenv("PLATE_RECOGNITION_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    plate_detector_model_path: str = os.getenv("PLATE_DETECTOR_MODEL_PATH", "ml/models/plates/license_plate_detector.pt")
    plate_detector_imgsz: int = int(os.getenv("PLATE_DETECTOR_IMGSZ", "640"))
    plate_detector_confidence: float = float(os.getenv("PLATE_DETECTOR_CONFIDENCE", "0.25"))
    plate_ocr_engine: str = os.getenv("PLATE_OCR_ENGINE", "easyocr").lower()
    plate_ocr_languages: list[str] = [
        lang.strip()
        for lang in os.getenv("PLATE_OCR_LANGUAGES", "en").split(",")
        if lang.strip()
    ]
    plate_ocr_min_confidence: float = float(os.getenv("PLATE_OCR_MIN_CONFIDENCE", "0.30"))
    plate_save_uncertain: bool = os.getenv("PLATE_SAVE_UNCERTAIN", "true").lower() in {"1", "true", "yes", "on"}
    plate_save_unreadable: bool = os.getenv("PLATE_SAVE_UNREADABLE", "false").lower() in {"1", "true", "yes", "on"}
    plate_show_unreadable_in_default_list: bool = os.getenv("PLATE_SHOW_UNREADABLE_IN_DEFAULT_LIST", "false").lower() in {"1", "true", "yes", "on"}
    plate_min_text_length_to_save: int = int(os.getenv("PLATE_MIN_TEXT_LENGTH_TO_SAVE", "5"))
    plate_require_valid_format_for_default: bool = os.getenv("PLATE_REQUIRE_VALID_FORMAT_FOR_DEFAULT", "false").lower() in {"1", "true", "yes", "on"}
    plate_test_image_auth_required: bool = os.getenv("PLATE_TEST_IMAGE_AUTH_REQUIRED", "false").lower() in {"1", "true", "yes", "on"}
    plate_debug_enabled: bool = os.getenv("PLATE_DEBUG_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    plate_frame_interval_fast: int = int(os.getenv("PLATE_FRAME_INTERVAL_FAST", "5"))
    plate_frame_interval_balanced: int = int(os.getenv("PLATE_FRAME_INTERVAL_BALANCED", "3"))
    plate_frame_interval_accurate: int = int(os.getenv("PLATE_FRAME_INTERVAL_ACCURATE", "1"))
    plate_dedup_window_seconds: int = int(os.getenv("PLATE_DEDUP_WINDOW_SECONDS", "30"))
    plate_retention_days: int = int(os.getenv("PLATE_RETENTION_DAYS", "7"))
    plate_save_snapshots: bool = os.getenv("PLATE_SAVE_SNAPSHOTS", "true").lower() in {"1", "true", "yes", "on"}
    plate_save_crops: bool = os.getenv("PLATE_SAVE_CROPS", "true").lower() in {"1", "true", "yes", "on"}
    plate_cleanup_on_startup: bool = os.getenv("PLATE_CLEANUP_ON_STARTUP", "true").lower() in {"1", "true", "yes", "on"}
    plate_regex_country: str = os.getenv("PLATE_REGEX_COUNTRY", "TR")
    allowed_video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    def analysis_profile(self, mode: str | None = None) -> dict:
        selected = (mode or self.analysis_mode or "fast").lower()
        profile = dict(self.analysis_modes.get(selected, self.analysis_modes["fast"]))
        profile["mode"] = selected if selected in self.analysis_modes else "fast"
        profile.setdefault("input_size", self.input_size)
        profile.setdefault("frame_skip", self.frame_skip)
        profile.setdefault("yolo_interval", profile["frame_skip"])
        profile.setdefault("optical_flow_interval", profile["frame_skip"])
        profile.setdefault("save_processed_video", True)
        profile.setdefault("output_fps", 0)
        return profile

    def plate_frame_interval(self, mode: str | None = None) -> int:
        selected = (mode or self.analysis_mode or "fast").lower()
        intervals = {
            "fast": self.plate_frame_interval_fast,
            "balanced": self.plate_frame_interval_balanced,
            "accurate": self.plate_frame_interval_accurate,
            "realtime": self.plate_frame_interval_balanced,
        }
        return max(1, int(intervals.get(selected, self.plate_frame_interval_balanced)))

    def ensure_directories(self) -> None:
        for path in [self.upload_dir, self.processed_dir, self.snapshot_dir, self.clip_dir, self.plate_snapshot_dir, self.plate_crop_dir, self.plate_debug_dir, BASE_DIR / "logs"]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
