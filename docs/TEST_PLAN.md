# Test Plan

Smoke test: backend `/` ve frontend dev server acilir.

Functional test: login, kamera CRUD, video upload, event listesi ve event detayi denenir.

Integration test: upload edilen video background job olusturur, processed video ve event kaydi uretir.

Regression test: scoring threshold ve motion analyzer unit testleri calisir.

Security test: JWT olmadan korumali endpointlerin reddedildigi, sifrelerin hashli saklandigi dogrulanir.

Performance test: 720p ve 1080p videolarda FPS, inference ms, toplam analiz suresi ve GPU/CPU kullanimi kaydedilir.

GUI test: desktop ve mobil genisliklerde metin tasmasi, tablo kaydirma, player ve progress bar kontrol edilir.

Accessibility test: klavye focus, kontrast ve form label kontrolleri yapilir.

