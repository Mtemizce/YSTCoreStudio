# Geçişler

## İlke: "nedenli geçiş"
Bir filmde **3-5 geçiş türü**; her biri ekranda bir nedenden doğar. Sert kesme sahne *içi* vuruşlara (punch-in) aittir;
sahne seamlarının en çok **1/3'ü sert kesme** olsun. **Farklı dünyalar birbirine crossfade olmaz** (mekân değişimini bir nesneyle/hareketle taşı).
Kaynak: HyperFrames'in resmî film ölçümleri + Remotion `transitions` kuralı.

| Ne anlatıyorsun | Geçiş | Süre (30 fps) | Neden |
|---|---|---|---|
| Önce → sonra (şantiye → teslim) | `wipe` / `clockWipe` / bizim "altın perde" | 1.0-2.5 sn (hareketin kendisi) | Perde ilerlemesi karşılaştırmanın kendisi |
| Aynı mekânda zaman geçişi | `filmBurn`, `dissolve`, ışık sızıntısı | 20-30 kare | Sıcak yanma "bir anı/an geçti" der |
| Mekân/konu değişimi (salon → cephe) | `crossZoom`, `zoomBlur`, whip (yatay blur 0.13-0.3 sn) | 15-24 kare | Kamera hareketi taşır, cut gizlenir |
| Duygusal/sakin an | `fade` (kısa) ya da `dreamyZoom` | 15-20 kare | Yumuşak, dikkat çekmez |
| Dramatik açılış/kapanış | `pushCut` (flash'lı sert kesme), `iris` | 6-15 kare | Vurgu |
| Kesme noktasını gizleme | Light leak **bindirmesi** (tepe noktasında kareyi örter) | 30-60 kare | Sahne uzunluğunu kısaltmaz (overlay) |
| Nesneden dünyaya | Bir kart/pill büyüyerek kareyi doldurur (ease-in-out 0.65 sn), çevresi ~15 px blur ile solar | 0.65 sn | HF "object becomes the world" |
| Renk dalgası | Nesne sabit, zemin ~0.4 sn `power2.inOut` ile renk değiştirir | 0.4 sn | HF "colour flood" |
| Ritmik vurgu | "Dip cut": giden kare 3 kare boyunca ~%40 kararır, sonra sert kesme | 3 kare | Kesme "bilerek" okunur |
| Sahne içi blur-swap | çıkış: opaklık→0 + ~8 px blur (0.13-0.2 sn); giriş: blur→0 (0.13 sn) | 0.13-0.2 sn | Zemin hiç kesilmez |

Kural-of-thumb: geçişte kesme **hareketin en hızlı karesinde** yapılır; iki yandaki hareket yönü/hızı eşleşir (match cut).
"Slayt gibi hissediyor" geri bildirimi → bir sonraki sahneye ekrandaki bir nesne üzerinden gir, hareketi yarıda kes.

## Remotion `@remotion/transitions` (doğrulandı: filmBurn, crossZoom, blurSlide + lightLeak overlay)
```bash
npm install --save-exact @remotion/transitions@<remotion sürümü> @remotion/effects@<aynı>
```
Presentation'lar (import yolu `@remotion/transitions/<kebab-ad>`): `fade` `slide` `wipe` `flip` `clockWipe` `cube` `iris` `none`
`blurSlide` `bookFlip` `crossZoom` `crosswarp` `dissolve` `dreamyZoom` `filmBurn` `linearBlur` `pushCut` `ripple` `swap` `zoomBlur` `zoomInOut`.
Timing: `linearTiming({durationInFrames})` ya da `springTiming`.

```tsx
<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={90}><SceneA /></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={filmBurn()} timing={linearTiming({durationInFrames: 24})} />
  <TransitionSeries.Sequence durationInFrames={90}><SceneB /></TransitionSeries.Sequence>
  <TransitionSeries.Overlay durationInFrames={30}><LightLeakOverlay seed={3} hueShift={20} /></TransitionSeries.Overlay>
  <TransitionSeries.Sequence durationInFrames={90}><SceneC /></TransitionSeries.Sequence>
</TransitionSeries>
```
- **Transition zaman çizelgesini kısaltır** (iki sahne aynı anda oynar): toplam = Σ sahne − Σ geçiş. **Overlay kısaltmaz.**
  Kompozisyon süresini (`Root.tsx`, `source.frames`) buna göre hesapla; FxLab: 90·4+60−(24+24+20) = 352.
- WebGL efekt/geçişler için `remotion.config.ts`: `Config.setChromiumOpenGlRenderer('angle')`.
- Doğrulanmış çalışan örnek: `assets/remotion-fx/FxLab.tsx` (+ `LightLeakOverlay` `FxKit.tsx` içinde). Light leak `progress` 0→1:
  ilk yarıda açılır, ikinci yarıda çekilir; **kesmeyi tepe noktasına (ortaya) denk getir.**
- Özel presentation: `TransitionPresentationComponentProps` (`presentationDirection: 'entering'|'exiting'`, `presentationProgress` 0→1).

## Kurgu katmanında (kodsuz) geçiş
Kurgu video katmanlarında `fade_in` = opaklık geçişi. **Çapraz çözülme:** sonraki sahne üstte (listede önde), `fade_in 0.5`, öncekiyle 0.5 sn **bindirilmiş**; giden sahneye `fade_out` verme (aksi halde siyaha dalar). Film sonu: `global.fade_out`.
Kurgu `keys` ile `opacity/x/y/scale` animasyonu, `effects` (blur/zoom/grayscale…) var; shader geçişi YOK → shader gereken yer sahne kodunda (Remotion/HF) yapılır.

## HyperFrames geçişleri (katalog: `npx hyperframes catalog --tag transition`, kurulum `npx hyperframes add <ad>`)
Shader blokları: `glitch`, `light-leak`, `cinematic-zoom`, `whip-pan`, `cross-warp-morph`, `domain-warp-dissolve`, `flash-through-white`,
`chromatic-radial-split`, `ridged-burn`, `ripple-waves`, `sdf-iris`, `swirl-vortex`, `thermal-distortion`, `gravitational-lens`.
Bileşenler: `fade-through`, `cut-the-curve` (hız eşlemeli yönlü kesme), `grid-pixelate-wipe`, `halftone-dissolve`, `curtain-reveal`.
Showcase blokları (`transitions-3d`, `-blur`, `-cover`, `-dissolve`, `-distortion`, `-grid`, `-light`, `-push`, `-radial`, `-scale`…) bir kategoriyi görmek içindir.
Mekanizmalar: iris = `clip-path: circle()`; reveal = inner wrapper'da `clip-path`/mask; hız rampası = `data-playback-rate`/`rate` lane; hareket bulanıklığı = kök elemanda `data-motion-blur="on"`.
Kurallar: GSAP zaman çizelgeleri `paused:true`, `window.__timelines[<kompozisyon-id>]` kaydı; yalnızca deterministik mantık (Math.random/Date.now yok). Her düzenlemeden sonra `npm run check` / `hyperframes lint`.

## GLSL kaynakları
`gl-transitions` (≈1.9k★, GLSL fragment shader, `from`/`to` doku; npm `gl-transitions`; son aktiflik 2024 ortası, yavaş geliştirme) HyperFrames shader bloklarının ve Remotion `crosswarp/ripple/...` geçişlerinin akrabasıdır. Yeni bir shader geçiş gerekirse önce bu koleksiyonda ara.

## Ses eşliği
Her geçişe ses atma. `whoosh` yalnızca **sahne kesmesinde** ya da büyük kartın hızlı hareketinde; zirvesi görüntüden **1 kare sonra** (ışık sesten önce gelir); aynı whoosh'u her kesmede kullanma (2-3 alım dönüşümlü). Bkz. `sound-and-music.md`.

## Sık hatalar
- Çok benzer iki fotoğraf arasına ağır geçiş: fark anlamsız, sıçrama gibi görünür → bu durumda `fade` ya da kesme.
- Her geçiş farklı tür: film "şablon denemesi" gibi görünür → 3-5 tür.
- Geçişi sahnenin son/ilk karesine koyup başlığı kesmek: başlık geçişin dışında kalacak şekilde yerleştir (iniş sonrası ≥ 0.5 sn tut).
- Geçiş süresi > sahne süresinin %40'ı: sahne okunamaz.
