import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, sans} from './theme';
import {useFormat} from './layout';

export type Word = {baslangic: number; bitis: number; kelime: string};

/**
 * Kelime zamanlı altyazı (yazi_cikar.py çıktısı: kelimeler[]). Aktif kelime altın, diğerleri sıcak beyaz.
 * `offset`: kelime zamanlarına eklenecek sn (ses katmanının sahnedeki başlangıcı). `perLine`: satırdaki kelime sayısı (dikey 2-3, yatay 6-7).
 * `y`: güvenli kutuya göre değil, kare yüksekliğine kesri (dikey 0.60 → alt arayüzün üstünde).
 */
export const Captions: React.FC<{words: Word[]; offset?: number; perLine?: number; y?: number; upper?: boolean; kinetic?: boolean}> = ({words, offset = 0, perLine, y, upper = false, kinetic = false}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {W, H, vertical, safe, u} = useFormat();
  const per = perLine ?? (vertical ? 3 : 7);
  const t = f / fps - offset;
  // Satırlar: cümle sınırında (. ? ! …) biter; cümle `per`'den uzunsa DENGELİ bölünür (4 kelime = 2+2, "her / detay." gibi yalnız kelime kalmaz)
  const groups: number[][] = [];
  let sent: number[] = [];
  const flush = () => {
    if (!sent.length) return;
    const k = Math.ceil(sent.length / per);
    const base = Math.floor(sent.length / k);
    let extra = sent.length % k;
    let p = 0;
    for (let g = 0; g < k; g++) {
      const size = base + (extra-- > 0 ? 1 : 0);
      groups.push(sent.slice(p, p + size));
      p += size;
    }
    sent = [];
  };
  words.forEach((w, i) => {
    sent.push(i);
    if (/[.?!…]$/.test(w.kelime)) flush();
  });
  flush();
  let idx = words.findIndex((w) => t >= w.baslangic && t < w.bitis + 0.12);
  if (idx < 0) idx = words.findIndex((w) => w.baslangic > t) - 1;
  if (idx < 0 || t < words[0].baslangic - 0.05 || t > words[words.length - 1].bitis + 0.4) return null;
  const gi = groups.findIndex((g) => g.includes(idx));
  const group = groups[gi].map((k) => words[k]);
  const g0 = groups[gi][0];
  const gStart = group[0].baslangic;
  const gEnd = group[group.length - 1].bitis;
  if (t > gEnd + 0.35 && gi + 1 < groups.length) return null;
  const pop = spring({frame: (t - gStart) * fps, fps, config: {damping: 16, stiffness: 180, mass: 0.7}});
  const size = (vertical ? 78 : 64) * (vertical ? 1 : u);
  const yy = (y ?? (vertical ? 0.6 : 0.86)) * H;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          left: safe.l,
          width: W - safe.l - safe.r,
          top: yy,
          transform: `translateY(-50%) scale(${interpolate(pop, [0, 1], [0.94, 1])})`,
          textAlign: 'center',
          fontFamily: sans,
          fontWeight: 600,
          fontSize: size,
          lineHeight: 1.12,
          letterSpacing: '0.01em',
          textShadow: '0 4px 22px rgba(0,0,0,.75), 0 0 2px rgba(0,0,0,.9)',
          opacity: interpolate(t, [gStart - 0.02, gStart + 0.08], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        {group.map((w, i) => {
          const active = g0 + i === idx;
          const txt = upper ? w.kelime.toLocaleUpperCase('tr-TR') : w.kelime;
          const movement = active && kinetic ? spring({
            frame: Math.max(0, (t - w.baslangic) * fps), fps,
            config: {damping: 17, stiffness: 220, mass: 0.8},
          }) : 1;
          const emphasis = active && kinetic ? {
            display: 'inline-block',
            transform: `translateY(${(1 - movement) * 12}px) scale(${0.92 + movement * 0.08})`,
            opacity: 0.65 + Math.min(1, movement) * 0.35,
          } : {};
          return (
            <React.Fragment key={i}>
              <span style={{color: active ? C.gold : C.paper, ...emphasis}}>{txt}</span>
              {i < group.length - 1 ? ' ' : ''}
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
