// Shader geçişleri (gl-transitions, MIT): 227 geçiş; herhangi iki sahne (foto, video, yazı) arasında <TransitionSeries> ile.
// Render: --gl=angle (sablon remotion.config.ts zaten ayarlı). Katalog + etiketler: .claude/skills/gl-transitions/references/catalog.md
// Marka sertliği: "aynı geçişi her yerde kullanma" → bir videoda en çok 2-3 farklı geçiş, çoğunlukla sakin gruptan.
import {glTransition} from '@gl-transitions/remotion';

export {glTransition};

/** Elle seçilmiş öneriler (hepsi katalogda doğrulandı). `kacin`: şablon/AI görünümü verir, MARKA ile çelişir. */
export const GL_ONERI = {
  sakin: ['Fade', 'FilmDissolve', 'CrossZoom', 'BokehDissolve', 'DefocusBlur', 'SimpleZoom', 'DirectionalEased', 'Overexposure', 'PhotoDevelop', 'FadeColor'],
  enerjik: ['WhipPan', 'LightStreaks', 'FilmBurn', 'FlashFade', 'LensFlare', 'WarpSpeed', 'CameraShake', 'ZoomInOut', 'SlotReels'],
  oncesiSonrasi: ['DirectionalWipe', 'LightWipe', 'BandWipe', 'ClockWipe', 'CircleOpen', 'KeyholeWipe', 'BurnThrough', 'ProjectorThrow', 'CurtainRise'],
  kacin: ['Cube', 'PuzzleCube', 'HeartWipe', 'FlowerWipe', 'Ascii', 'CodeRain', 'ComicPanels', 'GlitchFlicker', 'Vaporize'],
} as const;

export type GlOneriGrubu = Exclude<keyof typeof GL_ONERI, 'kacin'>;

/** Gruptan sıradaki öneriyi seçer (i her çağrıda artırılır: aynı geçiş tekrarlanmasın). */
export const glOner = (grup: GlOneriGrubu, i = 0): string => GL_ONERI[grup][i % GL_ONERI[grup].length];

/** İsimle geçiş (parametreler verilmeyenler katalog varsayılanında kalır). Kullanım:
 *  <TransitionSeries.Transition presentation={gecis('FilmDissolve')} timing={linearTiming({durationInFrames: 24})} /> */
export const gecis = (ad: string, params?: Record<string, unknown>) => glTransition({name: ad as any, params: params as any});
