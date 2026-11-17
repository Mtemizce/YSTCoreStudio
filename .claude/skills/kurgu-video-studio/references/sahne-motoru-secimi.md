# Sahne bazlı araç seçimi: "her sahnenin kendi kalemi var"

> Fikir ve tablo ilhamı: github.com/leodavincs/kalem (MIT, Leo). Bu belge **özgün bir anlatımdır, kalem'den kod ya da metin kopyalanmadı**; tablo bu kurulumun gerçekte sahip olduğu araçlara göre yeniden kuruldu. Kalem'in kendi motorlarını (Paper.js, PixiJS, Manim, "levha") bu kurulum **içermez**; ayrı bir proje olarak o depodan alınır.

## Fikir

Yapay zekâya kodla video yaptırınca hepsi birbirine benzer, çünkü bütün sahneler tek bir araçla çizilir. Çözüm: videoyu sahnelere böl, her sahnenin **içinde ne olduğuna** bak, ona en uygun aracı seç. **Bir sahne = bir ana araç**; sahnede birden çok iş varsa ekranı kaplayan iş aracı belirler, yan işler onun içinde yardımcıyla çözülür.

## Sahnenin içinde ne var → hangi araç

| Sahnenin içinde... | Bu kurulumda | Not |
|---|---|---|
| Yazı, sayı, sayaç, bilgi kartı, haber kurgusu | **HyperFrames** (HTML + GSAP) | Kurulu. Yazı/bilgi animasyonunda en temiz yol. |
| Kendi kendine çizilen çizgi, eskiz, **kalemle çizilen plan/çizim** (DWG/SVG kaynaktan) | **`kalem-cizim` skill'i** (Paper.js + başsız Chrome; `sistem/araclar/kalem_cizim.py`, panelde *Ara sahne ekle*); basit yol çizgisi için HyperFrames path-tracing (`.claude/skills/hyperframes/references/path-tracing.md`) | Kurulu ve Windows'ta doğrulandı. Üç stil: parşömen, kara kalem, mavi teknik. |
| Karakter, yürüme, şeklin başka şekle dönüşmesi, logo animasyonu | **Remotion** (React, `@remotion/shapes`, spring, hareket bulanıklığı) | Kurulu. |
| Patlama, parlama, toz, binlerce küçük parça | Remotion + canvas; *PixiJS kurulu değil* | Parça sayısı çok artarsa kare başına süre uzar; önce az parçayla dene. |
| Gerçek 3D: dönen kamera, ışık, gölge | HyperFrames 3D tarifi (`.claude/skills/hyperframes/references/types/3d.md`) | Tarif var; `three` paketi bu kurulumda ayrıca yüklü değil, gerekirse eklenir. |
| Formül, grafik, şema, matematik | Remotion + SVG/`@remotion/shapes`; *Manim kurulu değil* | Manim (Python, LaTeX isteyebilir) ayrı kurulum ister. |
| Çalışan makine, defter levhası (kaldıraç, palanga, dişli) | Kalem'in "levha" motoru | **Kurulu değil**; ayrı projeden alınır. |
| Sahneden sahneye geçiş | `gecis('...')` shader geçişleri (227 hazır), `TransitionSeries` | Kurulu: `references/transitions.md`, `references/gl-gecisler.md`. |
| Kareye kilitli efekt sesi (tık, vuruş, hışırtı) | `sistem/araclar/sfx_bul.py` + `references/sound-and-music.md` | Kurulu. |

Bu tablo bir kişinin zevkiyle kuruldu (kalem'de 20 araç aynı sahneyle yarıştırılıp izlenerek puanlanmış). **Kendi denemelerinle kendi gözüne göre değiştir.**

## Akış (YSTCore ajanlarıyla)

1. **Sahnelere böl** (`senarist`): 4-8 sahne. Her sahne için gündelik dille tek cümle ve seçilen araç; kullanıcıya tablo olarak göster ("1. sahnenin içinde kendi kendine çizilen bir eskiz var → path-tracing"). Teknik sıkıştırma yok: "sayı koşuyor" değil, "sahnenin içinde artan bir sayı var".
2. **Ortak görsel dili bir kez yaz** (BRIEF): kâğıt/zemin dokusu, renkler, yazı tipleri. Her sahne aynısını kullanır; videonun tek elden çıkmış gibi durması buna bağlı.
3. **Sahneleri üret** (`sahne-yapimcisi`): sahneler birbirinden bağımsızdır, paralel üretilebilir (her sahneye ayrı ajan).
4. **Kontrol**: her sahnenin birkaç tam karesine bak: yazı taşıyor mu, boş kare var mı, renkler ortak dilde mi, ilk kare dolu mu.
5. **Birleştir**: geçişler + ses (Kurgu zaman çizelgesi).
6. **Denetim** (`elestirmen`, taze ajan): yalnız kontrol karelerini ve BRIEF'i ver, sor: "İzleyen kişi burada 'olmaz öyle şey' der mi?" Bulunanları düzelt, sonra kullanıcıya aç.

## Teknik sözleşme (yalnız bu hatta yeni olanlar; gerisi diğer belgelerde var)

- **Zaman kare numarasından gelir**: rastgelelik tohumlu, iki koşu aynı kareyi vermeli. Efekt sesini de görüntüdeki kareye kilitle (olayın karesinden üret), ses ile görüntü kaymaz.
- **İlk kare dolu**: siyahtan açılış yok. **Son ~15 kare sakin**: geçiş oraya biner.
- **Ani parlama/flaş yok**: kareler arası parlaklık sıçraması küçük kalır.
- **Dikey video** (Reels/Shorts, 1080×1920): üst ~250 px, alt ~420 px, sağ ~150 px'e anlam taşıyan öğe koyma (platform arayüzü örter).
- **Türkçe harfler** eksiksiz (Ç Ğ Ş İ Ö Ü); büyük harfe çevirirken `toLocaleUpperCase('tr')` (İ/ı doğru dönüşür).
- Tarayıcı sayfası üreten sahne kodunu yakalamadan önce `node --check` ile sına; sözdizimi hatasında sayfa hiç yüklenmez ve yakalama süre aşımına kadar bekler.

## Referans videodan başlamak

Beğenilen bir videonun sahne yapısını ve görsel dilini çıkarmak için `referans` skill'i (`/referans <video>`): videoyu sahnelere böler, her sahne için kamera/ışık/konu tarifi ve video istemi yazar. Çıktı `referanslar/<ad>/istemler.html`.
