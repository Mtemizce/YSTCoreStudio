# Ses tasarımı, müzik, miksaj

Ses, filmin hissinin yarısıdır; izleyici sessiz filmi hiçbir kareden önce fark eder. Kaynak: HyperFrames `sound.md`/`mixing` kuralları + bizim ölçümlerimiz.

## 1. Varsayılan
- 15 sn'yi aşan, bir şey anlatan film = **müzik yatağı + görünür eylemlere ses**; sessizlik yalnızca istenirse (ya da sessiz oynatılacaksa: o zaman tipografi/görüntü tek başına taşır).
- Anlatım varsa **ses saattir**: her çekimin başlangıcı çapa kelimeye; metin söyleyen kelimenin anında iner. Anlatım yoksa **müzik saattir**: ödül/işaret güçlü vuruşa gelir; kesme hareketi izler, davulu değil.
- Her film "ses" tek satırını bilir: yatağın havası/temposu, müziğin değiştiği tek an, hangi eylemlere ses, ya da sessizlik ve nedeni.

## 2. Müzik
- Önce kullanıcının kendi parçası. Yoksa telifsiz/lisanslı kaynak (Pixabay Music, Free Music Archive, YouTube Audio Library; **her parçanın lisansını kaydet**). Aranırken konu değil **his + tempo** yaz ("sakin minimal piyano, 70 bpm, yavaş yükselen").
- Parçanın **en güçlü barında** gir; bar çizgisinde kısa fade ile bitir. Final kartına geri-zamanla (ending end-card'a düşsün).
- **Kodla üretilmiş pad (`pad_yer_tutucu.wav`) yer tutucudur.** HyperFrames'in kendi uyarısı: kodla müzik yazmak için zaman harcama, iyi mi diye kimse dinleyemez. Dinleyip onaylatmadan "tamam" deme.
- Beat ızgarası: kare/vuruş = `fps × 60 / BPM`; her vuruşu **indeksten hesapla ve yuvarla**, yuvarlanmış vuruşu toplayarak ilerleme (128 BPM/30 fps'te 32 vuruşta 2 kare kayar). Kesmeyi vuruşa, yerleşim değişimini ölçüye (bar) koy. Araçlar: `npx hyperframes beats <müzik>` (vuruş JSON'u), `npx hyperframes audio <dosya> --json` (başlangıç/vuruş zamanları).

## 3. Efektler (SFX)
Az ve kesin; her sesin ekranda bir nedeni olur, fazlası "şablon" kokar.
| Ses | Yalnızca |
|---|---|
| tık | gerçek bir imleç tıklaması |
| whoosh | sahne kesmesi ya da büyük kartın hızlı hareketi |
| hafif tuş tıkı | metin harf/satır harf gelirken |
| pop | rozet/etiket/sayı inerken |
| riser → impact | ödül/imza anı, filmde **bir kez** |
Kurallar:
- Klibi, **zirvesi görüntüden 1 kare sonra** gelecek şekilde yerleştir (ışık sesten önce gelir; erken ses geç sesten çabuk bozar). Çoğu dosya başlangıcından sonra zirve yapar: `hyperframes audio <dosya> --json`.
- Her vuruş yatağın **3-6 dB üstünde**; enerjisi çoğunlukla 150 Hz altında olan yatak telefon hoparlöründe "yok" gibi çalar.
- Tekrarlanan sesin 2-3 alımı dönüşümlü kullanılır (her kesmede aynı whoosh en sık görülen şablon işareti). Güçlü müzik üstünde tuş/tık seslerini bırakabilirsin. **Sentez zil/ding yok.**
- Kaynak: HyperFrames `media-use/audio/assets/sfx/` (18 mp3: whoosh ×3, riser, impact-bass ×2, glitch ×3, pop, click, sparkle…) **Pixabay Content License** (ticari serbest, atıf zorunlu değil; `CREDITS.md`, `manifest.json` süre/öneri). Remotion `https://remotion.media/*.wav` örnekleri: ticari kullanım koşulunu kontrol etmeden teslim edilecek filmde kullanma.

## 4. Miksaj sayıları (Kurgu)
- Kurgu `global.loudness_lufs: -14` **tüm miksi** normalize eder → göreli seviyeler önemli. Hedef: son film **−14 ±1 LUFS, tepe ≤ −1 dBTP**.
- İşlenmiş konuşma ≈ −16 LUFS (voice_studio çıktısı). **Müzik konuşmanın en az 12 dB altında**; HyperFrames'in anlatım filmlerinde müzik ≈ −31 LUFS civarı. Kurgu'da müzik katmanı `volume_db −12…−18` (kaynağın seviyesine göre ölç), konuşma 0 dB.
- **Ducking:** müzik katmanına `envelope`: `[[t0,0],[t0+0.3,−6],[t1−0.2,−6],[t1+0.4,0]]` (konuşma `t0..t1` arası). Linear dB; hızlı giriş, yavaş çıkış.
- Fade: müzik `fade_in 2-3`, `fade_out 3`; film sonu `global.fade_out 1.5`.
- Ölçüm: `ffmpeg -i out.mp4 -af ebur128=peak=true -f null -` (`I:` ve `Peak:`). Bizim filmde taslak −14.6 LUFS, tepe −1.3 dBFS ölçüldü.
- Ses/konuşma maskelenmesi kontrolü: konuşma anlarında müzik spektrumunda 1-4 kHz'i hafifçe kıs (EQ −2…−3 dB) ya da ducking'i 8 dB yap.

## 5. Sessizlik ve nefes
Konuşma bitince 0.3-0.5 sn "oda tonu"/yatak ile kal; görüntü vuruşu (kesme, başlık) sessizliğe denk gelirse daha güçlü hissedilir. Filmin son satırından sonra ≥ 1-2 sn kal.
