---
name: marka-kilidi
description: kimlik/MARKA.md'deki kilitli görsel kimliği (renk, yazı tipi, doku, hareket karakteri, YASAK listesi, güvenli kenarlar) her grafik/sahne/kapak/altyazıda uygular ve "slop" (jenerik, yapay görünümlü) çıktıyı engeller. Sahne yazarken, eleştirirken ve kapak/altyazı tasarlarken kullan. Yeni marka tanımlarken `kimlik/MARKA.md` doldurma rehberi.
---

# Marka kilidi ve anti-slop

Kaynak: `kimlik/MARKA.md` (stüdyo kökü) ve varsa `projeler/<ad>/MARKA.md`. Uygulamadaki değerler `sistem/kit/src/theme.ts`'dedir; ikisi **aynı** kalmalı. Yaklaşım avenoxai/avenoxskills (MIT) "brand frame" fikrinden uyarlanmıştır: **bir kez kilitle; yasak listesi paletten çok iş yapar.**

## Sahne yazmadan önce
1. `kimlik/MARKA.md` oku; renk/yazı tipi dışına çıkma. Yeni renk gerekiyorsa **vurgu rengi değil**, mevcut tonun varyasyonu (örn. `goldSoft`).
2. "Hareket gerekiyor mu?" sor: gerekmiyorsa temiz durağan kare. Hareketi **kanıtla** (ne anlatıyor?).
3. Bir sahnenin tek **hero** öğesi olsun (ana özne ekranın %60-85'i, küçük kart büyük boş alanda yüzmesin).

## Slop işaretleri (her biri ret sebebi; eleştirmen bunlara bakar)
- Jenerik giriş: fade+slide-up'ı **her** öğede; aynı geçiş her yerde; nefes alan/yüzen/nabız atan döngüler
- İnen başlığın kaymaya devam etmesi; "üretilmiş" yavaş zoom başlık üstünde
- Neon/gradyan mesh/aurora/glassmorphism/3B parlak plastik; stok-fotoğraf insanlar
- Hiyerarşisiz ortalama; her şeyin aynı boyutta olması; ikinci vurgu rengi
- Emoji/ünlem/"inanılmaz-şok" metni; doğrulanmamış iddia
- Okunur yazıyı/logoyu AI ile yeniden çizme; filigran silme
- Aşırı efekt: glow+CA+gren+blur hepsi aynı karede (efekt dozu: her efektin bir nedeni olur)
- Altyazının içeriği örtmesi/taşması; açık fotoğraf üstünde beyaz yazı (scrim yok)
- Müzik/SFX'in "şablon" kokması (aynı whoosh her kesmede)

## Doğru yön (premium okunan)
Tipografi öncelikli, ağırlıklı, ölçülü hareket; uzun kuyruklu ease-out; kısa çıkış; **ölü duran başlık**; tek vurgu kelimesi; 3-5 geçiş türü; iyi derecelendirilmiş fotoğraf + hafif gren; ses kuralları (`kurgu-video-studio/references/sound-and-music.md`).

## Yeni marka kilitleme (kimlik/MARKA.md doldurma sırası)
1. Renk: zemin, metin (saf siyah/beyaz değil), **TEK** vurgu, (isteğe) uyarı. 2. Yazı tipleri: başlık + arayüz; Türkçe karakter ve `tr-TR` büyük harf testi. 3. Doku: vinyet/gren değerleri, sabit tohum. 4. Hareket karakteri 2 cümle. 5. **Yasak listesi** (en çok iş yapan kısım; kullanıcının "sevmediklerim"i PROFIL §8'den al). 6. Güvenli kenarlar (16:9, 9:16). 7. Altyazı stili. 8. Logo/maskot (kullanıcı verdiyse; **uydurma yok**).
Sonra `sistem/kit/src/theme.ts` ve gerekirse `sistem/kit/fonts/` güncelle; örnek bir still ile doğrula (`remotion still`).

## Doğrulama
`kimlik/MARKA.md` değişikliği sonrası ilk render'da eleştirmen (`.claude/agents/elestirmen.md`) marka maddelerini ayrıca puanlar.
