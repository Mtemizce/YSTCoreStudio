# Remotion zanaat notları (haidrrrry/claude-remotion-skill, MIT'ten SEÇEREK; çelişkiler işaretli)

Kaynak okundu (SKILL.md + design-rules.md), tarandı (temiz). Olduğu gibi KURULMADI: bazı kuralları bizim anti-slop kurallarımızla çelişiyor.

## Alınanlar (bizim kurallarla uyumlu)
- `interpolate()` **hep ease'li**, `extrapolateLeft/Right: 'clamp'`; girişlerde `spring()` tercih. Tek başına opaklık geçişi yok: giriş **2-3 özelliği** birlikte hareket ettirir (opaklık + translateY + scale).
- **Stagger**: liste/kelime/kart girişleri 3-6 kare arayla; hiçbir şey aynı anda girmez. **Çıkışlar girişten hızlı** (~10 kare, giriş ~20).
- Tüm süreler `useVideoConfig().fps`'ten türetilir; **tek tema nesnesi** (renk/ease/spring/font), bileşende satır içi hex yok (bizde `sistem/kit/src/theme.ts`).
- **Video varlıkları `<OffthreadVideo>`** (Remotion'da `<Video>` değil) kareye-kesin render için.
- **Mutlaka: render → kare çıkar → BAK → düzelt.** `remotion still … --frame N` (ffmpeg gerekmez, kesin kare). Sık hatalar: `em` boşluğu ebeveyn font boyutuna göre çözülür (büyük yazı çevresinde px kullan); metin kenara taşar; klemp yokluğundan giriş öncesi/çıkış sonrası görünen öğe; renk/kontrast; katman sırası (gren/vinyet en üstte, derecelendirme içeriğin üstünde).
- Sahne ritmi: **VURUŞ → tutma (15-20 hareketsiz kare) → kuruluş → VURUŞ**; ilk 15 karede bir şey hareket etsin; 90 karede bir yeni görsel öğe. Sabit hareket amatör, **kontrast pahalı** okunur.
- 9:16: kritik metin dikey ortada (güvenli alan; bizde konservatif kutu 120/192/288/672).
- Emoji ikon olarak kullanma (paleti bozar, görünmez olabilir); CSS/SVG ile çiz.
- SFX yoksa sessiz teslim etme: bizde `sistem/kit/sfx/` (Pixabay). Giriş vuruşları **görsel inişten 2-3 kare ÖNCE başlayan** kısa whoosh/click (erken = senkron hissi); geçişte riser → kesmede bas vuruş. (HyperFrames ölçümü: zirve görüntüden ~1 kare SONRA: ikisi de "senkron" hissi içindir; kulakla ayarla.)
- Hero yazı için indirmeye değil yerel font dosyası: `@font-face` + `staticFile`.
- Önizlemede şüpheli hareketi 0.25× yavaşlat: 1×'te görünmeyen ease kusurları görünür.
- Render: `--codec h264 --crf 16-17` (platform yeniden sıkıştırır, pay bırak); yoğun şeffaflık/blur için `--image-format png`.

## Bizde GEÇERSİZ sayılanlar (anti-slop ile çelişir; uygulama)
- "Her sahnede arka plan mesh/gradyan": **YOK** (kimlik/MARKA.md: gradyan mesh/aurora yasak). Zemin: koyu antrasit + fotoğraf + gren/vinyet.
- "**Boşta duran öğeler nefes alsın** (sin dalgası)": **YOK** (nefes/yüzme/nabız döngüleri üretilmiş görünümün 1 numaralı işareti; ölü duran başlık).
- "Hero rengine glow": yalnızca koyu zeminde, tek öğede, bilinçli (bizde glow kuralı).
- "Her fotoğrafa Ken Burns": düşük çözünürlükte zoom ≤ 1.08; kalite sınıfına göre düzen (bant/tam ekran).
- "Daima 5 katman yığını": bilinçli sade kare de premium okunur; efekt dozu nedenli.
- İçerik üretim önerileri (AI görsel promptları): yerel kural, uygulanmaz.
