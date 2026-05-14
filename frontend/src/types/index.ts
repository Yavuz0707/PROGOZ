export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  message?: string;
  error?: string;
  detail?: string;
};

export type User = {
  id: number;
  username: string;
  email: string;
  role: "admin" | "operator";
};

export type Camera = {
  id: number;
  name: string;
  source_type: "rtsp" | "webcam" | "file";
  rtsp_url?: string;
  location?: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type EventRecord = {
  id: number;
  source_type: string;
  camera_id?: number;
  analysis_job_id?: number;
  severity: string;
  score: number;
  frame_index?: number;
  person_ids?: string;
  snapshot_url?: string;
  clip_url?: string;
  details_json?: string;
  created_at: string;
};

export type IncidentRecord = {
  id: number;
  source_type: "video" | "camera";
  camera_id?: number;
  analysis_job_id?: number;
  video_filename?: string;
  severity: string;
  status: "confirmed" | "false_positive" | "ignored";
  start_frame?: number;
  end_frame?: number;
  start_time_seconds?: number;
  end_time_seconds?: number;
  duration_seconds: number;
  started_at?: string;
  ended_at?: string;
  max_score: number;
  avg_score: number;
  best_snapshot_url?: string;
  best_snapshot_score?: number;
  clip_url?: string;
  involved_track_ids: number[];
  score_timeline: { t: number; score: number }[];
  details: Record<string, unknown>;
  created_at: string;
};

export type AnalysisJob = {
  id: number;
  filename: string;
  status: string;
  progress: number;
  total_frames: number;
  processed_frames: number;
  skipped_frames?: number;
  current_stage?: string;
  analysis_mode?: string;
  processed_video_exists?: boolean;
  processed_video_size?: number;
  performance?: Record<string, string | number | boolean | null>;
  processed_url?: string;
  original_url?: string;
  error_message?: string;
};

export type SystemStatus = {
  python: string;
  os: string;
  torch_version?: string;
  cuda_available: boolean;
  cuda_device?: string;
  device?: string;
  device_name?: string;
  opencv_version?: string;
  ultralytics_available?: boolean;
  ffmpeg_available: boolean;
  default_analysis_mode?: string;
  current_config?: Record<string, string | number | boolean>;
  model: string;
  confidence: number;
  frame_skip: number;
  input_size: number;
};
