# CV Algorithm

YOLOv8n-Pose varsayilan modeldir; kisi sinifi icin Ultralytics `track` API kullanilir. `tracker="bytetrack.yaml"` ile ByteTrack ID surekliligi saglanir.

Frame differencing her kisi bounding box ROI alaninda onceki gri frame ve mevcut gri frame `cv2.absdiff` ile hesaplanir. Farneback optical flow ROI uzerinde calisir; mean magnitude hareket miktari, standart sapma kaotik hareket gostergesi olarak kullanilir.

## Iki Katmanli Skor

Katman A kisi bazli aktiviteyi hesaplar:

- motion energy
- optical flow mean
- optical flow std / chaos
- speed
- bbox area variation
- center movement
- direction change

Bu katman tek basina kavga karari vermez. Tek kisi hareketi skor olarak sinirlanir ve alarm uretmez.

Katman B kisi ciftleri uzerinden etkilesim skorlar:

- proximity
- mutual energy
- mutual chaos
- overlap
- relative / closing speed
- direction or size variation
- interaction duration
- pose contact
- contact persistence
- restraint / immobilization
- pinned against frame edge
- group pressure

Asil alarm skoru Katman B'den gelir. Bir kisi cok hareketli ama etkilesimde oldugu ikinci kisi yoksa final skor dusuk kalir.

## Yakin Temasli Siddet Sinyalleri

False negative azaltmak icin hareket disi saldiri kanitlari eklendi:

- Persistent close contact: yakinlik veya overlap birkac frame surerse skor tabani yukselir.
- Pose contact: bir kisinin wrist/elbow keypoint'leri diger kisinin head/neck/shoulder/upper torso bolgesine yakin ise contact aggression cue uretilir.
- High overlap under contact: yuksek bbox overlap dusuk hareket olsa bile supheli kabul edilir.
- Restraint: bir kisi dusuk hareketliyken diger kisi yakin/temasli baski yapiyorsa immobilization sinyali uretilir.
- Pinned edge cue: kisi frame kenarina sikismis ve diger kisiyle yakin/overlap durumundaysa ek kanit uretilir.
- Group pressure: 3+ kisilik yogun cluster icinde bir kisi 2+ kisiyle temas/yakinlik altindaysa surrounded person skoru uretilir.

## Pair Gating

False positive azaltmak icin pair skoruna penalty uygulanir:

- Uzak ciftlerde skor ciddi dusurulur.
- Dusuk mutual energy varsa skor dusurulur.
- Sadece tek kisinin hareketli oldugu durum penalize edilir.
- Kisa sureli yan yana gecisler minimum interaction frame saglamadan alarm seviyesine kolay cikamaz.
- Sadece overlap/proximity olup enerji ve chaos yoksa skor dusurulur.
- Ancak pose contact, restraint, pinned veya group pressure gucluyse dusuk hareket penalty'leri yumusatilabilir.
- Yakin temas + yuksek overlap + hareket asimetrisi/restraint varsa skor KAVGA bandina hizlandirilir. Bu sayede bogaz sikma, tutma veya sabitleme gibi dusuk hareketli saldirilar NORMAL olarak kacmaz.

Tum bilesenler 0.0-1.0 araliginda normalize edilir. Final skor 0-100 araligina kalibre edilir.

## Agirliklar

- Mutual energy: 0.25
- Mutual chaos: 0.25
- Relative motion: 0.15
- Temporal persistence: 0.15
- Proximity: 0.10
- Bbox overlap: 0.05
- Pose contact: 0.05

Proximity ve overlap artik tek basina kavga kaniti degildir; sadece aday etkilesim sinyali olarak dusuk agirlikla kullanilir.

## False Positive Filtreleri

Balanced mode varsayilan moddur: NORMAL `<35`, SUPHELI `>=35`, OLASI_KAVGA `>=55`, KAVGA `>=75`. High sensitivity mode icin `DETECTION_MODE=high_sensitivity` kullanilir; bu modda esikler `30/45/65` olur.

KAVGA etiketi icin mandatory evidence kuralı uygulanir. Skor KAVGA esigini gecse bile su sartlar yoksa seviye KAVGA'ya cikamaz: `proximity > 0.55`, en az 4 frame persistence ve `mutual_chaos > 0.50`, `mutual_energy > 0.55`, `pose_contact > 0.60` veya `relative_motion > 0.55` kanitlarindan en az biri.

Kalabalik penalty: `person_count >= 5` ve mutual chaos dusukse skor `0.55` ile carpilir. Normal yakin durma filtresi, proximity/overlap yuksek ama mutual energy ve chaos dusukse skoru `0.35` ile carpar. Tek tarafli hareket filtresi, yalnizca bir kisi hareketliyse skoru `0.45` ile carpar; pose contact cok yuksekse bu penalty yumusatilir.

Overlay tarafinda `ONLY_HIGHLIGHT_INVOLVED_PERSONS=true` iken global alarm seviyesi KAVGA olsa bile sadece ilgili pair/group track id'leri kirmizi/turuncu cizilir; diger kisiler yesil kalir.

## Temporal Mantik

Adaptive baseline ilk framelerde normal hareket enerjisini ogrenir. Weighted temporal average son 15 frame skorunu yumsatir. Consecutive frame confirmation tek frame kaynakli yanlis alarmlari azaltir. Hysteresis alarm seviyeleri arasinda ziplama etkisini dusurur. Event cooldown ayni kisi ciftinden kisa surede tekrar tekrar event yazilmasini engeller.

Alarm seviyeleri balanced mode icin: NORMAL `<35`, SUPHELI `>=35 + 2 frame`, OLASI_KAVGA `>=55 + 3 frame`, KAVGA `>=75 + 5 frame`.

Yakın temas saldırıları için ek skor tabanları `.env` uzerinden ayarlanir: `HIGH_OVERLAP_FIGHT_FLOOR=62`, `CONTACT_FIGHT_FLOOR=66`, `GROUP_FIGHT_FLOOR=62`, `MIN_FIGHT_CONTACT_PERSISTENCE=0.42`.

## Debug ve Overlay

`.env` icinde `DEBUG_SCORING=true` yapildiginda pair skor bilesenleri `backend/logs/scoring_debug.log` dosyasina yazilir.

Overlay ayarlari `.env` uzerinden `OVERLAY_FONT_SCALE`, `OVERLAY_SMALL_FONT_SCALE`, `OVERLAY_BANNER_HEIGHT_RATIO`, `OVERLAY_PADDING` ve `OVERLAY_COMPACT_MODE` ile degistirilebilir.

## Evaluation

Sample klipleri toplu denemek icin:

```powershell
python scripts/evaluate_video.py
python scripts/evaluate_video.py test_videos\normal test_videos\fight
```

Onerilen manuel senaryolar: tek kisi yuruyus, iki kisi yan yana gecis, kalabalik normal yuruyus, yakin konusma/kisa temas, itisme, bogaz sikma/fiziksel kisitlama, grup halinde sikistirma, dusuk hareketli ama saldiri iceren yakin temas.

## Incident Grouping

Frame-level skorlar varsayilan olarak SQLite'a tek tek event olarak yazilmaz. Video ve kamera analizinde `IncidentTracker` ardisik skorlari tek bir kullanici olayi olarak gruplar. Bir incident baslamasi icin skor `INCIDENT_MIN_SCORE_TO_START=35` ustune cikar; kisa dususler `INCIDENT_END_GRACE_SECONDS=1.0` boyunca tolere edilir. Incident kapaninca yalnizca tek kayit `incidents` tablosuna yazilir.

Varsayilan onay kurallari: SUPHELI icin en az 5 processed frame veya 0.5 sn, OLASI_KAVGA icin 8 frame veya 0.8 sn, KAVGA icin 12 frame veya 1.2 sn. Incident icinde en yuksek skorlu frame tek `best_snapshot` olarak kaydedilir; timeline `score_timeline_json` alaninda tutulur.

Islenmis video uretimi artik opsiyoneldir. Varsayilan demo akisi yalnizca olaylari, snapshot'i ve skor timeline'ini cikarir; kullanici isterse Video Analiz ekranindan "Islenmis video uret" secebilir.
