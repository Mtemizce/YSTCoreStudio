# remotion-fx (test edildi: Remotion 4.0.543, Windows, RTX 3050)

Üç dosya, Remotion projesinde `src/fx/` altına kopyalanır:
- `FxKit.tsx`    GradedPhoto (renk derecelendirme + vinyet + canlı gren + Ken Burns + isteğe bağlı chromatic aberration), GlowText, LightLeakOverlay
- `FxLab.tsx`    TransitionSeries örneği: filmBurn, crossZoom, blurSlide geçişleri + lightLeak bindirmesi (kompozisyon süresi 352 kare)
- `ObjectsLab.tsx`  spring ile uçan şekiller + HtmlInCanvasMotionBlur + rough-notation vurgu kalemi

Ön koşullar (hepsi `remotion` ile AYNI sürüm):
  npm install --save-exact @remotion/effects@X @remotion/transitions@X @remotion/motion-blur@X @remotion/rough-notation@X @remotion/shapes@X
`remotion.config.ts` içine:  Config.setChromiumOpenGlRenderer('angle');
`FxKit`/`FxLab` projedeki `../theme` ve `../parts` (useFonts, renkler) dosyalarına dayanır; yoksa renk/font satırlarını değiştir.
Kompozisyonları Root.tsx'e kaydet, `remotion still src/index.ts FxLab out.png --frame=78` ile bak.

Bilinen: GlowText parlak fotoğraf üstünde okunaksız kalır, koyu zemin/scrim gerektirir.
