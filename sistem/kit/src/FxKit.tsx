/**
 * FxKit: Remotion >= 4.0.500 için "After Effects tarzı" yapı taşları (test edildi: 4.0.543).
 * Gerekli paketler (hepsi remotion ile AYNI sürüm): @remotion/effects @remotion/transitions @remotion/motion-blur
 * Gerekli yapılandırma (remotion.config.ts): Config.setChromiumOpenGlRenderer('angle');   // WebGL efektleri için
 */
import React from 'react';
import {AbsoluteFill, HtmlInCanvas, Img, Solid, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {chromaticAberration} from '@remotion/effects/chromatic-aberration';
import {colorCorrection} from '@remotion/effects/color-correction';
import {glow} from '@remotion/effects/glow';
import {lightLeak} from '@remotion/effects/light-leak';
import {noise} from '@remotion/effects/noise';
import {vignette} from '@remotion/effects/vignette';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export type Grade = 'warm' | 'cool' | 'neutral' | 'punchy' | 'mono';
const GRADES: Record<Grade, Parameters<typeof colorCorrection>[0]> = {
  warm: {exposure: 0.1, temperature: 0.12, tint: 0.02, contrast: 1.08, saturation: 1.05, highlights: -0.08, shadows: 0.08},
  cool: {exposure: 0.05, temperature: -0.1, contrast: 1.06, saturation: 1.0, highlights: -0.05},
  neutral: {contrast: 1.04, saturation: 1.02},
  mono: {exposure: -0.05, contrast: 1.12, saturation: 0.12, highlights: -0.1},
  punchy: {exposure: 0.08, contrast: 1.18, saturation: 1.15, vibrance: 0.15, highlights: -0.12, shadows: 0.1},
};

/**
 * Renk derecelendirilmiş, vinyetli, ince grenli, Ken Burns hareketli fotoğraf.
 * `ca` > 0: chromatic aberration (kenarlarda RGB kayması), geçiş anlarında kısa vurgu için animasyonla ver.
 */
export const GradedPhoto: React.FC<{
  name: string;
  grade?: Grade;
  grain?: number;
  vignetteAmount?: number;
  ca?: number;
  from?: {s: number; x?: number; y?: number};
  to?: {s: number; x?: number; y?: number};
}> = ({name, grade = 'warm', grain = 0.05, vignetteAmount = 0.4, ca = 0, from = {s: 1.12}, to = {s: 1.0}}) => {
  const f = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const t = interpolate(f, [0, durationInFrames], [0, 1], clamp);
  const s = from.s + (to.s - from.s) * t;
  const x = (from.x ?? 0) + ((to.x ?? 0) - (from.x ?? 0)) * t;
  const y = (from.y ?? 0) + ((to.y ?? 0) - (from.y ?? 0)) * t;
  const effects = [
    colorCorrection(GRADES[grade]),
    ...(ca > 0 ? [chromaticAberration({amount: ca})] : []),
    vignette({amount: vignetteAmount}),
    noise({amount: grain, seed: f % 24}), // her karede farklı gren: canlı film hissi
  ];
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <Img
        src={staticFile(`foto/${name}.jpg`)}
        effects={effects}
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: `translate(${x}px, ${y}px) scale(${s})`}}
      />
    </AbsoluteFill>
  );
};

/** Parlayan başlık: HTML'i canvas'a alıp glow efekti uygular. */
export const GlowText: React.FC<{text: string; size?: number; color?: string; glowColor?: string; intensity?: number; style?: React.CSSProperties}> = ({
  text,
  size = 150,
  color = '#f4efe6',
  glowColor = '#e6cc86',
  intensity = 0.9,
  style,
}) => {
  const {width, height} = useVideoConfig();
  return (
    <HtmlInCanvas width={width} height={height} effects={[glow({radius: 28, intensity, threshold: 0.35, color: glowColor})]}>
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontFamily: "'Cormorant Garamond', serif", fontWeight: 700, fontSize: size, letterSpacing: '0.14em', color, ...style}}>{text}</div>
      </AbsoluteFill>
    </HtmlInCanvas>
  );
};

/** Kesme noktasının üstüne oynayan ışık sızıntısı. <TransitionSeries.Overlay> içinde kullan. */
export const LightLeakOverlay: React.FC<{seed?: number; hueShift?: number}> = ({seed = 0, hueShift = 0}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, height, width} = useVideoConfig();
  return (
    <Solid
      width={width}
      height={height}
      effects={[lightLeak({seed, hueShift, progress: interpolate(frame, [0, durationInFrames - 1], [0, 1], clamp)})]}
    />
  );
};
