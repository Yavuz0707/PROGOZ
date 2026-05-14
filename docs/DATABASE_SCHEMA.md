# Database Schema

## users

`id`, `username`, `email`, `hashed_password`, `role`, `is_active`, `created_at`

## cameras

`id`, `name`, `source_type`, `rtsp_url`, `location`, `enabled`, `created_at`, `updated_at`

## analysis_jobs

`id`, `filename`, `original_path`, `processed_path`, `status`, `progress`, `total_frames`, `processed_frames`, `started_at`, `finished_at`, `error_message`

## events

`id`, `source_type`, `camera_id`, `analysis_job_id`, `event_type`, `severity`, `score`, `started_at`, `ended_at`, `frame_index`, `person_ids`, `snapshot_path`, `clip_path`, `details_json`, `created_at`

## system_logs

Opsiyonel olarak sonraki surumde eklenebilir: `id`, `level`, `message`, `created_at`.

