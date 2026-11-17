---
description: "Kimliği tamamla: PROFIL.md'yi ölç, eksikleri sırayla röportajla doldur, gerçek örneklerden ses profili çıkar, çelişkileri göster."
argument-hint: "[istersen bir not: \"yeni bölümü ekledim\", \"markamı değiştirdim\"…]"
---

Kimlik tamamlama. Not: $ARGUMENTS

Amaç: sistemin kullanıcıyı **gerçekten** anlaması. Beyan tek başına yetmez; dört katmanı (beyan, kanıt, zevk, öğrenme) birlikte kur.

1. Ölç: `python sistem/araclar/kimlik_olc.py`. `kimlik/PROFIL.md`, `kimlik/MARKA.md` ve varsa `kimlik/ses_profili.md`, `zevk.md`, `ogrenilenler.md` dosyalarını oku; `.claude/skills/kisilik-ve-ton/SKILL.md` ilkelerini uygula. Kullanıcıya doluluğu ve **en çok etkileyen eksikleri** (KRİTİK listesi) söyle.
2. **Röportaj (form doldurtma değil):** KRİTİK eksikleri sırayla, **her turda en çok 3 soru**, kullanıcının cevabına göre derinleşen takip soruları ile sor. Soyut sıfat yerine somut iste: "bir örnek ver", "en son ne zaman söyledin", "bunu hangi cümleyle söylerdin". Özellikle: §4 gerçek örnek cümleler ve yasak kelimeler · §5 ana fikirler + kanıtı · §6 kim izliyor · §7 çağrı cümlesi · §11 izinler (çocuk, müşteri adı) · §13 duygular · §14 arşiv ve işler · §15 doğrulanmış gerçekler (her satır: iddia | kaynak | kullanılabilir mi) · §16 telaffuz sözlüğü (marka adı ve özel adlar nasıl okunur) ve onay tercihi · §17 anlatı soruları.
3. **Kanıt iste:** kullanıcıdan 3+ gerçek yazı örneği (caption, mesaj, e-posta) ve/veya 1-2 dakikalık doğal ses kaydı (telefon kaydı) isteyip `kimlik/ornekler/` içine koymasını söyle; sonra `python sistem/araclar/ses_profili.py` çalıştır ve çıkan ölçümü (ritim, hitap, dolgu sözcükler) **beyanıyla karşılaştırıp çelişkileri göster** ("resmi olduğunu söyledin, yazdıkların gündelik").
4. **Zevk testi:** panelde **Kimlik → Zevk testi** adımını öner (A/B cümle üslubu + müzik dinleme); sonuç `kimlik/zevk.md`.
5. Cevapları `kimlik/PROFIL.md`'ye **kullanıcının sözleriyle** yaz (sen yorumlama; uydurma yok); yazmadan önce kısa özeti göster ve onay al. Doğrulanmamış rakam/yıl/ödül yazma; §15'e kaynağıyla gir.
6. **Kişilik ve ton özeti** (≤ 12 satır): sentez, kopya değil; her karar yanında kaynağı (hangi katman). Çakışmalar: profil ↔ marka, beyan ↔ ölçüm, profil ↔ hedef platform.
7. Bitince `python sistem/araclar/kimlik_olc.py` ile yeni doluluğu göster. Profil dosyasını **kullanıcı onayı olmadan değiştirme**.
