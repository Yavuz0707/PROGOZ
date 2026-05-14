# Architecture

Backend FastAPI uzerinde API route, service, core CV ve model katmanlarina ayrilir. SQLite SQLAlchemy modelleri `users`, `cameras`, `analysis_jobs` ve `events` tablolarini olusturur.

Frontend React + Vite + TypeScript ile yazilmistir. Sayfalar login, dashboard, live camera, video upload, events, event detail, cameras ve settings olarak ayrilir.

WebSocket akislari:

- `/ws/live/{camera_id}`: frame status ve live event mesajlari
- `/ws/jobs`: genel job progress
- `/ws/jobs/{job_id}`: ilgili analiz isinin olay/log mesajlari

Kamera akisi `CameraStreamWorker` ile thread icinde OpenCV `VideoCapture` kullanir. Eski frameleri biriktirmek yerine son JPEG goruntu MJPEG endpointinden servis edilir.

Video upload analizi `BackgroundTasks` ile baslatilir. Job DB'de `queued`, `running`, `completed` veya `failed` durumuyla takip edilir.

Bildirim sistemi `notification_manager.py` ve `websocket_manager.py` ile soyutlanmistir; mobil push daha sonra eklenebilir.

