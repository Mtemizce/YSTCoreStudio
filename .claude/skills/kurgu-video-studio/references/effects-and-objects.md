# Efektler ve hareketli nesneler ("After Effects" tarzı)

Durum: ✅ kareyle doğrulanmış kullanım · ⚪ belgelendi: kullanmadan önce küçük bir still ile dene.

## A. `@remotion/effects` (Remotion ≥ 4.0.500; bizde 4.0.543)
Kurulum: `npm i --save-exact @remotion/effects@<remotion sürümü>`; `remotion.config.ts`: `Config.setChromiumOpenGlRenderer('angle')`.
Efektler `effects={[...]}` ile şu bileşenlere takılır: `<Img>`, `<Video>` (`@remotion/media`), `<Solid>`, `<CanvasImage>`, `<AnimatedImage>`, `<Gif>`,
`@remotion/shapes` şekilleri. **Düz HTML/`AbsoluteFill` efekt almaz** → `<HtmlInCanvas width height effects={[...]}>` ile sar.
Çoğu WebGL2; `cylinder`, `sphere`, `pageTurn` WebGPU (daha ağır). İçe aktarma: `@remotion/effects/<kebab-ad>`, fonksiyon camelCase. Tam parametre için `node_modules/@remotion/effects/dist/<ad>.d.ts`.

### After Effects karşılıkları
| After Effects | Remotion efekti | Durum / not |
|---|---|---|
| Lumetri / Color Correction | `colorCorrection({exposure,temperature,tint,shadows,highlights,blacks,whites,contrast,saturation,vibrance})`, `curves`, `levels`, `lut` (.cube), `whiteBalance`, `shadowsHighlights` | ✅ `colorCorrection` |
| Glow | `glow({radius,intensity,threshold,color})` | ✅ **koyu zemin şart**; parlak fotoğrafta yazı silikleşir |
| Chromatic aberration | `chromaticAberration({amount,angle})` | ✅ geçiş anlarında 0→6→0 ile kısa vurgu; sürekli açık bırakma |
| Vignette | `vignette({amount,radius,feather,mode})` | ✅ |
| Noise / film grain | `noise({amount,seed,premultiply})`, `whiteNoise`, `fractalNoise`, `speckle` | ✅ `seed={frame%24}` → her karede farklı gren |
| Light leak / Optical flare | `lightLeak({seed,hueShift,progress})`, `starburst`, `shine`, `lightTrail` | ✅ `lightLeak` (Solid üstünde; overlay) |
| Film burn | `filmBurn` (geçiş olarak da) | ✅ |
| Blur'lar | `blur`, `lensBlur`, `zoomBlur`, `regionBlur`, `linearProgressiveBlur`, `radialProgressiveBlur` | ⚪ |
| Distorsiyon | `wave`, `waves`, `noiseDisplacement`, `turbulentDisplace`, `fisheye`, `barrelDistortion`, `magnify`, `mirror`, `tile`, `skew`, `cornerPin` | ⚪ |
| Halftone / mosaic / pixelate | `halftone`, `halftoneLinearGradient`, `pixelate`, `pixelDissolve`, `dotGrid` | ⚪ |
| Renk stilleri | `duotone`, `tint`, `grayscale`, `hue`, `invert`, `thermalVision`, `linearGradientTint` | ⚪ |
| Gölge / dış hat | `dropShadow`, `longShadows`, `outline`, `bevelAlpha`, `emboss`, `roughenEdges`, `shrinkwrap` | ⚪ |
| Doku / desen | `paper`, `burlap`, `flannel`, `lines`, `scanlines`, `gridlines`, `contourLines`, `liquidContours`, `rings`, `checkerboard`, `pattern` | ⚪ |
| Kırılma / yırtılma | `shatter`, `tear`, `pageTurn`, `venetianBlinds`, `evolve`, `irisWipe`, `radialWipe` | ⚪ |
| Hava / parçacık | `snowFall`, `rainFall`, `lightning` | ⚪ |
| TV / glitch | `tvSignalOff`, `scanlines`, `whiteNoise` + `chromaticAberration` | ⚪ |
| 3B yüzey | `sphere`, `cylinder` (WebGPU) | ⚪ |

### Hazır parçalar (`assets/remotion-fx/FxKit.tsx`, ✅)
- `GradedPhoto`: derecelendirme preset'leri (`warm` `cool` `neutral` `punchy`) + vinyet + canlı gren + Ken Burns + isteğe bağlı CA.
- `GlowText`: `HtmlInCanvas` + `glow`.
- `LightLeakOverlay`: `TransitionSeries.Overlay` içinde.

### Sayısal başlangıç değerleri
- Sıcak mimari iç mekân: `exposure .1, temperature .12, contrast 1.08, saturation 1.05, highlights -.08, shadows .08`.
- Vinyet `amount .35-.5`; gren `amount .04-.06` (sıkıştırmada detay hissi verir, AI upscale "plastiğini" gizler).
- Önce/sonra vurgusu: "önce" karesine `gray .3-.35, bright .9`; "sonra" tam renk.
- CA `amount` tepe 4-6, 10-20 kare içinde 0→tepe→0. Glow `intensity .6-.9, threshold .35, radius 20-30` yalnızca koyu zeminde.
- Efekt zincir sırası: renk → bozulma/CA → vinyet → gren (gren en son, tüm görüntüye biner).

## B. Hareketli nesneler
### Yay (spring) + şekil (✅ `assets/remotion-fx/ObjectsLab.tsx`)
`spring({frame: f - delay, fps, config:{damping, stiffness, mass}})`. Damping: 1.0 sekmez · 0.7-0.85 premium · 0.4-0.6 eğlenceli · <0.3 çizgi film.
Konum/boyut/rotasyon sekebilir; **opaklık ve renk asla**. Giriş gecikmeleri: öğeler arası 6-10 kare (stagger).
Şekiller: `@remotion/shapes` (`Star` `Circle` `Rect` `Polygon` `Triangle` `Heart` `Pie` `Arrow` `Callout` `Spark` `Ellipse`).
### Hareket bulanıklığı (✅)
`@remotion/motion-blur` → `<HtmlInCanvasMotionBlur width height samples={8-12} shutterAngle={180-240}>` (Remotion ≥ 4.0.529; render için ek ayar yok; Studio önizleme Chrome 149+ bayrağı).
`shutterAngle` 0 = kapalı, 360 güçlü. Maliyet ≈ `samples`× kare süresi. Yalnızca **hızlı** hareket eden 2B öğelere; yavaş Ken Burns'e gerekmez.
HyperFrames'te kök elemana `data-motion-blur="on"` (`-shutter="360"` güçlü; `-events="on"`). Hızlı hareket 0.3-0.6 sn; blur tepe değeri metin ölçeğinde 6-12 px, tam kare 15-20 px, yalnızca hareket yönünde.
### Vurgu kalemi (✅)
`@remotion/rough-notation`: `<Highlight>` `<Circle>` `<Underline>` `<StrikeThrough>` `<Box>` `<Bracket>`; `progress` `useCurrentFrame()` ile 0→1 sürülür (20-25 kare). Anahtar kelimeyi **seslendirmedeki an**a denk getir.
### Çizim açma / vektör (⚪)
`@remotion/paths` `evolvePath(progress, path)` ya da `stroke-dasharray/offset` ile SVG çizgiyi "çizdir". Mimari plan SVG'si (LibreDWG → SVG, bkz. kurgu-pipeline) için ideal: duvarlar sırayla çizilir, sonra oda dolguları belirir.
### Lottie (⚪)
`@remotion/lottie` + `lottie-web`; After Effects → Bodymovin/LottieFiles ile JSON. Sınır: expression, 3B katman, bazı eklenti efektleri desteklenmez; metin outline'a çevrilmeli. Hazır/üretken: `diffusionstudio/lottie` skill'i (Claude Code ile Lottie üretir). Kompozisyonu AE kompozisyonuyla aynı boyut/süre yap.
### 3B (⚪)
`@remotion/three` (`ThreeCanvas`) + three.js; yavaş yörünge 3-5°/sn. Yalnızca nesne gerçekten 3B ise (ör. mimari model); aksi halde 2.5D paralaks (image-enhancement.md).
### Karakter/vektör animasyon (⚪)
Rive: `@remotion/rive`. Çizgi sanatı: SVG + `evolvePath`.

## C. Metin hareketi (kinetik tipografi)
Girişleri filmde çeşitlendir (aynı fade+slide-up'ı her yerde kullanma): kelime başı `blur(6px)→0` + opaklık 0.13 sn, 0.067 sn arayla (translate yok); harf harf (isim için) 0.1 sn arayla opaklık .3→1;
satırın tümü blur 8→0 px 0.13-0.2 sn; tek kelimenin "slot makinesi" gibi seçenekler arasında dönmesi (≈0.1 sn/dönüş). Çıkış: blur+fade 0.13-0.25 sn. İnen başlık hareketsiz.
Türkçe: büyük harfe çevirirken `toLocaleUpperCase('tr-TR')` (i→İ, ı→I); harf harf animasyonda `İ`/`Ğ` bileşik değil, tek karakter olarak bölünür (spread/`Array.from`).

## D. Önce/sonra ve karşılaştırma kalıpları (✅ bizim filmde)
Perde: `clip-path: inset(0 {W-x}px 0 0)` ile "sonra" katmanı soldan açılır, altın dikey çizgi `box-shadow` ile parlar, 0.7-2.5 sn `Easing.inOut(cubic)`.
Köşegen perde: `polygon(0 0, x+skew 0, x-skew H, 0 H)` + SVG çizgi. Etiket pill'leri perde geçtikçe değişir.
