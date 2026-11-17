---
name: kurgu-video-studio
description: "Kurgu + Remotion + HyperFrames ile profesyonel, çarpıcı video üretimi için usta rehberi. Geçişler (filmBurn, crossZoom, light leak, shader), After Effects tarzı efektler (glow, chromatic aberration, renk derecelendirme, gren, vinyet), hareketli nesneler ve hareket bulanıklığı, düşük çözünürlüklü/bulanık fotoğrafları yapay zekâyla iyileştirme (Real-ESRGAN), Türkçe seslendirmede vurgu-ton-duraklama yönetimi (EMA Lightning) ve ses tasarımı/miksaj. Şunlarda kullan: \"video yap/iyileştir\", \"geçiş\", \"efekt\", \"After Effects gibi\", \"fotoğraf bulanık/düşük çözünürlük\", \"seslendirme daha doğal/vurgulu olsun\", \"tanıtım filmi\", Kurgu notu bir sahnenin görünümünü/sesini değiştiriyorsa. Use for motion graphics, transitions, VFX, photo upscaling and voice-over direction in the Kurgu/Remotion/HyperFrames stack."
---

# Kurgu Video Studio

Kurgu zaman çizelgesini yönetir; **sahneleri kod üretir** (Remotion = React, HyperFrames = HTML+GSAP); ses `speak` (EMA Lightning) ile gelir.
Bu skill "ne zaman hangi tekniği, hangi sayılarla kullanırım" sorusunu çözer. Teknikler sayılarıyla yazılmıştır.
**Denemediğin hiçbir şeyi çalışıyor gibi sunma; sonucu kareye ve ölçüme bakarak doğrula.**

## 0. Önce oku (her işte)
1. Proje klasöründe `brief.md`, `CLAUDE.md`, `senaryo.json`, `changes.md`, `.kurgu/state.json` (Kurgu kuralı: önce insanın elle yaptığını gör).
2. Sahne kodu ve render yolu: `references/kurgu-pipeline.md`.
3. Bir şeyi değiştirmeden **önce** ve **sonra** kareye bak (`kurgu frame` / `kurgu strip`). "Derlendi" ≠ "güzel görünüyor".

## 1. Karar tablosu: istek → teknik → dosya
| İstek / sorun | Teknik | Oku |
|---|---|---|
| Sahneler arası geçiş | Nedenli geçiş (3-5 çeşit), süre 0.5-0.8 sn; Remotion `TransitionSeries`, HF shader blokları | `references/transitions.md` |
| **Shader geçişi / "özel efekt" geçişi** (ışık, yanma, lens, film, whip, glitch): 227 hazır geçiş, doğrulandı | `gecis('FilmDissolve')` (`sistem/kit/src/GlGecis.ts`) + `.claude/skills/gl-transitions` | `references/gl-gecisler.md` |
| "After Effects gibi" görünüm: parıltı, ışık sızıntısı, renk, gren, bozulma | `@remotion/effects` (60+ efekt), `FxKit.tsx` | `references/effects-and-objects.md` |
| Hareketli nesne, şekil, vurgu, çizgi/ok, logo animasyonu | spring + `@remotion/shapes` + hareket bulanıklığı, Lottie, rough-notation | `references/effects-and-objects.md` |
| Fotoğraf bulanık / düşük çözünürlük / JPEG artefaktı / "yumuşak" | Real-ESRGAN (`scripts/enhance_image.py`) + gren + 2.5D hareket | `references/image-enhancement.md` |
| Ses düz/robotik, vurgu yok, tempo hatalı | Parçalı yönlendirme (`scripts/voice_studio.py`), ses işleme zinciri | `references/voice-direction.md` |
| Müzik, SFX, miksaj, ses seviyesi | Ses tasarımı kuralları, LUFS hedefleri | `references/sound-and-music.md` |
| **Hangi müzik / hangi ses efekti** (320 CC0 efekt + 12 atıfsız müzik; ekrandaki ana göre arama ve senkron yerleştirme) | `sistem/araclar/sfx_bul.py`, `sistem/varlik/varlik.py` | `references/ses-kutuphanesi.md` |
| **Video tek bir araçla çizildiği için "hep aynı" duruyor**; sahnenin içindekine göre araç seçmek istiyorum | Sahneye böl, her sahneye uygun ana araç (HyperFrames/Remotion; ilham: kalem) | `references/sahne-motoru-secimi.md` |
| **Beğendiğim videodan sahne sahne istem/prompt çıkar**, referans video | `/referans <video>` (referans skill'i; videoyu üretmez) | `.claude/skills/referans/SKILL.md` |
| "Daha profesyonel/çarpıcı olsun" (belirsiz) | Bölüm 3'ün kalite kapısı + bölüm 2 kuralları | bu dosya |

## 2. Hareket dilinin kuralları (HyperFrames'in resmî filmlerinden ölçülmüş + Remotion en iyi uygulamaları)
- **Hızlı hareket 0.3-0.6 sn**, kendi ease'inde hareket bulanıklığı taşır. **Varış yavaş, çıkış temiz:** iniş uzun kuyruklu ease-out (`expo.out`, `power4.out`), çıkış girişten **%40-50 kısa**. Aynı `power2.out` her şeyde = "şablon" kokusu.
- **Ease rolü:** varış = `out-expo/quart`; kamera/renk dalgası = `inOut`; zoom-through/çıkış = `in-cubic`. Yaylar (spring) damping oranıyla adlanır: 1.0 sekmez, **0.7-0.85 premium**, 0.4-0.6 eğlenceli, <0.3 çizgi film. Konum/boyut sekebilir; opaklık ve renk **asla**.
- **Üst üste bindir:** sonraki öğe öncekinin %30-50'sinde başlar (tamamen sıralı = robot, hepsi birden = ucuz). Stagger: harf 1 kare, kelime 60-120 ms, liste öğesi 40-80 ms.
- **İnen başlık ölü durur.** Hareket bir sonraki öğeye/kameraya/arka plana geçer; başlığı sürekli süzdürme/nefes aldırma ("üretilmiş" görünümün 1 numaralı işareti). Aynı filmde girişleri çeşitlendir: kelime-kelime blur→net, harf-harf, tüm satır blur-in.
- **Tutma süresi:** okunacak satır ≈ 0.5 sn + kelime başı 0.3 sn; filmin son satırı ≥ 2 sn. Hazırlık: ödülden (payoff) önce 0.3-0.75 sn bekle.
- **Ritim kontrastı:** ortalama çekim 1.8-3 sn, içinde hareketle. Foto bazlı filmde bile: yavaş Ken Burns + arada tek hızlı kesme.
- **Başlık boyutu:** kare yüksekliğinin %4-9'u, en çok 2 satır; tek kelime vurgu rengiyle (anlam taşıyan).
- **Sürekli hareket çıkışı (işe yarayan):** gerçek içerik hareketi (foto Ken Burns, çalışan arayüz), arka planın yavaş (3-5°/sn) dönüşü. İşe yaramayan: nefes/yüzme/nabız döngüleri, iniş sonrası süzülen başlık, UI'da zıplama, tıklama halkaları.

## 3. Kalite kapısı ("üreten ≠ yargılayan")
Bitirdim demeden önce **render çıktısına** (planına değil) bak:
1. `kurgu strip <proje> <t0> <t1> --n 8` ile her geçişte tek kontak sayfası; geçiş ortasında kare bozuk/boş mu?
2. Metin okunabilirliği: açık fotoğraf üstünde beyaz yazı/glow yok mu? (scrim ekle). Güvenli alan: kenardan ≥ %4 (çerçeve çizgisi hariç).
3. Ses: `ffmpeg -i out.mp4 -af ebur128=peak=true -f null -` → **LUFS -14±1, tepe ≤ -1 dBTP**; konuşma müziğin ≥ 12 dB üstünde (bkz. sound-and-music).
4. Kimlik tutarlılığı: renk/font `theme.ts` dışına çıkmamış; filmde en çok 3-5 geçiş türü; sert kesme geçişlerin ≤ 1/3'ü.
5. Dürüstlük: metinlerde doğrulanmamış iddia (yıl, adet, ödül, telefon) yok; AI ile iyileştirilen/üretilen görüntü gerçek müşteri sonucu gibi sunulmuyor; okunur yazı/logo yapay zekâyla "uydurulmuş" harf içermiyor.
6. İçerik izni: kişi/çocuk yüzleri için yayın izni açık karar olarak `brief.md`'de duruyor.
Belirsiz isteklerde ("daha çarpıcı") en küçük net okumayı uygula, kullandığın sayıları cevapta yaz.

## 4. Sınırlar (bilerek)
- Kurgu'nun **headless uyanma** modu yalnızca `kurgu notes|frame|strip|rerender|detect|probe` ve `mcp__kurgu__*` araçlarına izin verir. `python`/`npm`/`ffmpeg` çalıştıran betikler (`enhance_image.py`, `voice_studio.py`, paket kurulumu) **interaktif oturumda** ya da kullanıcı izniyle çalışır. Bunları uyanma modunda deneme; notu `notes_ask` ile kullanıcıya bırak.
- EMA Lightning tek ses, yalnızca Türkçe, kontrol = `speed` + `seed`. Duygu/etiket (`[sevinçle]`) YOK; bu yüzden `voice-direction.md`'deki metin-mühendisliği + parçalama + işleme yolu kullanılır.
- Yapay zekâ upscale **yazıyı/logoyu/yüzü** uydurabilir; kritik kimlik öğelerinde orijinali koru ya da vektörle yeniden çiz.
- Remotion lisansı: küçük ekipler için ücretsiz, ticari/büyük ekipte lisans gerekebilir (`remotion-license` skill'i). HyperFrames Apache-2.0; telemetri kapalı tutulur.
- Gerçek müzik: kodla üretilmiş pad yalnızca yer tutucudur (HyperFrames'in kendi notu: kod ile müzik üretip iyi mi diye kimse dinleyemez). Lisanslı/telifsiz parça tercih edilir.

## 4b. Stüdyo katmanı (proje kapsamlı)
`<stüdyo klasörü>\` içinde bu skill'in üstüne bir üretim katmanı var: `/video`, `/sosyal`, `/profil` komutları; `video-yonetmen`, `kisilik-ve-ton`, `marka-kilidi`, `kaba-kurgu`, `sosyal-surumler`, `hook-ve-kapak` skill'leri; 6 alt ajan (içinde bağımsız `elestirmen`); `kimlik/PROFIL.md`/`kimlik/MARKA.md`; `sistem/kit/` ve `sistem/araclar/`. Yeni bir video ya da platform sürümü isteniyorsa **önce `CLAUDE.md`**. Bu skill yalnızca teknik zanaat içindir (geçiş/efekt/foto/ses sayıları).
Yeni dersler: dikey sürüm = yeniden kompozisyon (bulanık zemine kırpma slop); sentetik ses altyazısı senaryodan; ASR geri-okuma TTS netlik testidir (özel adlar bozulur → kulakla doğrula).

## 5. Hızlı başlangıç komutları
```
# fotoğrafları iyileştir (GPU, klasördeki tümü)
python .claude/skills/kurgu-video-studio/scripts/enhance_image.py <proje>/media/foto_orijinal -o <proje>/media/foto --scale 2
# seslendirmeyi yönlendirerek üret (3 alım, işleme zinciri dahil)
python .claude/skills/kurgu-video-studio/scripts/voice_studio.py plan.json -o ses_cikti --takes 3
# Remotion efektleri / geçişleri: assets/remotion-fx/ -> projenin src/fx/ klasörüne kopyala, FxLab'ı Root.tsx'e kaydet
# HyperFrames shader geçişleri
npx hyperframes catalog --tag transition        # liste; yüklemek için: npx hyperframes add <blok-adı>
```
