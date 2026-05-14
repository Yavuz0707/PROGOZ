# Runbook

Uygulamayi baslatmak icin once backend, sonra frontend calistirilir. Panel `http://localhost:5173` adresindedir.

Kamera eklemek icin Kameralar sayfasinda `webcam` veya `rtsp` secilir. RTSP icin URL girilir, webcam icin kaynak otomatik `0` kabul edilir.

Video yuklemek icin Video Analiz sayfasinda dosya secilip analiz baslatilir. Progress bar job durumunu gosterir. Analiz sonunda video player ve olay ozeti guncellenir.

Olaylari incelemek icin Olaylar sayfasinda seviye filtresi kullanilir; detay sayfasinda snapshot, skor, kisi ID'leri ve kriter JSON'u gorulur.

Sik hatalar:

- CUDA pasif: NVIDIA driver ve CUDA destekli PyTorch kurulumunu kontrol edin.
- FFmpeg yok: PATH'e FFmpeg ekleyin.
- RTSP acilmiyor: URL, ag erisimi ve kamera kimlik bilgilerini kontrol edin.
- YOLO ilk calismada bekliyor: model dosyasi otomatik indiriliyor olabilir.

Skor debug icin `backend/.env` dosyasinda `DEBUG_SCORING=true` yapip backend'i yeniden baslatin. Pair bazli proximity, mutual energy, chaos, overlap, relative speed, raw/final score ve label bilgileri `backend/logs/scoring_debug.log` dosyasina yazilir.
