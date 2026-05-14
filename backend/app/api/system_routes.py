import platform

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.schemas.common import ok
from app.services.auth_service import get_current_user
from app.utils.ffmpeg_utils import ffmpeg_available


router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def system_status():
    settings = get_settings()
    cuda_available = False
    torch_version = None
    cuda_device = None
    cuda_version = None
    try:
        import torch

        torch_version = torch.__version__
        cuda_available = torch.cuda.is_available()
        cuda_device = torch.cuda.get_device_name(0) if cuda_available else None
        cuda_version = torch.version.cuda
    except Exception:
        pass
    try:
        import cv2

        opencv_version = cv2.__version__
    except Exception:
        opencv_version = None
    try:
        import ultralytics

        ultralytics_available = True
        ultralytics_version = ultralytics.__version__
    except Exception:
        ultralytics_available = False
        ultralytics_version = None
    profile = settings.analysis_profile()
    return ok(
        {
            "backend_status": "ok",
            "python": platform.python_version(),
            "python_version": platform.python_version(),
            "os": platform.platform(),
            "torch_version": torch_version,
            "cuda_available": cuda_available,
            "cuda_version": cuda_version,
            "device": "cuda:0" if cuda_available else "cpu",
            "cuda_device": cuda_device,
            "device_name": cuda_device,
            "opencv_version": opencv_version,
            "ultralytics_available": ultralytics_available,
            "ultralytics_version": ultralytics_version,
            "ffmpeg_available": ffmpeg_available(),
            "model": settings.yolo_model,
            "default_analysis_mode": settings.analysis_mode,
            "current_config": profile,
            "confidence": settings.confidence_threshold,
            "frame_skip": settings.frame_skip,
            "input_size": settings.input_size,
            "baseline_frame_count": settings.baseline_frame_count,
            "smoothing_window": settings.smoothing_window,
            "min_pair_proximity": settings.min_pair_proximity,
            "min_pair_overlap": settings.min_pair_overlap,
            "min_mutual_energy": settings.min_mutual_energy,
            "min_interaction_frames": settings.min_interaction_frames,
            "cooldown_seconds": settings.cooldown_seconds,
            "debug_scoring": settings.debug_scoring,
            "detection_mode": settings.detection_mode,
            "fight_thresholds": settings.fight_thresholds,
            "scoring_weights": settings.scoring_weights,
            "crowd_penalty_enabled": settings.crowd_penalty_enabled,
            "crowd_person_count_threshold": settings.crowd_person_count_threshold,
            "normal_close_contact_filter_enabled": settings.normal_close_contact_filter_enabled,
            "mandatory_fight_evidence_enabled": settings.mandatory_fight_evidence_enabled,
            "single_sided_motion_filter_enabled": settings.single_sided_motion_filter_enabled,
            "only_highlight_involved_persons": settings.only_highlight_involved_persons,
            "alarm_thresholds": settings.alarm_thresholds,
            "consecutive_frames": settings.consecutive_frames,
            "use_pose_contact_cues": settings.use_pose_contact_cues,
            "use_group_interaction_scoring": settings.use_group_interaction_scoring,
            "use_violence_classifier": settings.use_violence_classifier,
            "classifier_model_path": settings.classifier_model_path,
            "classifier_input_frames": settings.classifier_input_frames,
            "classifier_stride": settings.classifier_stride,
            "contact_persistence_min_frames": settings.contact_persistence_min_frames,
            "neck_proximity_threshold": settings.neck_proximity_threshold,
            "high_overlap_contact_threshold": settings.high_overlap_contact_threshold,
            "group_density_threshold": settings.group_density_threshold,
            "restraint_threshold": settings.restraint_threshold,
            "high_overlap_fight_floor": settings.high_overlap_fight_floor,
            "contact_fight_floor": settings.contact_fight_floor,
            "group_fight_floor": settings.group_fight_floor,
            "min_fight_contact_persistence": settings.min_fight_contact_persistence,
            "overlay_font_scale": settings.overlay_font_scale,
            "overlay_small_font_scale": settings.overlay_small_font_scale,
            "overlay_banner_height_ratio": settings.overlay_banner_height_ratio,
            "overlay_padding": settings.overlay_padding,
            "overlay_compact_mode": settings.overlay_compact_mode,
        }
    )
