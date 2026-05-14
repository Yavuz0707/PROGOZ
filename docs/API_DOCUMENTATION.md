# API Documentation

Tum basarili yanitlar:

```json
{ "success": true, "data": {}, "message": "OK" }
```

Hata yanitlari:

```json
{ "success": false, "error": "server_error", "detail": "..." }
```

Auth:

- `POST /api/auth/login` body `{ "username": "admin", "password": "admin123" }`
- `GET /api/auth/me`
- `POST /api/auth/logout`

Cameras:

- `GET /api/cameras`
- `POST /api/cameras`
- `GET /api/cameras/{id}`
- `PUT /api/cameras/{id}`
- `DELETE /api/cameras/{id}`
- `POST /api/cameras/{id}/start`
- `POST /api/cameras/{id}/stop`

Uploads:

- `POST /api/uploads/analyze` multipart `file`
- `GET /api/uploads/jobs`
- `GET /api/uploads/jobs/{job_id}`
- `GET /api/uploads/jobs/{job_id}/result`

Events:

- `GET /api/events`
- `GET /api/events/{id}`
- `DELETE /api/events/{id}`
- `GET /api/events/stats`
- `GET /api/events/export/csv`

System:

- `GET /api/system/status`

WebSocket:

```json
{ "type": "frame_status", "camera_id": 1, "fps": 24.5, "latency_ms": 120, "alarm_level": "NORMAL", "score": 12.4 }
```

```json
{ "type": "event", "severity": "KAVGA", "score": 72.5, "camera_id": 1, "snapshot_url": "/static/snapshots/event.jpg", "created_at": "..." }
```

```json
{ "type": "job_progress", "job_id": 5, "progress": 43, "processed_frames": 1200, "total_frames": 2800 }
```

