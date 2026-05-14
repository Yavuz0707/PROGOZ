# AGENTS - PROGOZ

## Proje Amaci

PROGOZ, guvenlik kameralari ve yuklenen videolar uzerinde kavga/anomali sinyallerini tespit eden web tabanli bir gozetim sistemidir. Mobil uygulama bu asamada kapsam disidir; `notification_manager.py` ileride Firebase/FCM veya benzeri servislerle genisletilebilir.

## Calisma Komutlari

Backend:

```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

Test:

```powershell
pytest
```

## Kod Kurallari

- Backend modulleri `backend/app` altinda tutulur.
- Dosya yollari icin `pathlib` tercih edilir.
- API response formati `{ success, data, message }` ve hata icin `{ success, error, detail }` seklindedir.
- Uzun video islemleri request thread'ini kilitlemeden background task olarak calisir.
- CV pipeline'da GPU varsa CUDA kullanilir, yoksa CPU fallback yapilir.

## Mimari Kararlar

- FastAPI async endpointleri, SQLAlchemy SQLite persist katmani, React Vite panel.
- YOLO tracking Ultralytics `model.track(..., tracker="bytetrack.yaml")` ile yapilir.
- Frame differencing ve Farneback optical flow kisi ROI'lerinde hesaplanir.
- Event olusturma tek noktadan `event_service.create_event` ile yapilir.

## Yeni Ozellik Eklerken

- Event, job veya kamera davranisi degisirse ilgili docs ve testler guncellenmelidir.
- Mobil bildirim eklemek icin `NotificationManager` soyutlamasi genisletilmelidir.
- Settings UI su an `.env` degerlerini okur; runtime kalici ayar icin yeni bir settings tablosu eklenmelidir.

## CV Pipeline

Input kaynaklari RTSP, webcam veya video dosyasidir. OpenCV frame okur; YOLOv8n-Pose kisi tespiti yapar; ByteTrack ID atar; ROI bazli hareket enerjisi ve optik akistaki kaotik hareket hesaplanir. Kisi ciftleri yakinlik, enerji, flow chaos, bbox overlap, hiz ve bbox boyut degisimiyle skorlanir. Temporal ortalama ve ardil frame onayi alarm seviyesini belirler.

