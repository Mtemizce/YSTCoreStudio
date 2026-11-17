# Shader geçişleri (gl-transitions, MIT): 227 hazır geçiş, Remotion içinde

**Doğrulandı (gerçek render):** `Cube`, `CrossWarp`, `FilmBurn`, `LightStreaks` iki fotoğraf arasında 1920×1080 render aldı. Paketler: `gl-transitions@3.3.0`, `@gl-transitions/remotion@2.0.0` (kökteki `package.json`).
Skill (ayrıntı + tam katalog + parametreler): `.claude/skills/gl-transitions/` (`references/catalog.md`).

## Kullanım (Remotion)
```tsx
import {linearTiming, TransitionSeries} from '@remotion/transitions';
import {gecis} from '../../../../../sistem/kit/src';   // yeni_proje.py yolu kendisi ayarlar (proje: projeler/<ad>/<format>/remotion/src)

<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={90}><SahneA/></TransitionSeries.Sequence>
  <TransitionSeries.Transition presentation={gecis('FilmDissolve')} timing={linearTiming({durationInFrames: 24})}/>
  <TransitionSeries.Sequence durationInFrames={90}><SahneB/></TransitionSeries.Sequence>
</TransitionSeries>
```
- Sahneler **herhangi bir işaretleme** olabilir (foto, video, yazı, başka kompozisyon). Parametre: `gecis('LightStreaks', {intensity: 1.0})`; verilmeyen parametre katalog varsayılanında kalır. Ek doku isteyenler (`DisplacementMap`, `LumaWipe`) kaçınılır.
- Render'da WebGL gerekir: `remotion.config.ts` zaten `Config.setChromiumOpenGlRenderer('angle')` içerir (şablon). Studio önizlemesi Chrome 149+ ve bayrak ister; **kontrol render'dan alınan kareyle yapılır** (`remotion still … --frame=<geçişin ortası>`).
- Süre: geçiş süresi toplam süreden düşer (iki 60 kare sahne + 30 kare geçiş = 90 kare).

## Seçim (marka: sakin, premium, tipografi öncelikli; "aynı geçişi her yerde kullanma")
`sistem/kit/src/GlGecis.ts` → `GL_ONERI` (hepsi katalogda doğrulandı):
- **sakin:** `Fade`, `FilmDissolve`, `CrossZoom`, `BokehDissolve`, `DefocusBlur`, `SimpleZoom`, `DirectionalEased`, `Overexposure`, `PhotoDevelop`, `FadeColor`
- **enerjik/vurucu (kısa videolar, hook):** `WhipPan`, `LightStreaks`, `FilmBurn`, `FlashFade`, `LensFlare`, `WarpSpeed`, `CameraShake`, `ZoomInOut`, `SlotReels`
- **önce/sonra (şantiye → teslim):** `DirectionalWipe`, `LightWipe`, `BandWipe`, `ClockWipe`, `CircleOpen`, `KeyholeWipe`, `BurnThrough`, `ProjectorThrow`, `CurtainRise`
- **KAÇIN (şablon/AI görünümü verir):** `Cube`, `PuzzleCube`, `HeartWipe`, `FlowerWipe`, `Ascii`, `CodeRain`, `ComicPanels`, `GlitchFlicker`, `Vaporize`
Kural: bir videoda **en çok 2-3 farklı geçiş**, çoğu sakin gruptan; enerjik bir geçişi tek bir tepe anına sakla. Geçiş süresi: sakin 18-30 kare (30 fps), enerjik 10-18. Geçiş sesi için `ses-kutuphanesi.md`: `whoosh-*-soft`, `reverse-whoosh-*`.
`LightStreaks` ve `WhipPan` zirvede güçlü hareket bulanıklığı üretir: metin ve logo bu anlarda okunmaz, geçişin ortasına metin koyma.
Etiketle bul: katalogdaki `light`, `burn`, `lens`, `film`, `motion-blur`, `glow`, `flash` etiketleri "özel efekt" hissi verenlerdir.
