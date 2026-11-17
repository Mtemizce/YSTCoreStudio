# Seslendirme yönetimi: vurgu, ton, tepki

## 0. Motorlar (güncel)
`voice_studio.py` motorları `sistem/tts/` adaptörlerinden alır. Şu an tek motor: **EMA Lightning** (Apache-2.0, atıf gerekmez). Atıf gerektiren motorlar (Pocket TTS Turkish, CC-BY-4.0) atıfla kullanılır; yeni bir motor `sistem/tts/<ad>.py` adaptörü olarak eklenir (yönerge: `sistem/tts/__init__.py`).
- EMA ölçümü: perde canlılığı ≈ 3.8 st; kapanış perde düşüşü ≈ −3.9 st (ham). `--aday 5` cümle sonu düşüşünü iyileştirir (denemede aday başına seed farkıyla −4.9 st seçildi).
- `--aday N`: her parçadan N alım (farklı seed) üretip **cümle sonu tonu hedefe** (bildirim = düşen, soru = açık, '…' = serbest) en yakın olanı seçer; seçim rapor.json'da (`secim`).
- **"Ses havada kalıyor" teşhisi:** perde ve enerji ölçümlerinde teknik kesilme bulunmadı; asıl nedenler yapısaldı: kapanış bir ismin söylenmesiyle bitiyor (vaatle değil), müzikal çözülme yok, sonrası sessiz boşluk, marka adı yanlış okunuyor. Çözüm: vaat cümlesiyle kapat + düşen ton + son hecede sönüş (`son_fade_ms`) + oda kuyruğu (`kuyruk`) + riser→vuruş + çağrı.
- Özel ad telaffuzu: konuşma tanıma özel adı doğrulamaz (Whisper "Örnekoğlu"yu bilmiyor); doğrusunu kulak söyler. EMA'da telaffuz sözlüğü yok: yazımı değiştirerek (ör. okunduğu gibi) denenir ve kullanıcıya dinletilir.
- Duygu/ses tipi gerektiren işler EMA'nın dışına çıkar: şimdilik **görüntü, müzik, sessizlik ve cümle yapısı** duyguyu taşır. Atıfsız, duygu kontrollü bir Türkçe motor bulunursa adaptör olarak eklenir.

## 1. EMA Lightning ne yapabilir
`ema_lightning.EMA().say(text, path=, speed=0.25-4, seed=, sample_rate=48000|24000|16000|8000)`. **Tek ses, yalnızca Türkçe; duygu/vurgu/SSML/etiket yok.** Elimizdeki kontroller:
1. **Metin** (noktalama, cümle uzunluğu, yazım),
2. **`speed`** (parça başına),
3. **`seed`** (aynı metin farklı alım: tonlama/tempo hafif değişir; ✅ iki alım tutarlı süre verdi, tonu dinleyerek seç),
4. **Parça sınırları ve aralarındaki sessizlik** (bizim kontrolümüz),
5. **Ses işleme** (EQ, sıkıştırma, sibilans, oda, seviye).
Bunların hepsi `scripts/voice_studio.py` içinde. **Sesi dinleyemiyorsun**: ölçülebilenleri (süre, LUFS, tepe) ölç, tonu/vurguyu kullanıcıya dinleterek karara bağla; "doğal oldu" diye iddia etme.

## 2. İş akışı
1. **Senaryo**: cümle başına 8-14 kelime; bir cümle = bir fikir; ritim için kısa-uzun-kısa. Hedef tempo ≈ 140-155 kelime/dk (HyperFrames belgelerindeki anlatıcı hedefi 145-155; bizim açılış satırı ≈ 137). Sayı/kısaltma/yabancı özel isim **yazıyla**/okunduğu gibi yaz (`2013` → "iki bin on üç").
2. **Parçalama planı** (`plan.json`): her cümleyi nefes/vurgu birimlerine böl.
   - Vurgulanacak kelime/ifade: **ayrı parça**, `hiz 0.85-0.92`, önünde **0.2-0.35 sn** duraklama.
   - Virgülde `sonra 0.15-0.25`; nokta `0.4-0.6`; sahne/paragraf `0.7+`; marka adı sonrası `0.5-0.6`.
   - Coşkulu satır: `hiz 1.03-1.08`; ciddi/anma satırı: `0.9-0.95`. Aynı hızı bütün filmde kullanma (monoton = robot).
   - **Tepki/"reaksiyon"**: kısa cümle + sonrasında duraklama + görüntüde karşılığı (vuruş, geçiş). Ses duyguyu veremiyorsa **görüntü ve sessizlik** taşır.
3. **Alımlar**: `--takes 3`; farklı seed'ler. Her biri kısa özetle (süre, LUFS) raporlanır; kullanıcıya dinletip seçtir. Seçilen seed'i `plan.json` parçasına `"seed": N` olarak sabitle (tekrarlanabilir).
4. **İşleme zinciri** (ffmpeg, hepsi ölçülerek doğrulandı: ham ≈ −25 LUFS, çıktı ≈ −15.5 LUFS, tepe −1.5 dBTP):
   `highpass 70 Hz` (rumble) → `equalizer 190 Hz +1.5 dB` (sıcaklık) → `equalizer 3.2 kHz +2 dB` (netlik) → `deesser i=.4` (sibilans) → `acompressor 3:1, −21 dB eşik` (tutarlılık) → `aecho 19|41 ms, .18|.10` (çok hafif oda; yankı gibi duyuluyorsa kaldır) → `loudnorm I=−16 TP=−1.5`.
   Kulakla ayarla: ıslık/“s” sert → deesser↑; boğuk → 3.2 kHz +3; kuru/stüdyo → aecho kalsın; **yankı gibi → `aecho` sil**.
5. **Yerleştirme**: ses saattir. Her satırın başlangıcını **çapa kelimeye** göre belirle; ekrandaki vurgu (başlık, kalem, kart) o kelime anında iner. Kelime zamanları için `transcribe` (faster-whisper gerekir, kurulu değil) ya da parça sınırlarından hesapla (parça başlangıcı = Σ önceki süre + duraklamalar).
   Kurgu: `speak` MCP aracı WAV'ı `media/tts/`'ye yazar, `start` verilirse `audio` katmanı ekler (grup "Voice"); `voice_studio.py` çıktısını `import_file` ile alıp katmanı elle tanımla.
6. **Altyazı**: seslendirme metninden `text` katmanları; senaryo bilindiği için STT'ye gerek yok. Sahnelerde alt başlık/etiket varsa altyazıyı üst-orta (y≈130) ya da gizli bırak.

## 3. Daha fazla duygu gerekirse (⚪ belgelendi; kullanıcıya sor, kendiliğinden geçme; atıf gerektiren motorlarda atfı koru)
| Model | Türkçe | Duygu/vurgu kontrolü | Not |
|---|---|---|---|
| **Chatterbox Multilingual** (Resemble AI, `pip install chatterbox-tts`, MIT) | ✔ (23 dil, `tr`) | `exaggeration` (vars. 0.5; ifade için ≥0.7) + `cfg_weight` (vars. 0.5; ifade için ≈0.3 → daha yavaş/kasıtlı) | Yerel; referans ses gerekir (klonlama). Dilller arası referansta aksan geçebilir → `cfg_weight 0`. Yüksek exaggeration hızlandırır. |
| **ElevenLabs v3** | 70+ dil; Türkçe etiket geçerliliği doğrulanmadı | `[sad] [happily] [laughs]` gibi ses etiketleri, SSML yok | **Bulut/ücretli**: metin 3. tarafa gider → kullanıcı onayı şart; API anahtarı kullanıcıdan |
| **XTTS-v2 / F5-TTS / Fish-OpenAudio** | XTTS: Türkçe destekli (doğrulanmadı) | referans ses ile ton aktarımı | Lisanslar farklı (XTTS-v2'nin Coqui lisansının ticari kullanımı kısıtladığı biliniyor, bu araştırmada doğrulanmadı); kurmadan önce lisansı oku |
| **Gemini TTS / OpenAI gpt-4o-mini-tts** | doğrulanmadı | doğal dil "stil talimatı" (tonu tarif et) | Bulut; bu araştırmada doğrulanmadı |
Karar: Önce EMA + parçalı yönlendirme + işleme. Yeterli duygu yoksa Chatterbox-Multilingual'ı **yerelde** dene (gizlilik korunur), bulut yalnızca açık izinle.

## 4. Kalite kontrol listesi
- [ ] Her satır: LUFS −16±1 (işlenmiş), tepe ≤ −1.5 dBTP; sessizlik ve tıklama yok (parça birleşimlerinde patlama olmamalı).
- [ ] Tüm satırlar aynı ses karakteri (aynı zincir; seed farkı tonu değiştirebilir → kulakla).
- [ ] Marka adı iki yerde aynı okunuyor ("Örnekoğlu": ğ yumuşak; alım farkı varsa aynı alımı kullan).
- [ ] Müzik/SFX konuşmanın üstüne binmiyor (sound-and-music.md).
- [ ] Vurgulu kelime ↔ ekran vurgusu aynı anda.
- [ ] Kullanıcı dinleyip onayladı.
