import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {C, sans, serif} from './theme';
import {useFormat} from './layout';
import {clamp, ease, useFonts} from './parts';

/**
 * MARKA KİTİ bileşenleri: proje başına `remotion/src/marka.json` (yeni_proje.py yazar) + `media/marka/<logo>` kullanır.
 * Kullanım (sahne kodu):  import marka from './marka.json';  <MarkaIntro marka={marka}/>  <MarkaOutro marka={marka}/>  <Filigran marka={marka}/>
 * Her bölüm marka.intro.acik / outro.acik / filigran.acik anahtarlarıyla kapatılabilir; kapalıysa hiçbir şey çizmez (null) ve süre 0 olur.
 * Süreler: markaSure(marka, fps) → {intro, outro} kare. Toplam süreye ekle.
 */
export type Marka = {
  isim?: string;
  slogan?: string;
  logo?: string | null; // media/marka/ içindeki dosya adı
  imza_cumle?: string;
  iletisim_goster?: boolean;
  iletisim?: {telefon?: string; eposta?: string; web?: string; instagram?: string; adres?: string};
  renkler?: {zemin?: string; metin?: string; vurgu?: string};
  intro?: {acik?: boolean; sure?: number};
  outro?: {acik?: boolean; sure?: number};
  filigran?: {acik?: boolean; konum?: 'sag-alt' | 'sol-alt' | 'sag-ust' | 'sol-ust'; opaklik?: number; boyut?: number};
};

const renk = (m: Marka) => ({zemin: m.renkler?.zemin || C.ink, metin: m.renkler?.metin || C.paper, vurgu: m.renkler?.vurgu || C.gold});

export const markaSure = (m: Marka, fps: number) => ({
  intro: m.intro?.acik ? Math.round((m.intro.sure ?? 2.5) * fps) : 0,
  outro: m.outro?.acik ? Math.round((m.outro.sure ?? 3.5) * fps) : 0,
});

const Logo: React.FC<{marka: Marka; yukseklik: number; style?: React.CSSProperties}> = ({marka, yukseklik, style}) =>
  marka.logo ? <Img src={staticFile(`marka/${marka.logo}`)} style={{height: yukseklik, width: 'auto', objectFit: 'contain', ...style}} /> : null;

/** Açılış: logo + isim (harf aralıklı serif) + slogan; ince vurgu çizgisi. Sakin, ağırlıklı hareket (MARKA.md): uzun kuyruklu ease-out, ölü durur. */
export const MarkaIntro: React.FC<{marka: Marka}> = ({marka}) => {
  useFonts();
  const f = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const {u: fu, vertical} = useFormat();
  const u = vertical ? 1 : fu; // dikeyde (1080 px geniş) tasarım pikseli, yatayda 1080p'ye göre ölçek
  const r = renk(marka);
  if (!marka.intro?.acik) return null;
  const gir = interpolate(f, [0, fps * 0.8], [0, 1], {...clamp, easing: ease});
  const cik = interpolate(f, [durationInFrames - fps * 0.4, durationInFrames], [1, 0], clamp);
  const cizgi = interpolate(f, [fps * 0.3, fps * 1.2], [0, 1], {...clamp, easing: ease});
  return (
    <AbsoluteFill style={{background: r.zemin, alignItems: 'center', justifyContent: 'center', opacity: cik}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 28 * u, opacity: gir, transform: `translateY(${(1 - gir) * 18 * u}px)`}}>
        <Logo marka={marka} yukseklik={(vertical ? 150 : 170) * u} />
        {marka.isim ? (
          <div style={{fontFamily: serif, fontWeight: 700, fontSize: (vertical ? 62 : 92) * u, letterSpacing: '0.12em', color: r.metin, textAlign: 'center'}}>{marka.isim}</div>
        ) : null}
        <div style={{width: 160 * u * cizgi, height: 2 * u, background: r.vurgu}} />
        {marka.slogan ? <div style={{fontFamily: sans, fontWeight: 500, fontSize: 28 * u, letterSpacing: '0.32em', textTransform: 'none', color: r.vurgu, textAlign: 'center'}}>{marka.slogan}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/** Kapanış: logo + isim + imza cümle + (isteniyorsa) iletişim bilgileri. İletişim yalnızca marka.iletisim_goster açıksa ve değer varsa çizilir. */
export const MarkaOutro: React.FC<{marka: Marka}> = ({marka}) => {
  useFonts();
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {u: fu, vertical, safe, W, H} = useFormat();
  const u = vertical ? 1 : fu;
  const r = renk(marka);
  if (!marka.outro?.acik) return null;
  const gir = interpolate(f, [0, fps * 0.9], [0, 1], {...clamp, easing: ease});
  const satir = marka.iletisim_goster
    ? Object.entries(marka.iletisim || {}).filter(([, v]) => v && String(v).trim()).map(([, v]) => String(v))
    : [];
  return (
    <AbsoluteFill style={{background: r.zemin}}>
      <div
        style={{
          position: 'absolute', left: safe.l, top: safe.t, width: W - safe.l - safe.r, height: H - safe.t - safe.b,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 26 * u,
          opacity: gir, transform: `translateY(${(1 - gir) * 16 * u}px)`,
        }}
      >
        <Logo marka={marka} yukseklik={(vertical ? 130 : 150) * u} />
        {marka.isim ? <div style={{fontFamily: serif, fontWeight: 700, fontSize: (vertical ? 58 : 84) * u, letterSpacing: '0.1em', color: r.metin, textAlign: 'center'}}>{marka.isim}</div> : null}
        <div style={{width: 140 * u, height: 2 * u, background: r.vurgu}} />
        {marka.imza_cumle ? <div style={{fontFamily: serif, fontStyle: 'italic', fontSize: (vertical ? 40 : 48) * u, color: r.vurgu, textAlign: 'center', lineHeight: 1.25}}>{marka.imza_cumle}</div> : null}
        {satir.length ? (
          <div style={{display: 'flex', flexDirection: 'column', gap: 10 * u, marginTop: 14 * u}}>
            {satir.map((s, i) => (
              <div key={i} style={{fontFamily: sans, fontWeight: 600, fontSize: 30 * u, letterSpacing: '0.06em', color: r.metin, textAlign: 'center'}}>{s}</div>
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

/** Filigran: videonun üstünde köşede küçük logo (yoksa isim). Güvenli kutu içinde durur (dikeyde platform arayüzüyle çakışmaz). */
export const Filigran: React.FC<{marka: Marka}> = ({marka}) => {
  useFonts();
  const {u: fu, vertical, safe} = useFormat();
  const u = vertical ? 1 : fu;
  const r = renk(marka);
  const fg = marka.filigran;
  if (!fg?.acik || (!marka.logo && !marka.isim)) return null;
  const konum = fg.konum || 'sag-alt';
  const stil: React.CSSProperties = {position: 'absolute', opacity: fg.opaklik ?? 0.6};
  if (konum.endsWith('alt')) stil.bottom = safe.b; else stil.top = safe.t;
  if (konum.startsWith('sag')) stil.right = safe.r; else stil.left = safe.l;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={stil}>
        {marka.logo ? (
          <Logo marka={marka} yukseklik={(fg.boyut ?? 0.09) * 1080 * u} />
        ) : (
          <div style={{fontFamily: serif, fontWeight: 700, fontSize: 30 * u, letterSpacing: '0.14em', color: r.metin, textShadow: '0 1px 6px rgba(0,0,0,0.55)'}}>{marka.isim}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};
