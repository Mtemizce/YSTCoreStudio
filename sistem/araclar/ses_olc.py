#!/usr/bin/env python3
"""Ses ölçümü (Praat perde analizi): konuşmanın CANLILIĞINI ve cümle SONUNUN çözülüp çözülmediğini sayıyla söyler. Kulağın yerine geçmez.

  python ses_olc.py <wav|mp4> [--aralik BAS:BIT] [--json]

Çıktı:
  sure, sessizlik_orani      süre ve sessizliğin payı
  f0_medyan_hz, f0_std_st    perde medyanı ve değişkenliği (yarım ton): düz/robotik ses ≈ 1.5-2 st altı, canlı anlatım ≈ 3-5 st
  son_dusus_st               cümle sonundaki (son ~0.5 sn sesli bölge) perde medyanı ile cümle orta bölgesi farkı (yarım ton, NEGATİF = düşüyor)
                             Bildirim cümlesi doğal biter: ≈ -2…-6 st. ~0 ya da pozitif = "havada kalıyor" (soru gibi / bitmemiş)
  son_enerji_db              son 0.3 sn'nin ses seviyesi, cümle ortasına göre dB (≈ -8…-20 doğal sönüş; ≥ -3 = sönmeden kesilmiş izlenimi)
Sınırlar: ölçüt yalnızca şüpheyi gösterir; sesin güzelliğini, doğruluğunu, telaffuzu ölçmez.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import wave


def to_wav(path, aralik):
    from shutil import which
    ff = which("ffmpeg")
    if not ff:
        import media_tools
        ff = media_tools.ffmpeg()
    fd, out = tempfile.mkstemp(suffix=".wav", prefix="kurgu-ses-")
    os.close(fd)
    cmd = [ff, "-v", "error", "-y"]
    if aralik:
        s, _, e = aralik.partition(":")
        cmd += ["-ss", s, "-to", e]
    cmd += ["-i", path, "-vn", "-ac", "1", "-ar", "24000", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ses okunamadı: " + (r.stderr.strip().splitlines() or ["?"])[-1])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dosya")
    ap.add_argument("--aralik")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    import numpy as np
    import parselmouth
    wav = to_wav(a.dosya, a.aralik)
    try:
        snd = parselmouth.Sound(wav)
        with wave.open(wav) as w:
            dur = w.getnframes() / w.getframerate()
    finally:
        os.remove(wav)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=420)
    f0 = pitch.selected_array["frequency"]
    t = pitch.xs()
    voiced = f0 > 0
    inten = snd.to_intensity(minimum_pitch=70, time_step=0.01)
    iv = inten.values[0]
    it = inten.xs()
    r = {"sure": round(dur, 2)}
    if voiced.sum() < 10:
        r["hata"] = "yeterli sesli bölge yok"
    else:
        st = 12 * np.log2(f0[voiced] / 100.0)
        r["f0_medyan_hz"] = round(float(np.median(f0[voiced])), 1)
        r["f0_std_st"] = round(float(np.std(st)), 2)
        r["f0_aralik_st"] = round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2)
        tv = t[voiced]
        t_end = float(tv[-1])
        last = st[tv >= t_end - 0.5]
        mid = st[(tv >= tv[0] + (t_end - tv[0]) * 0.25) & (tv <= tv[0] + (t_end - tv[0]) * 0.75)]
        if len(last) > 3 and len(mid) > 3:
            r["son_dusus_st"] = round(float(np.median(last) - np.median(mid)), 2)
        thr = np.percentile(iv, 20)
        r["sessizlik_orani"] = round(float((iv < thr).mean()), 2)
        mid_db = float(np.percentile(iv[it <= t_end], 80))            # konuşmanın güçlü kısmı (sessizlikler medyanı bozmasın)
        endseg = iv[(it >= t_end - 0.3) & (it <= t_end)]
        if len(endseg):
            r["son_enerji_db"] = round(float(np.median(endseg)) - mid_db, 1)
        # yorum
        notes = []
        if r["f0_std_st"] < 1.8:
            notes.append("düz/monoton olabilir (f0_std_st düşük)")
        if "son_dusus_st" in r and r["son_dusus_st"] > -1.0:
            notes.append("cümle sonu düşmüyor: 'havada kalma' şüphesi")
        if "son_enerji_db" in r and r["son_enerji_db"] > -3:
            notes.append("son hece yüksek enerjiyle bitiyor: ani kesilmiş/ağır basmış olabilir")
        r["yorum"] = notes or ["ölçülebilir bir sorun yok"]
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(os.path.basename(a.dosya), a.aralik or "", "|", ", ".join(f"{k}={v}" for k, v in r.items() if k != "yorum"), "|", "; ".join(r.get("yorum", [])))


if __name__ == "__main__":
    main()
