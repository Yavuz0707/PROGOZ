# Scoring Debug

Debug acmak icin:

```powershell
cd backend
copy .env.example .env
notepad .env
```

`DEBUG_SCORING=true` yapip backend'i yeniden baslatin. Log dosyasi:

```text
backend/logs/scoring_debug.log
```

Her pair icin frame index, kisi ID'leri, proximity, mutual energy, mutual chaos, overlap, relative speed, direction/size, pose contact, restraint, contact persistence, group contact, raw score, final score, label, reason code ve penalty bilgileri yazilir.
