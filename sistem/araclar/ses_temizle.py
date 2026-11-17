#!/usr/bin/env python3
"""Ses temizleme zinciri (yerel, yalnızca ffmpeg): kayıttaki dip gürültüsünü azaltır, baştaki/sondaki ve uzun boşlukları kırpar, klik/solukları sınırlar, ses seviyesini
−16 LUFS'a normalize eder. Önce/sonra ölçülür. Dikte ya da Kurgu'daki "ses ekle" noktaları için kaydettiğin sesi videoya hazırlar.

  python sistem/araclar/ses_temizle.py <girdi.(wav|webm|mp3|m4a)> -o cikti.wav [--gurultu-yok] [--kirpma-yok] [--seviye-yok] [--bosluk 0.8]

Ses klonlama / başka ses: bu araç sesi DEĞİŞTİRMEZ, yalnızca temizler. (Klon sesle dublaj, Ayarlar'da tanımlı bir 'ses-klon' sağlayıcıyla yapılır.)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which

NW = 0x08000000 if os.name == "nt" else 0


def _ff() -> str:
    f = which("ffmpeg")
    if not f:
        raise RuntimeError("ffmpeg bulunamadı")
    return f


def olc(dosya: str | Path) -> dict:
    """Ortalama/tepe ses (dB) ve süre. volumedetect."""
    r = subprocess.run([_ff(), "-hide_banner", "-nostats", "-i", str(dosya), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NW)
    o = lambda ad: (float(m.group(1)) if (m := re.search(ad + r":\s*(-?[\d.]+) dB", r.stderr)) else None)  # noqa: E731
    sure = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
    s = (int(sure.group(1)) * 3600 + int(sure.group(2)) * 60 + float(sure.group(3))) if sure else None
    return {"ortalama_db": o("mean_volume"), "tepe_db": o("max_volume"), "sure": round(s, 2) if s else None}


def temizle(girdi: str, cikti: str, gurultu: bool = True, kirpma: bool = True, seviye: bool = True, bosluk: float = 0.8) -> dict:
    filt = ["highpass=f=80"]  # uğultu/rüzgâr altı
    if gurultu:
        filt.append("afftdn=nr=18:nf=-30:tn=1")  # dip gürültüsü: ffmpeg'in kendi FFT gürültü azaltıcısı (ek model gerekmez)
    if kirpma:  # baştaki sessizliği at; ortadaki uzun boşlukları `bosluk` sn'ye indir
        filt.append(f"silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.1:stop_periods=-1:stop_duration={bosluk}:stop_threshold=-48dB:stop_silence=0.25")
    filt.append("alimiter=limit=0.95")  # klik/ani tepeleri sınırla
    if seviye:
        filt.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    once = olc(girdi)
    r = subprocess.run([_ff(), "-v", "error", "-y", "-i", str(girdi), "-af", ",".join(filt), "-ar", "48000", "-ac", "1", str(cikti)], capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NW)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + (r.stderr or "")[-300:])
    sonra = olc(cikti)
    return {"dosya": str(cikti), "once": once, "sonra": sonra, "adimlar": [f.split("=")[0] for f in filt]}


def bayttan(veri: bytes, cikti: str, uzanti: str = ".webm", **kw) -> dict:
    """Panelden gelen kayıt (webm/ogg) → temizlenmiş wav."""
    with tempfile.TemporaryDirectory() as td:
        g = Path(td) / ("giris" + (uzanti if re.fullmatch(r"\.[a-z0-9]{2,4}", uzanti) else ".webm"))
        g.write_bytes(veri)
        return temizle(str(g), cikti, **kw)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if not a or "-o" not in a:
        print(__doc__)
        return 2
    try:
        r = temizle(a[0], a[a.index("-o") + 1], "--gurultu-yok" not in a, "--kirpma-yok" not in a, "--seviye-yok" not in a, float(a[a.index("--bosluk") + 1]) if "--bosluk" in a else 0.8)
    except (RuntimeError, OSError) as e:
        print("HATA:", e)
        return 1
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
