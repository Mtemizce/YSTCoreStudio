---
description: "Onaylanan taslağı final kalitede render et, eleştirmenden geçir ve seçili platformların sürümlerini üret (panelde Onaylıyorum sonrası)."
argument-hint: "projeler/<ad>"
---

Final aşaması. Proje: $ARGUMENTS

Sen orkestratörsün (`.claude/skills/video-yonetmen/orkestrasyon.md`). Bu komut **durumsuzdur**: bilgi dosyalardadır, sohbet geçmişine güvenme.

1. **Ön koşul:** `python sistem/araclar/durum.py goster <ad>` → aşama `onaylandi` olmalı ve `projeler/<ad>/onay.json` olmalı. Değilse dur, kullanıcıya "önce panelde Onaylıyorum de" de. Girdiler: `projeler/<ad>/uretim.json` (seçilen platformlar, seslendirme, marka, görsel üretimi), `calisma_gunlugu.md`, `brief.md`, `kimlik/*`.
2. Aşamayı `final-render` yap: `python sistem/araclar/durum.py ayarla <ad> final-render`.
3. **Bekleyen Kurgu notları:** `kurgu notes list projeler/<ad>/ana --open` (ve diğer biçimler): açık not varsa uygula (`orkestrasyon.md` ve Kurgu kuralları: not → düzelt → kareye bak → `notes done`), sonra devam et. Kullanıcının elle yaptığı değişiklikleri (changes.md) **geri alma**.
4. **Ana film (16:9) final render:** tam kalite (`kurgu-render projeler/<ad>/ana`, taslak değil). Ölçüm: `sistem/araclar/kalite_olc.py` (−14 ±1 LUFS, tepe ≤ −1 dBTP, 1920×1080, 30 fps), siyah/donmuş kare, ses sonu sönüşü. Hata varsa ilgili ajana geri ver (en çok 2 döngü).
5. **Bağımsız eleştirmen** (`elestirmen`, açık `model`/`effort`: `sistem/ayar/ayar.py ajan elestirmen <ad>`): final render + brief + marka. SHIP değilse maddeleri düzelt.
6. **Platform sürümleri** (`uretim.json` → `platformlar`): her dikey platform (shorts, reels, story, tiktok) için ana filmden **yeniden kompoze edilmiş** dikey sürüm. Dikey malzemeler (görseller, kadrajlar, dikey üretilmiş görseller `*_dikey.png`) planlama aşamasında zaten hazırlanmıştır: yatay kırpma/bulanık zemin YOK (`sosyal-surumler` skill'i). `sosyal-kesici` ajanıyla paralel çalıştır, her çıktıyı `kalite_olc.py --platform` ile ölç, kapak + `paylasim_<platform>.md` yaz. Aşama: `platform-surumleri`.
7. **Teslim:** tüm bitmiş videoları `projeler/<ad>/cikti/` altına kopyala (`ana.mp4`, `youtube-shorts.mp4`, `instagram-reels.mp4`, `instagram-story.mp4`, `tiktok.mp4`), `durum.py ayarla <ad> teslim`. Kullanıcıya: dosya yolları, ölçümler, eleştirmen kararı, **izleyip/dinleyip karar vereceği yerler**, bulut çağrı sayısı ve maliyet notu (`bulut_gunlugu.md`).
8. Kullanıcı geri bildirimini tarihli kurallar olarak `kimlik/ogrenilenler.md`'ye eklemeyi teklif et (onaylarsa yaz).

Her ajan devrini `calisma_gunlugu.md`'ye işle. Bulut (ücretli) hiçbir şeyi izin/ayar yoksa kullanma.
