# Düşük çözünürlüklü / bulanık görsellerin iyileştirilmesi

Arşiv fotoğrafları (2010-2013 telefon/kompakt kamera; 482-980 px, JPEG artefaktlı) 1080p filmde 2-3× büyütülür. Boru hattı:

```
analiz → (pozlama/renk düzelt) → AI upscale 4× → hedefe indir (2×) → ince gren → hareket (Ken Burns / 2.5D) → kompozisyon hileleri
```

## 1. Hızlı karar
| Girdi | Yap |
|---|---|
| Uzun kenar ≥ 1700 px, keskin | Dokunma (yalnızca derecelendirme) |
| 700-1700 px, genel foto | `enhance_image.py --scale 2` (Real-ESRGAN x4plus) |
| < 700 px | `--scale 2`, ek olarak çerçeveli/blurlu-zemin kompozisyonu, zoom ≤ 1.08 |
| Okunur yazı/logo/tabela var | AI'a güvenme: harf **uydurabilir**; orijinali küçük kullan ya da vektörle yeniden çiz |
| Yakın plan yüz | Önce/sonra karşılaştır (x4plus yüzü yumuşatır/bozabilir); gerekirse yüz modeli (GFPGAN/CodeFormer, ⚪ belgelendi) |
| Çok karanlık/düz renk bozuk | Önce pozlama/renk (`colorCorrection`, HF `media-treatment --analyze`), sonra upscale |

## 2. Çalıştırma (örnek ölçüm: 6 GB ekran kartında 4 foto ~42 sn, ilk model indirmesi dahil)
```
python .claude/skills/kurgu-video-studio/scripts/enhance_image.py girdi_klasoru -o cikti_klasoru --scale 2 --grain 0.012
```
- Model: `RealESRGAN_x4plus.safetensors` (67 MB, Comfy-Org/Real-ESRGAN_repackaged, xinntao/Real-ESRGAN BSD-3-Clause), `%LOCALAPPDATA%\Kurgu\models\` altına **bir kez** iner; boyut doğrulanır.
- **Güvenlik:** yalnızca `.safetensors` yüklenir (pickle yok). İnternetten gelen `.pth` dosyaları rastgele kod çalıştırabilir; kullanma. Model sunucusu sabit HTTPS adresi.
- Karolama (256 px, 16 px bindirme) 6 GB VRAM'e sığar; bellek hatasında `--tile 128`. CPU'da çalışır ama yavaş.
- `--scale 2` = 4× büyütüp 2×'e indirir (artefakt küçülür, keskinlik kalır). `--scale 4` ham 4×. `--max-side 3840` üst sınır.
- `--grain 0.012` sabit tohumlu ince gren: AI'ın "plastik" düz alanlarını gizler. Videoda ayrıca `noise({seed: frame%24})` ile canlı gren eklenir (iki katman toplamı çok olmasın: video grenini .04'te tut).
- Sonuç (3 test foto, %100 kırpım): panel yazıları, çizgi film konturları, tavan armatür detayları belirgin netleşti; eski yöntem (Lanczos+unsharp) yumuşak/bulanık kalıyordu. **Not:** panel üstü yazılarda bazı harfler "makul ama uydurma" — kimlik/okunur metin için kullanma.
- Pipeline'a bağlama: orijinaller `media/foto_orijinal/` (asla ezme), iyileştirilmişler `media/foto/`; Remotion `staticFile('foto/ad.jpg')` aynı adı okur → dosya adı sabit, uzantı `.jpg` ise çıktıyı `.jpg` yaz (`-o ad.jpg` ile kalite 95).

## 3. Alternatifler (⚪ belgelendi)
- **realesrgan-ncnn-vulkan** (xinntao/Real-ESRGAN Releases, Windows taşınabilir .exe; Python/CUDA gerekmez, Vulkan'lı her GPU): `realesrgan-ncnn-vulkan.exe -i in.jpg -o out.png -n realesrgan-x4plus`; `-s 2|3|4`, `-t` karo, `-g` GPU. Sürüm 2022 (v0.2.5.0); indirilen .exe'yi çalıştırmak kullanıcı onayı ister.
- **spandrel** (MIT, `pip install spandrel`): ESRGAN/RealESRGAN, SwinIR/Swin2SR, HAT, DAT, SPAN, Real-CUGAN, yüz onarımı, gürültü giderme, düşük ışık modellerini tek arayüzle yükler. Bizim betik bunu kullanıyor; başka model eklemek için `MODELS` sözlüğüne (url, dosya, boyut) satırı ekle. Mimari lisansları ayrı: ticari olmayan mimariler `spandrel_extra_arches` paketinde.
- **OpenModelDB** (openmodeldb.info): fotoğraf/anime/JPEG-deblock için topluluk modelleri; **yalnızca safetensors** ya da güvenilir kaynak. JPEG'e özel model aranırsa orada "JPEG" etiketine bak (bu araştırmada doğrulanmadı).
- **chaiNNer**: aynı modellerle görsel arayüzlü işlem hattı (toplu/özel zincir gerekirse).

## 4. Hareketsiz fotoğrafa can verme
### Ken Burns (✅)
Scale 1.0→1.08-1.14 + 20-40 px kayma, `Easing.inOut(sin)`; **düşük çözünürlükte zoom ≤ 1.1** (büyüttükçe yumuşar). Çekim süresi 1.8-3 sn.
### 2.5D paralaks (⚪ belgelendi)
**DepthFlow** (BrokenSource, `pip install depthflow`, GLSL shader + derinlik haritası; Depth Anything V2 tabanlı; GPU hızlı): tek fotoğraftan kamera hareketli (dolly/orbit/zoom) video klip üretir; mimari iç mekânlarda çok etkili (derinlik katmanları ayrışır).
**Lisans:** DepthFlow **AGPL-3.0** (yazılım); ürettiği videoyu bağlamaz ama kodu dağıtırsan AGPL'e uy. **Depth Anything V2** ağırlıkları Apache-2.0 (Small ≈ 100 MB). Alternatif: kendi paralaksını `HtmlInCanvas`/three.js ile derinlik haritası displacement ile yap.
Kullanım: önce küçük bir klibi 3 sn üret, kenarlarda "esneme" (stretching) artefaktına bak; kenarlarda ek zoom ile kırp. Sonucu Kurgu'ya video katmanı olarak ya da Remotion `<Video>` içinde ver.

## 5. Kompozisyon hileleri (kalan yumuşaklığı gizler)
- **Blurlu-zemin + çerçeveli ön plan:** aynı fotoğraf `blur 24-28 px, brightness .5` ile zemin, ön planda `contain` kart (altın 2 px çerçeve, gölge). Dikey fotoğraflar için zorunlu (✅ Kütüphane sahnesi).
- **Küçük kartlar:** düşük çözünürlüklü fotoğrafı tam ekran yerine 300-420 px kart olarak ver (yüksek PPI hissi); ana fotoğrafı yüksek çözünürlüklü olandan seç.
- **Vinyet + scrim + renk derecelendirme + gren:** detay hissini artırır, kusurları gizler.
- **Dönüşüm (watermark):** filigranlı fotoğrafta filigran çatışabilir; markaya aitse bilerek bırak (örn. kendi marka filigranın), değilse kırp/yerleşimle gizle (**başkasının filigranını silme**).
- Hareket yönünü ışık/nesne akışıyla eşle (soldan sağa okuma).

## 6. Dürüstlük
AI ile iyileştirilmiş görüntü "olduğundan netmiş" izlenimi verebilir. Önce/sonra gibi kanıt niteliğindeki karelerde (şantiye ↔ teslim) **içeriği** değiştirme; yalnızca çözünürlük/gürültü iyileştir. Yüz/yazı yeniden üretimi gerçek müşteri/iş kanıtı gibi sunulmaz.
