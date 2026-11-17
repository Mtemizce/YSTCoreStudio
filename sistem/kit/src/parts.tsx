import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Easing, Img, continueRender, delayRender, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, sans, serif} from './theme';
import {useFormat} from './layout';

export const ease = Easing.bezier(0.22, 1, 0.36, 1);
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const FACES: [string, string, string][] = [
  ['Cormorant Garamond', 'CormorantGaramond-Regular.ttf', '400'],
  ['Cormorant Garamond', 'CormorantGaramond-Bold.ttf', '700'],
  ['Cormorant Garamond', 'CormorantGaramond-Italic.ttf', 'italic'],
  ['Inter', 'Inter-Regular.ttf', '400'],
  ['Inter', 'Inter-Medium.ttf', '500'],
  ['Inter', 'Inter-SemiBold.ttf', '600'],
];

/** Yerel font dosyaları (proje media/fonts/): render, fontlar hazır olana kadar bekler. */
export const useFonts = () => {
  const [handle] = useState(() => delayRender('fontlar'));
  useEffect(() => {
    Promise.all(
      FACES.map(([family, file, weight]) => {
        const italic = weight === 'italic';
        const face = new FontFace(family, `url(${staticFile('fonts/' + file)})`, {weight: italic ? '400' : weight, style: italic ? 'italic' : 'normal'});
        return face.load().then((f) => document.fonts.add(f));
      }),
    )
      .catch(() => undefined)
      .finally(() => continueRender(handle));
  }, [handle]);
};

type Move = {s?: number; x?: number; y?: number};

/** Ken Burns hareketli fotoğraf. fit='cover' (tam ekran) ya da 'contain'. `focus` 0-1: kırpmada öznenin yatay/dikey konumu. */
export const Photo: React.FC<{
  name: string;
  from?: Move;
  to?: Move;
  frames?: number;
  bright?: number;
  sat?: number;
  gray?: number;
  blur?: number;
  fit?: 'cover' | 'contain';
  focus?: [number, number];
  style?: React.CSSProperties;
}> = ({name, from = {}, to = {}, frames, bright = 1, sat = 1, gray = 0, blur = 0, fit = 'cover', focus = [0.5, 0.5], style}) => {
  const f = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const n = frames ?? durationInFrames;
  const t = interpolate(f, [0, n], [0, 1], {...clamp, easing: Easing.inOut(Easing.sin)});
  const s = (from.s ?? 1) + ((to.s ?? 1.08) - (from.s ?? 1)) * t;
  const x = (from.x ?? 0) + ((to.x ?? 0) - (from.x ?? 0)) * t;
  const y = (from.y ?? 0) + ((to.y ?? 0) - (from.y ?? 0)) * t;
  return (
    <AbsoluteFill style={{overflow: 'hidden', ...style}}>
      <Img
        src={staticFile(`foto/${name}.jpg`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: fit,
          objectPosition: `${focus[0] * 100}% ${focus[1] * 100}%`,
          transform: `translate(${x}px, ${y}px) scale(${s})`,
          filter: `brightness(${bright}) saturate(${sat}) grayscale(${gray}) blur(${blur}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

export const Scrim: React.FC<{bottom?: number; top?: number; vignette?: number}> = ({bottom = 0.75, top = 0.35, vignette = 0.45}) => (
  <AbsoluteFill style={{pointerEvents: 'none'}}>
    <AbsoluteFill style={{background: `linear-gradient(to top, rgba(10,12,15,${bottom}) 0%, rgba(10,12,15,0) 48%)`}} />
    <AbsoluteFill style={{background: `linear-gradient(to bottom, rgba(10,12,15,${top}) 0%, rgba(10,12,15,0) 28%)`}} />
    <AbsoluteFill style={{background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,${vignette}) 100%)`}} />
  </AbsoluteFill>
);

/** Köşelerden çizilerek açılan ince altın çerçeve (kenardan `inset` px). */
export const GoldFrame: React.FC<{start?: number; inset?: number}> = ({start = 0, inset = 44}) => {
  const f = useCurrentFrame();
  const {W, H} = useFormat();
  const p = interpolate(f, [start, start + 40], [0, 1], {...clamp, easing: ease});
  const w = (W - inset * 2) * p;
  const h = (H - inset * 2) * p;
  const line = {position: 'absolute' as const, background: C.gold, opacity: 0.8};
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{...line, left: inset, top: inset, width: w, height: 2}} />
      <div style={{...line, left: inset, top: inset, width: 2, height: h}} />
      <div style={{...line, right: inset, bottom: inset, width: w, height: 2}} />
      <div style={{...line, right: inset, bottom: inset, width: 2, height: h}} />
    </AbsoluteFill>
  );
};

export const Pill: React.FC<{text: string; style?: React.CSSProperties; dark?: boolean; size?: number}> = ({text, style, dark = true, size = 26}) => (
  <div
    style={{
      position: 'absolute',
      padding: `${size * 0.55}px ${size * 1.15}px`,
      borderRadius: 999,
      border: `2px solid ${C.gold}`,
      background: dark ? 'rgba(14,16,19,0.72)' : C.gold,
      color: dark ? C.goldSoft : C.ink,
      fontFamily: sans,
      fontWeight: 600,
      fontSize: size,
      letterSpacing: '0.28em',
      ...style,
    }}
  >
    {text}
  </div>
);

/** Serif başlık + altın alt başlık. `anchor`: güvenli kutunun neresine (alt-sol / üst-sol / merkez). */
export const TitleBlock: React.FC<{title: string; sub?: string; start?: number; anchor?: 'bl' | 'tl' | 'c'; size?: number}> = ({title, sub, start = 0, anchor = 'bl', size}) => {
  const f = useCurrentFrame();
  const {safe, u, vertical, cw} = useFormat();
  const a = interpolate(f, [start, start + 28], [0, 1], {...clamp, easing: ease});
  const b = interpolate(f, [start + 12, start + 40], [0, 1], {...clamp, easing: ease});
  const fs = size ?? (vertical ? 112 : 112) * u;
  const pos: React.CSSProperties =
    anchor === 'bl' ? {left: safe.l, bottom: safe.b} : anchor === 'tl' ? {left: safe.l, top: safe.t} : {left: safe.l, top: safe.t + 200 * u};
  return (
    <div style={{position: 'absolute', width: cw, ...pos}}>
      <div style={{width: 120 * a * u, height: 3, background: C.gold, marginBottom: 26 * u}} />
      <div style={{fontFamily: serif, fontWeight: 700, fontSize: fs, lineHeight: 1.02, color: C.paper, opacity: a, transform: `translateY(${(1 - a) * 34}px)`, textShadow: '0 6px 30px rgba(0,0,0,.55)'}}>{title}</div>
      {sub ? (
        <div style={{fontFamily: sans, fontWeight: 500, fontSize: 28 * u, letterSpacing: '0.34em', color: C.goldSoft, marginTop: 22 * u, opacity: b, transform: `translateY(${(1 - b) * 20}px)`}}>
          {sub.toLocaleUpperCase('tr-TR')}
        </div>
      ) : null}
    </div>
  );
};
