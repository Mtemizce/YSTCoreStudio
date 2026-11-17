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
| leodavincs/kurgu | editör (skill değil) | MIT | [aç](#leodavincs-kurgu) |

Skill olmayan bileşenler: [kütüphaneler](#kutuphaneler) · [ses ve konuşma modelleri](#ses-modelleri) · [görüntü modelleri](#goruntu-modelleri) · [yerel görsel üretim](#yerel-gorsel-uretim) · [müzik ve ses efektleri](#muzik-ve-ses-efektleri) · [araçlar](#araclar) · [yazı tipleri](#yazi-tipleri) · [örnek videonun kaynakları](#ornek-video)

Bu stüdyonun kendi yazdığı skill'ler (üçüncü taraf değil): `video-yonetmen`, `kisilik-ve-ton`, `kurgu-video-studio`, `sosyal-surumler`.

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
- **Uyarlanan skill'ler (3):** `kaba-kurgu` (`avenox-roughcut`), `marka-kilidi` (`avenox-graphics`, `brand/frame.template.md`), `hook-ve-kapak` (`avenox-thumbnail`, `hook-patterns`). `sosyal-surumler` skill'i `avenox-video` yönlendirici fikrinden esinlenilmiştir (ilham).
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
- Kaynak: https://github.com/leodavincs/kurgu (sabit commit). Lisans: MIT. Zaman çizelgeli yerel video editörüdür (skill değil); kurulumda çekilir, `sistem/yama/kurgu/` altındaki yamayla Türkçe konuşma entegrasyonu eklenir.

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
| ffmpeg | ffmpeg.org | LGPL/GPL (kurulum yayın ikilisini indirir) | Kodlama ve ses/video işleme |

<a id="ses-modelleri"></a>
## Ses ve konuşma modelleri (yerel)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| EMA Lightning | huggingface.co/canberkkkkkk/ema-lightning, PyPI `ema-lightning` | Apache-2.0 | Varsayılan Türkçe seslendirme (`sistem/tts/ema.py`) |
| **Pocket TTS Turkish** (wite-tech; Kyutai Pocket TTS'ten türetilmiştir) | huggingface.co/wite-tech/pocket-tts-turkish | **CC-BY-4.0, atıf gerekir** | 6 hazır ses, duygu etiketi ve ses klonlama. Atıf: *Pocket TTS Turkish by wite-tech, CC-BY-4.0, derived from Kyutai's Pocket TTS (CC-BY-4.0) with Turkish fine-tuning and six-layer distillation.* Bu motorla üretilen her seslendirmenin yanına `ATIF.txt` yazılır |
| faster-whisper, CTranslate2 (SYSTRAN) | github.com/SYSTRAN/faster-whisper | MIT | Yerel konuşma → yazı (dikte, altyazı) |

<a id="goruntu-modelleri"></a>
## Görüntü modelleri (yerel)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| Real-ESRGAN x4plus | github.com/xinntao/Real-ESRGAN; ağırlıklar Comfy-Org/Real-ESRGAN_repackaged | BSD-3-Clause | Fotoğraf iyileştirme (sha256'ya sabit) |
| Depth Anything V2 Small | huggingface.co/depth-anything/Depth-Anything-V2-Small-hf | Apache-2.0 | Mekân gezisi derinlik haritası |

<a id="yerel-gorsel-uretim"></a>
## Yerel görsel üretim (isteğe bağlı; kullanıcı isterse kendi kaynaklarından indirilir, depoda dosya yok)
| Bileşen | Kaynak | Lisans | Kullanım |
|---|---|---|---|
| Z-Image-Turbo (model) | github.com/Tongyi-MAI/Z-Image, huggingface.co/Tongyi-MAI/Z-Image-Turbo (Alibaba Tongyi-MAI) | Apache-2.0 | Metinden görsel üretim modeli |
| Z-Image-Turbo GGUF | huggingface.co/leejet/Z-Image-Turbo-GGUF (leejet) | Apache-2.0 | Q3_K ... Q6_K nicemlenmiş ağırlıklar; indirilen dosya Hugging Face'in yayımladığı SHA256 ile doğrulanır |
| stable-diffusion.cpp | github.com/leejet/stable-diffusion.cpp (leejet) | MIT | Vulkan çalıştırıcısı (`sd-cli`); resmî sürümü kendi GitHub yayınından indirilir |
| Qwen3-4B-Instruct-2507 (GGUF) | huggingface.co/Qwen/Qwen3-4B-Instruct-2507 (Alibaba Qwen); nicemlenmiş: huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF (Unsloth) | Apache-2.0 | Z-Image'ın metin kodlayıcısı |
| FLUX.1-schnell VAE (`ae.safetensors`) | huggingface.co/black-forest-labs/FLUX.1-schnell (Black Forest Labs) | Apache-2.0 | Z-Image'ın görüntü çözücüsü |
| **Z-Image-Turbo Pascal 4GB** | github.com/alexturkey/z-image-turbo-pascal-4gb (alexturkey) | Apache-2.0 | **Esin kaynağı:** 4 GB'lık eski ekran kartlarında Z-Image-Turbo'yu çalıştırma yöntemi (`--offload-to-cpu --mmap --flash-attn`, 8 adım / cfg 1.0 / euler, VAE'yi karolu çalıştırma) ve model dosyalarını sabit adres + sha256 ile indiren **kilit dosyası** deseni. Betikler ve kod kopyalanmadı; fikirler `sistem/araclar/yerel_gorsel.py` içinde kendi kodumuzla yazıldı |

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
