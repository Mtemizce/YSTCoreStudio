import {useVideoConfig} from 'remotion';

/**
 * Format-bilinçli yerleşim. Aynı sahne kodu hem 16:9 (1920x1080) hem 9:16 (1080x1920) için yazılabilir.
 * Güvenli alan (px): kaynaklar çelişkili olduğu için KONSERVATİF ortak değer (bkz. sosyal-surumler skill'i):
 *   9:16: sol 120, sağ 192, üst 288, alt 672 · 16:9: her kenardan 96.
 * Metin ve ana özne `safe` kutusunda; arka plan görüntü tam ekran olabilir.
 */
export const useFormat = () => {
  const {width: W, height: H} = useVideoConfig();
  const vertical = H > W;
  const safe = vertical ? {l: 120, r: 192, t: 288, b: 672} : {l: 96, r: 96, t: 96, b: 96};
  return {
    W,
    H,
    vertical,
    safe,
    cw: W - safe.l - safe.r, // güvenli kutu genişliği
    ch: H - safe.t - safe.b, // güvenli kutu yüksekliği
    u: W / 1920 > H / 1080 ? H / 1080 : W / 1920, // yazı ölçeği birimi (1080p'ye göre)
  };
};
