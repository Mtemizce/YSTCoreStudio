# Üçüncü taraf kaynaklar: hangi depodan neler alındı

Bu belge, YSTCoreStudio'nun kullandığı açık kaynak depoları, onlardan alınan skill'leri ve diğer bileşenleri lisanslarıyla birlikte tek tek listeler. README'deki bağlantılar doğrudan ilgili bölüme gelir.

Skill dosyalarının çoğu depoya **konmaz**: `sistem/kurulum/dis_kaynaklar.json` her dosyanın kaynağını (depo + sabit commit ya da npm paketi) listeler, kurulum bunları kendi depolarından çeker. Bizim değiştirdiğimiz dosyalar (`YEREL KURAL` başlıkları, bulut/telemetri satırlarının sökülmesi) `sistem/yama/skills/` altındadır ve çekimden sonra üzerine uygulanır. Depoda bulunan parçalar (uyarlamalar, yazı tipleri, şablonlar) ilgili bölümde belirtilmiştir.

## İçindekiler

| Depo / kaynak | Skill sayısı | Lisans | Bölüm |
|---|---|---|---|
| remotion-dev/skills | 1 | Remotion Lisansı | [aç](#remotion-dev-skills) |
| HeyGen hyperframes (npm) | 2 | Apache-2.0 | [aç](#heygen-hyperframes) |
| echris6/motion-video-kit | 1 | MIT | [aç](#echris6-motion-video-kit) |
| artificialguybr/hyperframes-video-director | 1 | MIT | [aç](#artificialguybr-hyperframes-video-director) |
| anthropics/skills | 1 | Apache-2.0 | [aç](#anthropics-skills) |
| greensock/gsap-skills | 5 | MIT | [aç](#greensock-gsap-skills) |
| gl-transitions/gl-transitions | 1 | MIT | [aç](#gl-transitions) |
| avenoxai/avenoxskills | 3 (+1 ilham) | MIT | [aç](#avenoxai-avenoxskills) |
| leodavincs/kalem | 2 | MIT | [aç](#leodavincs-kalem) |
| leodavincs/kurgu | editör ve yerel rehber | MIT | [aç](#leodavincs-kurgu) |

Skill olmayan bileşenler: [kütüphaneler](#kutuphaneler) · [ses ve konuşma modelleri](#ses-modelleri) · [görüntü modelleri](#goruntu-modelleri) · [yerel görsel üretim](#yerel-gorsel-uretim) · [müzik ve ses efektleri](#muzik-ve-ses-efektleri) · [araçlar](#araclar) · [yazı tipleri](#yazi-tipleri) · [örnek videonun kaynakları](#ornek-video)

<a id="yerlesik-skiller"></a>
## Yerleşik skill’ler

Bu rehberler YSTCoreStudio’nun parçasıdır. Üçüncü taraf esin ve uyarlamalar ilgili kaynak bölümlerinde ayrıca belirtilir.

| Skill | Görevi |
|---|---|
| [`video-yonetmen`](video-yonetmen/SKILL.md) | Brief’ten sahne planına, üretimden teslim denetimine kadar video projesini yönetir. |
| [`kisilik-ve-ton`](kisilik-ve-ton/SKILL.md) | Anlatım üslubunu ve kişi kimliğini proje metinlerine taşır. |
| [`kurgu-video-studio`](kurgu-video-studio/SKILL.md) | Sahne motoru seçimi, geçişler, efektler ve render için teknik rehber. |
| [`sosyal-surumler`](sosyal-surumler/SKILL.md) | Platforma uygun çıktı düzenlerini tarif eder. [Esin kaynağı](#avenoxai-avenoxskills). |

---

## Skill kaynakları

<a id="remotion-dev-skills"></a>
### remotion-dev/skills
- Kaynak: https://github.com/remotion-dev/skills (resmî; v4.0.543 ile eşleşen sabit commit). Lisans: depoda ayrı lisans dosyası yoktur; Remotion'un kendi resmî skill'idir, Remotion Lisansı geçerlidir ([remotion.dev/license](https://www.remotion.dev/license): 3'ten fazla çalışanlı kâr amaçlı şirketler lisans almalıdır).
- **Alınan skill'ler (1):** `remotion-best-practices`: yalnızca ilgili alt klasörler (markup, captions, create, docs, interactivity, multimedia, render, license).
- Yerel değişiklik: `voiceover.md` (bulut seslendirme) kullanılmaz diye işaretlendi.

<a id="heygen-hyperframes"></a>
### HeyGen hyperframes (npm `hyperframes`)
- Kaynak: https://www.npmjs.com/package/hyperframes (sürüm 0.9.49). Lisans: Apache-2.0.
- **Alınan skill'ler (2):** `hyperframes`, `hyperframes-cli`.
- Yerel değişiklik: kullanım işareti (telemetri) ve geri bildirim satırları söküldü, `YEREL KURAL` başlığı eklendi; frame-preset slayt şablonları alınmadı. Paketin `media-use` skill'i kurulmadı (bulut oturum ve kredi tabanlı); yalnızca yerel parçaları `sistem/kit/referans/medya/` ve `sistem/kit/sfx/` altına alındı (ses efektleri Pixabay Content License).

<a id="echris6-motion-video-kit"></a>
### echris6/motion-video-kit
- Kaynak: https://github.com/echris6/motion-video-kit. Lisans: MIT.
- **Alınan skill'ler (1):** `business-motion-film`: kalite çıtası ve bağımsız eleştirmen döngüsü.
- Yerel değişiklik: `YEREL KURAL` başlığı (yapay zekâ görsel/video üretimi adımı uygulanmaz); betikler ffmpeg ve numpy kullanır, ağ çağrısı yoktur.

<a id="artificialguybr-hyperframes-video-director"></a>
### artificialguybr/hyperframes-video-director
- Kaynak: https://github.com/artificialguybr/hyperframes-video-director. Lisans: MIT.
- **Alınan skill'ler (1):** `hyperframes-video-director`: yalnızca belgeler (craft, directing, references, rubric); betikleri kurulmaz. Eleştirmen ajanının rubriği ve "dört karar" adımı buradan alındı.

<a id="anthropics-skills"></a>
### anthropics/skills
- Kaynak: https://github.com/anthropics/skills (resmî). Lisans: Apache-2.0.
- **Alınan skill'ler (1):** `frontend-design`: jenerik "yapay zekâ tasarımı" varsayılanlarından kaçınma ilkeleri; `video-yonetmen` bunu videoya uyarlar. Değişiklik yok.

<a id="greensock-gsap-skills"></a>
### greensock/gsap-skills
- Kaynak: https://github.com/greensock/gsap-skills (resmî). Lisans: MIT.
- **Alınan skill'ler (5):** `gsap-core`, `gsap-timeline`, `gsap-plugins`, `gsap-performance`, `gsap-utils`. HyperFrames'in animasyon motoru GSAP'tir. Değişiklik yok.

<a id="gl-transitions"></a>
### gl-transitions/gl-transitions
- Kaynak: https://github.com/gl-transitions/gl-transitions, npm `gl-transitions` ve `@gl-transitions/remotion`. Lisans: MIT (227 geçişin çoğu MIT, ikisi BSD).
- **Alınan skill'ler (1):** `gl-transitions`: skill npm paketiyle gelir; shader geçişleri Remotion `TransitionSeries` içinde `gecis('…')` ile kullanılır.

<a id="avenoxai-avenoxskills"></a>
### avenoxai/avenoxskills
- Kaynak: https://github.com/avenoxai/avenoxskills. Lisans: MIT. Depoda **uyarlama** olarak bulunur; `.claude/skills/LICENSES/avenoxskills-MIT.txt` lisans metnidir.
- Açık olarak paylaştığı rehberler ve şablonlar için Avenox ekibine teşekkür ederiz.

| Kaynak | Stüdyodaki karşılığı | Yararlanılan bölüm |
|---|---|---|
| <a id="avenox-roughcut"></a>`avenox-roughcut` | [`kaba-kurgu`](kaba-kurgu/SKILL.md) | Kaba kurgu yaklaşımı ve sessizlik kesimi. |
| <a id="avenox-graphics"></a>`avenox-graphics` | [`marka-kilidi`](marka-kilidi/SKILL.md) | `brand/frame.template.md` içindeki marka çerçevesi yaklaşımı. |
| <a id="avenox-thumbnail"></a>`avenox-thumbnail` | [`hook-ve-kapak`](hook-ve-kapak/SKILL.md) | `hook-patterns` içindeki açılış ve kapak fikirleri. |
| <a id="avenox-video"></a>`avenox-video` | [`sosyal-surumler`](sosyal-surumler/SKILL.md) | Platforma göre yönlendirme fikri. |

- Yerel değişiklik: Türkçeye ve bu stüdyonun yerel yığınına yeniden yazıldı (MLT/Kdenlive/auto-editor/mlx-whisper ve bulut görsel modeli çıkarıldı). `sistem/araclar/sessizlik_kes.py`, `remove-silence.py`'den uyarlanmıştır.

<a id="leodavincs-kalem"></a>
### leodavincs/kalem
- Kaynak: https://github.com/leodavincs/kalem. Lisans: MIT (© 2026 Leo); lisans metinleri `.claude/skills/referans/LICENSE-kalem.txt` ve `sistem/kit/kalem/LICENSE-kalem.txt`; yazı tipleri SIL OFL 1.1.
- **Alınan skill'ler (2):**
  - `kalem-cizim` (+ `sistem/kit/kalem/`): kalemle çizim ara sahnesi. `ortak/surucu.js` ve `ortak/yakala.py` uyarlandı, şablon sahne ve yazı tipleri alındı. DWG/SVG ve resim (ton taramalı) çizimi, zemin rengi, gerçeğe dönüşüm ve video girişi, çizim darbelerine bağlı kalem sesi bu depoya özgüdür.
  - `referans`: videoyu sahnelere bölüp her sahne için video istemi çıkarır (`/referans <video>`); betikler satır satır okundu ve taranıp (0 bulgu) uyarlandı.
- İlham: `kurgu-video-studio/references/sahne-motoru-secimi.md` kalem'in motor yaklaşımından esinlenir; kod ya da metin kopyalanmadı.
- Paper.js (npm, MIT) kalemle çizim sahnesi için kullanılır, bkz. [kütüphaneler](#kutuphaneler).

<a id="leodavincs-kurgu"></a>
### leodavincs/kurgu
- Kaynak: https://github.com/leodavincs/kurgu (sabit commit). Lisans: MIT. Zaman çizelgeli yerel video editörüdür; kurulumda çekilir, `sistem/yama/kurgu/` altındaki yamayla Türkçe konuşma entegrasyonu eklenir. [`kurgu` skill’i](../../sistem/yama/kurgu/skills/kurgu/SKILL.md) editörün proje ve zaman çizelgesi iş akışını tarif eder.

<a id="haidrrrry-claude-remotion-skill"></a>
### haidrrrry/claude-remotion-skill (esin)
- Kaynak: https://github.com/haidrrrry/claude-remotion-skill. Lisans: MIT. Skill kurulmadı; bu stüdyoyla uyumlu kurallar `kurgu-video-studio/references/remotion-craft-notlari.md` içine notlaştırıldı.

---

<a id="kutuphaneler"></a>
## Kütüphaneler ve çalışma zamanı
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| Remotion (`remotion`, `@remotion/*` 4.0.543) | remotion.dev | Remotion Lisansı | React ile video; **3'ten fazla çalışanlı kâr amaçlı şirketler lisans almalıdır** |
| HyperFrames (`hyperframes` 0.9.49) | HeyGen, npm | Apache-2.0 | HTML+GSAP video |
| GSAP 3.15 | greensock.com | GSAP Standart Lisansı (npm paketi) | HyperFrames animasyon motoru |
| React, React DOM 19.3 | react.dev | MIT | Remotion sahneleri |
| Paper.js 0.16.0 | paperjs.org | MIT | Kalemle çizim şablon sahnesi |
| gl-transitions 3.3.0, `@gl-transitions/remotion` 2.0.0 | gl-transitions | MIT | Shader geçişleri |
| PyTorch, NumPy, SciPy, Pillow, spandrel, safetensors, transformers, pypdf, pypdfium2, praat-parselmouth | ilgili projeler | BSD / MIT / Apache-2.0 (parselmouth: GPL-3 sarmalayıcı) | Yerel işleme |
| <a id="ffmpeg"></a>ffmpeg | ffmpeg.org | LGPL/GPL (kurulum yayın ikilisini indirir) | Kodlama ve ses/video işleme |

<a id="remotion-eklentileri"></a>
### Remotion sahne eklentileri

Doğrudan bağımlılıklar [package.json](../../package.json) dosyasında Remotion ile aynı sürüme sabitlenir. Paketler için [Remotion lisans koşulları](#remotion-dev-skills) geçerlidir.

| Paket | Kullanım |
|---|---|
| `@remotion/effects`, `@remotion/transitions` | Görsel efektler ve sahne geçişleri. |
| `@remotion/motion-blur`, `@remotion/noise` | Hareket bulanıklığı ve gürültü tabanlı animasyon. |
| `@remotion/shapes`, `@remotion/rough-notation` | Vektör şekiller ve çizgiyle görsel vurgu. |
| `@remotion/lottie` | Lottie animasyonlarının sahnelerde oynatılması. |
| `@remotion/cli` | Yerel önizleme ve render komutları. |

<a id="ses-modelleri"></a>
## Ses ve konuşma modelleri (yerel)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| <a id="ema-lightning"></a>EMA Lightning | huggingface.co/canberkkkkkk/ema-lightning, PyPI `ema-lightning` | Apache-2.0 | Varsayılan Türkçe seslendirme (`sistem/tts/ema.py`) |
| <a id="pocket-tts-turkish"></a>**Pocket TTS Turkish** (wite-tech; Kyutai Pocket TTS'ten türetilmiştir) | huggingface.co/wite-tech/pocket-tts-turkish | **CC-BY-4.0, atıf gerekir** | 6 hazır ses, duygu etiketi ve ses klonlama. Atıf: *Pocket TTS Turkish by wite-tech, CC-BY-4.0, derived from Kyutai's Pocket TTS (CC-BY-4.0) with Turkish fine-tuning and six-layer distillation.* Bu motorla üretilen her seslendirmenin yanına `ATIF.txt` yazılır |
| <a id="whisper-modelleri"></a>faster-whisper, CTranslate2 (SYSTRAN) | github.com/SYSTRAN/faster-whisper | MIT | Yerel konuşma → yazı (dikte, altyazı) |

Whisper ağırlıkları [`bilesen.py`](../../sistem/araclar/bilesen.py) üzerinden seçilir. Varsayılan model [small](https://huggingface.co/Systran/faster-whisper-small). Diğer seçenekler [tiny](https://huggingface.co/Systran/faster-whisper-tiny), [base](https://huggingface.co/Systran/faster-whisper-base), [medium](https://huggingface.co/Systran/faster-whisper-medium), [large-v3](https://huggingface.co/Systran/faster-whisper-large-v3) ve [Mobius Labs large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo). Ağırlıklarla ilgili koşullar için ilgili model kartına bak.

<a id="goruntu-modelleri"></a>
## Görüntü modelleri (yerel)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| <a id="real-esrgan"></a>Real-ESRGAN x4plus | github.com/xinntao/Real-ESRGAN; ağırlıklar Comfy-Org/Real-ESRGAN_repackaged | BSD-3-Clause | Fotoğraf iyileştirme (sha256'ya sabit) |
| <a id="depth-anything"></a>Depth Anything V2 Small | huggingface.co/depth-anything/Depth-Anything-V2-Small-hf | Apache-2.0 | Mekân gezisi derinlik haritası |

<a id="yerel-gorsel-uretim"></a>
## Yerel görsel üretim (isteğe bağlı; kullanıcı isterse kendi kaynaklarından indirilir, depoda dosya yok)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| <a id="z-image-modelleri"></a>Z-Image-Turbo (model) | github.com/Tongyi-MAI/Z-Image, huggingface.co/Tongyi-MAI/Z-Image-Turbo (Alibaba Tongyi-MAI) | Apache-2.0 | Metinden görsel üretim modeli |
| Z-Image-Turbo GGUF | huggingface.co/leejet/Z-Image-Turbo-GGUF (leejet) | Apache-2.0 | Q3_K ... Q6_K nicemlenmiş ağırlıklar; indirilen dosya Hugging Face'in yayımladığı SHA256 ile doğrulanır |
| <a id="stable-diffusion-cpp"></a>stable-diffusion.cpp | github.com/leejet/stable-diffusion.cpp (leejet) | MIT | Vulkan çalıştırıcısı (`sd-cli`); resmî sürümü kendi GitHub yayınından indirilir |
| <a id="z-image-qwen"></a>Qwen3-4B-Instruct-2507 (GGUF) | huggingface.co/Qwen/Qwen3-4B-Instruct-2507 (Alibaba Qwen); nicemlenmiş: huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF (Unsloth) | Apache-2.0 | Z-Image'ın metin kodlayıcısı |
| <a id="z-image-vae"></a>FLUX.1-schnell VAE (`ae.safetensors`) | huggingface.co/Comfy-Org/Z-Image-Turbo, `split_files/vae/ae.safetensors` (Black Forest Labs VAE, Comfy-Org dağıtımı) | Apache-2.0 | Z-Image'ın görüntü çözücüsü |
| <a id="z-image-pascal"></a>**Z-Image-Turbo Pascal 4GB** | github.com/alexturkey/z-image-turbo-pascal-4gb (alexturkey) | Apache-2.0 | **Esin kaynağı:** 4 GB'lık eski ekran kartlarında Z-Image-Turbo'yu çalıştırma yöntemi (`--offload-to-cpu --mmap --flash-attn`, 8 adım / cfg 1.0 / euler, VAE'yi karolu çalıştırma) ve model dosyalarını sabit adres + sha256 ile indiren **kilit dosyası** deseni. Betikler ve kod kopyalanmadı; fikirler `sistem/araclar/yerel_gorsel.py` içinde kendi kodumuzla yazıldı |

<a id="muzik-ve-ses-efektleri"></a>
## Müzik ve ses efektleri (`sistem/varlik/varliklar.db`; kurulum indirir, depoda dosya yok)
- **Wyzowl SFX Kit** (github.com/wyzowl/sfx-kit, sabit commit `92780e7`): 320 ses efekti, **CC0**, atıf gerekmez. `sistem/kit/sfx-wyzowl/`. Kalemle çizim sesi bu kitin `writing-pencil-draw` ve `writing-scribble` kayıtlarını kullanır.
- **Müzik, Internet Archive (Musopen, CC0 1.0):** "Musopen - The Complete Chopin Collection" (archive.org/details/musopen-chopin, Aaron Dunn) içinden 9 Noktürn ve 3 Prelüd; her kaydın adresi, sha256 değeri ve lisansı veritabanındadır.
- **Müzik (Wikimedia Commons; lisans API ile doğrulandı):** Satie Gymnopédie 1 ve 3 (Michael Laucke kaydı, kamu malı), Debussy Clair de Lune 1905 (kamu malı), Vivaldi Dört Mevsim'den Yaz-Presto / Bahar-Allegro / Sonbahar-Allegro / Kış-Allegro (The Modena Chamber Orchestra, Public Domain Mark). Her kaydın Commons dosya sayfası ve lisansı veritabanında kayıtlıdır.
- **Pixabay ses efektleri** (HeyGen hyperframes paketiyle gelen 20 kısa efekt): Pixabay Content License; tek başına yeniden dağıtılamaz, bu yüzden depoda değil kurulumda kopyalanır.

<a id="araclar"></a>
## Araçlar
- **LibreDWG** 0.14.9011 win64 (github.com/LibreDWG/libredwg, GPL-3.0-or-later): DWG → SVG. Resmî GitHub yayını, sha256'ya sabit; depoya konmaz, ayrı program olarak çalıştırılır (yalnızca Windows).
- **rclone** (MIT): Google Drive / OneDrive / Dropbox arşivi; resmî siteden indirilir, sağlama toplamı doğrulanır.

<a id="yazi-tipleri"></a>
## Yazı tipleri (SIL Open Font License 1.1; lisans metinleri yazı tiplerinin yanında)
Cormorant Garamond, Inter (`sistem/kit/fonts/`), EB Garamond, IM Fell (`sistem/kit/kalem/ortak/font/`).

<a id="ornek-video"></a>
## Örnek videonun kaynakları
Portre, bayrak, 1933 ses kaydı ve diğer örnek girdiler: [docs/ornek/ATIF.md](../../docs/ornek/ATIF.md).

---

## Kurulum yöntemi ve güvenlik taraması
Üçüncü taraf skill dosyaları kurulumda kendi depolarından, sabit commit ya da sürümle çekilir; kendiliğinden güncellenmez. `python sistem/kurulum/yama_cikar.py` bizim yama ile çekilen dosyalar arasındaki farkı çalışan bir kurulumdan yeniden üretir. Alınan her üçüncü taraf skill ve kaynak, eklenmeden önce `sistem/araclar/skill_tara.py` ile taranır (ağ çağrısı, gizli betik, bulut/hesap yönlendirmesi, görünmez karakter) ve içeriği okunur. Üçüncü taraf betik çalıştırılmaz: önce okunur, gerekirse kendi kodumuzla yeniden yazılır.


<a id="yerel-video-uretim"></a>
## Yerel video üretim (isteğe bağlı)

| Bileşen | Kaynak / sürüm | Lisans ve kullanım |
|---|---|---|
| wan22-pascal-4gb | https://github.com/alexturkey/wan22-pascal-4gb, v0.1.0 | MIT, Copyright (c) 2026 alexturkey. Kurulum/üretim tarifi, Pascal yamaları ve hazır motor. Yalnızca kullanıcı isteğiyle indirilir; betikler ve lisans dosyaları kaynak paketinde korunur. |
| stable-diffusion.cpp / ggml | leejet; yukarıdaki v0.1.0 paketinde sabit motor | MIT; motor paketindeki `licenses/` ve `THIRD_PARTY.md` dosyaları korunur. |
| <a id="wan-modeli"></a>Wan 2.2 TI2V-5B Q8_0 ve VAE | https://huggingface.co/QuantStack/Wan2.2-TI2V-5B-GGUF, revision `57437632ddd08bdcbd1508c866aa22e126ed51d2` | Apache-2.0; Wan-AI model kartındaki kullanım koşulları da incelenmelidir. |
| <a id="wan-umt5"></a>UMT5 XXL Q5_K_M | https://huggingface.co/city96/umt5-xxl-encoder-gguf, revision `b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7` | Apache-2.0; metin kodlayıcı. |
| CUDA 12.8 runtime | v0.1.0 ayrı `cudart-cuda12.8-win-x64.zip` paketi | NVIDIA CUDA Toolkit EULA; MIT değildir. Orijinal runtime DLL'leri değiştirilmez. |
| Visual C++ runtime | Microsoft resmi yükleyicisi | Microsoft koşulları; depoya dahil edilmez. |

Entegrasyon: `sistem/araclar/yerel_video.py`. Motor/runtime SHA256 değerleri upstream sürüm duyurusundan, üç modelin boyut ve SHA256 değerleri upstream `models.lock.json` dosyasından alınmıştır. Yarım indirmeler `.part` olarak tutulur. Üretilen videonun yanında kaynağı ve AI üretimini belirten `*-ATIF.txt` yazılır. Bu entegrasyon Alibaba/Wan-AI, NVIDIA veya alexturkey tarafından verilmiş bir uyumluluk onayı değildir.

<a id="orkestrator-baglantilari"></a>
## Panel orkestratör bağlantısı

- Claude Agent SDK Python: https://github.com/anthropics/claude-agent-sdk-python. SDK ve birlikte kullanılan Claude Code çalışma zamanının kendi lisans/hesap koşulları geçerlidir. Panel SDK üzerinden yanıt ve izin olaylarını işler; hesap kimlik bilgilerini kopyalamaz.
- Ollama, LM Studio ve llama.cpp paketleri veya model ağırlıkları depoya dahil edilmez. Panel onların yerel HTTP API'lerine bağlanır. Seçilen modelin ve sunucu yazılımının kendi lisansı geçerlidir.

- Codex CLI, Gemini CLI ve OpenCode deneysel çalışma ortamlarıdır. Kurulu istemci ile seçilen sağlayıcı ve modelin kendi koşulları geçerlidir.

<a id="medya-baglayicilari"></a>
## Medya API bağlayıcıları

| Bağlayıcı | Kullanım |
|---|---|
| Gemini | İsteğe bağlı görsel üretimi. |
| OpenAI görsel | İsteğe bağlı görsel üretimi. |
| ElevenLabs | İsteğe bağlı seslendirme. |
| fal / Seedance | [Seedance manifest örneği](../../sistem/baglayici/ornekler/seedance-fal.json) ile asenkron video üretimi. |
| Özel servis | [Asenkron HTTP](../../sistem/baglayici/ornekler/http-is-asenkron.json) ve [OpenAI uyumlu](../../sistem/baglayici/ornekler/openai-uyumlu.json) manifest örnekleri. |

API ve model kendi sağlayıcısında çalışır. Kota, ücret ve çıktı koşulları seçilen hizmete bağlıdır.

<a id="ace-step"></a>
## Yerel müzik üretimi

**ACE-Step 1.5 Turbo**, isteğe bağlı sözsüz müzik motorudur. [Kaynak ve MIT lisansı](https://github.com/ace-step/ACE-Step-1.5/tree/v0.1.8), [model kartı ve ağırlıklar](https://huggingface.co/ACE-Step/Ace-Step1.5). Kod ve ağırlıklar dağıtım ZIP’ine eklenmez; kullanıcı kurulum isteğiyle indirilir.

<a id="video-studio-kit"></a>
## Video Studio Kit

**Video Studio Kit (owlinthebarnai)**, stil ve araç kataloğu referansıdır. Uygulaması, örnek görüntüleri ve toplu skill arşivi paketlenmez. [Kaynak](https://github.com/owlinthebarnai/video-studio-kit) · [Upstream atıfları](https://github.com/owlinthebarnai/video-studio-kit/blob/main/THIRD_PARTY.md).
<a id="lottiefiles-motion-design"></a>
## LottieFiles Motion Design Skill

`motion-design` rehberi MIT lisanslıdır. Copyright (c) 2025 LottieFiles. Kurulum Video Studio Kit’in işaret ettiği `f9a8a041` commit’indeki Markdown rehberlerini lisansla birlikte doğrudan yazardan çeker. [Kaynak ve lisans](https://github.com/LottieFiles/motion-design-skill).

<a id="montaj-referanslari"></a>
## Montaj teknikleri referansları

| Bileşen | Kaynak / sürüm | Lisans ve kullanım |
|---|---|---|
| <a id="opus-video-skills"></a>Opus Video Skills | https://github.com/tuzhechen2005/opus-video-skills | MIT. Kinetik tipografi teknik referansı. Örnekler ve render şablonları paketlenmez. |
| <a id="brag"></a>Brag | https://github.com/latent-spaces/brag | MIT. Kod ve örnekler paketlenmez. Render ilk karesinin denetimi için teknik referans. |
| <a id="claude-motion-design"></a>Claude Motion Design | https://github.com/howseen-ai/claude-motion-design | MIT. Vuruş eşleme referansı. Kendi kodumuz ses dosyasından vuruş adaylarını çıkarır. |
| <a id="herk-edit-kit"></a>Herk Edit Kit | https://github.com/nateherkai/herk-edit-kit | MIT, Copyright (c) 2026 Nate Herk. Kelime zamanları ve kesim doğrulaması için teknik referans. Kit dosyaları paketlenmez. |
| <a id="saas-motion-kit"></a>SaaS Motion Kit | https://github.com/tugrawork-creator/saas-motion-kit | MIT (kod ve belgeler). Tanıtım sahnesi ve hareket düzenleri için referans. Örnekler, fontlar ve harici materyal paketlenmez. |
| <a id="snapcn"></a>Snapcn | https://github.com/shadcn-labs/snapcn | MIT. Modüler düzen ve hareket stili için referans. Registry kodu ve tasarım varlıkları paketlenmez. |
