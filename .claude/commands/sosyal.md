---
description: Bitmiş bir projeden TikTok / Instagram Reels / YouTube Shorts sürümlerini üret (yeniden kompozisyon, altyazı, kapak, paylaşım metni).
argument-hint: "<proje adı> [platformlar: tiktok reels shorts] [süre/vurgu notu]"
---

Sosyal sürüm üretimi: **$ARGUMENTS**

1. `.claude/skills/sosyal-surumler/SKILL.md` ve `hook-ve-kapak` skill'lerini oku. Proje: `projeler/<ad>/` (ya da belirtilen yol); `ton_rehberi.md`, `senaryo.md`, `envanter.json`, ana film.
2. Platform belirtilmediyse üçü: tiktok, reels, shorts. Süre/ton farkı yoksa **tek dikey ana kurgu** + küçük farklar (kapak, metin, uzunluk, müzik lisansı).
3. `sosyal-kesici` ajanını (model: sonnet) çağır; **kırpma değil yeniden kompozisyon**. Sonra her çıktı için `elestirmen` (model: opus) ve `sistem/araclar/kalite_olc.py`.
4. Teslim: `projeler/<ad>/sosyal/<platform>/cikti/*.mp4`, `*_kapak.jpg`, `paylasim_<platform>.md`; ölçüm özeti; kullanıcının bakacağı yerler. Platform sayıları kaynaklarda çelişkilidir: yüklemeden önce app'te doğrulanmalı (skill'de yazılı).
