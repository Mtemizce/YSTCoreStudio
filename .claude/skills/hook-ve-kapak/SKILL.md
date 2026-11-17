---
name: hook-ve-kapak
description: Kısa videolar ve uzun film için ilk 3 saniye (hook), kapak karesi, başlık ve açıklama/etiket metni yazma kalıpları. Merak açığı, somut vaat, kontrast, soru; kapak güvenli bant tasarımı; Türkçe ton ve doğruluk kuralları. Hook, kapak, başlık, "ilk saniye", "açılış cümlesi" istendiğinde kullan.
---

# Hook, kapak, başlık

Uyarlama: avenoxai/avenoxskills `avenox-thumbnail/references/hook-patterns.md` (MIT) fikirleri; **görsel üretim kısmı alınmadı** (bulut görsel modeli): kapak yerelde Remotion `still` ya da videodan kare ile yapılır.

İlke: İnsanlar **izlemek istedikleri** videoya basar. Kapak/hook **merak açığı açar**, video kapatır. Aynı sözcükleri kapakta ve başlıkta tekrarlama: farklı sözcükler aynı vaadi göstersin.

## Hook açıları (en keskin olanı seç; birbirinden gerçekten farklı 2-3 öner)
| Açı | His | Türkçe örnek (uydurma iddia YOK: yalnızca doğruysa kullan) |
|---|---|---|
| Önce/sonra (kontrast) | "vay, aynı yer mi?" | "Burası bir şantiyeydi." → teslim karesi |
| Çelişkili merak | "nasıl olur?" | "Ekranı kapatıp dinleyin: bu salon konuşuyor" |
| Somut sayı/süre | net getiri | yalnızca gerçek rakamla ("3 haftada teslim" ancak doğruysa) |
| Soru (cliffhanger) | cevabı merak | "Bu duvar neyi anlatıyor?" |
| Hata/risk | kaybetme korkusu | "Kütüphane tasarlarken en sık yapılan hata" (bilgi doğruysa) |
| Otorite/nasıl | içeriden kesinlik | "Bir cephe böyle kaplanır" |
| Nostalji/duygu | bağ | arşiv fotoğrafından hikâye |
| Mizah | yakınlık | **yalnızca profil izin veriyorsa**; mizah çevrilmez, bağlam ister |
Seçimi `kimlik/PROFIL.md` (mizah, enerji, hedef kitle) ve `ton_rehberi.md` yönetir.

## Kurallar
- İlk 3 saniyede **görsel hareket + net vaat**; ilk cümle ≤ 3 sn. Yalnızca "merhaba, ben X" ile başlama.
- Kapak/hook metni **2-4 kelime**; fikri bitirme (hafif eksik his iyi). Büyük, kalın, tek vurgu kelimesi (`kimlik/MARKA.md` vurgu rengi).
- Hook **videonun vaadini karşılamalı**; aldatıcı (clickbait) açılış güveni bozar. Gövde vaadi tutmuyorsa hook'u değil gövdeyi düzelt.
- Doğruluk: rakam/ödül/müşteri adı yalnızca kaynaklı; yoksa o açıyı seçme.
- Seri/parça numarasını kapağa koyma (devam bölümlerini öldürür); her parçaya kendi bağlamsal hook'u.

## Kapak karesi (yerel)
- Dikey (Reels/TikTok): ızgara/önizleme kırpmasını düşünerek **orta bantta** (güvenli kutuda) tasarla; yüz/özne merkezde; metin kısa.
- Kare: videonun en güçlü karesi (`ffmpeg -ss <t> -i video -frames:v 1`) ya da `remotion still` ile özel kapak. Ayrıca marka renkleri + `Pill`/`TitleBlock` bileşenleri.
- Yüksek çözünürlük (≥ 1080×1920), JPEG q≥90. Okunabilirlik: küçük (≈ 200 px) önizlemede de okunuyor mu bak.
- YouTube uzun film kapağı: 1280×720, 16:9; aynı kural: 2-4 kelime, tek vurgu.

## Başlık ve açıklama (platforma göre)
- Anahtar kelimeyi **başa** koy (arama + tarama ağırlığı). Shorts/YouTube: anahtar kelime ilk, net başlık; Reels/TikTok: kısa başlık + 3-5 etiket.
- Dil/ton = `kimlik/PROFIL.md` §4 (hitap, yasak kelimeler). Emoji/ünlem yığını yok (`kimlik/MARKA.md`).
- CTA kullanıcının kendi cümlesiyle (profil §7); iletişim bilgisi **yalnızca verilmişse**.
- Çıktı: `paylasim_<platform>.md` → Başlık · Açıklama · Etiketler · Kapak dosyası · Müzik/lisans notu.

## Metrik (küçük hesaplar)
Düşük gösterimde (≈1-3 bin) A/B gürültülüdür: tek en güçlü kapağı yayınla, ilk 24-48 saat tıklama oranına bak, gerekirse elle değiştir. Hook performansı: platform analitiğinde elde tutma eğrisinde ilk 3 sn düşüşü.
