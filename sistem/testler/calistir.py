#!/usr/bin/env python3
"""Geliştirici testleri çalıştırıcısı.

  python sistem/testler/calistir.py                 hızlı testler (ağ ve gerçek model gerekmez)
  python sistem/testler/calistir.py --canli         ayrıca canlı testler: çalışan panel (127.0.0.1:8700) ve kurulu modeller (Pocket TTS, EMA, Whisper) ister
  python sistem/testler/calistir.py kimlik donanim  yalnızca adı geçenler (test_<ad>.py ya da canli_<ad>.py)

Notlar:
- Çalıştırdığın Python, kurulumun sanal ortamındaki olmalı (Windows: sistem\\ortam\\venv\\Scripts\\python.exe, Linux/macOS: sistem/ortam/venv/bin/python).
- Testler ayarları ve geçici `zz-*` projelerini kendileri yedekleyip geri yükler; yine de çalışan panelin KAPALI olması gerekir
  (panel_api/modul_panel/drive/guncelleme testleri kendi panelini açar). Canlı testler tersine paneli AÇIK ister.
- Sonuç satırı testin kendi çıktısından okunur ("N başarılı, M başarısız", "SONUÇ: N tamam, M hata" ya da "TÜM TESTLER GEÇTİ").
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

AD = Path(__file__).resolve().parent
ROOT = AD.parents[1]
sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
import yol  # noqa: E402

yol.hazirla()  # kurulumun getirdiği ffmpeg sistemde yoksa da testler bulsun
ZAMAN = 900


def karar(cikti: str, rc: int) -> tuple[bool, str]:
    satirlar = [x for x in cikti.strip().splitlines() if x.strip()]
    son = satirlar[-1] if satirlar else ""
    if rc != 0:
        return False, f"çıkış kodu {rc}: {son[:110]}"
    for pat in (r"(\d+) başarılı, (\d+) başarısız", r"SONUÇ: (\d+) tamam, (\d+) hata"):
        m = re.search(pat, cikti)
        if m:
            return int(m.group(2)) == 0 and int(m.group(1)) > 0, f"{m.group(1)} tamam, {m.group(2)} hata"
    if "TÜM TESTLER GEÇTİ" in cikti:
        return True, "tüm testler geçti"
    return False, "sonuç satırı bulunamadı: " + son[:100]


def main() -> int:
    a = sys.argv[1:]
    canli = "--canli" in a
    adlar = [x for x in a if not x.startswith("--")]
    dosyalar = sorted(AD.glob("test_*.py")) + (sorted(AD.glob("canli_*.py")) if canli else [])
    if adlar:
        dosyalar = [f for f in sorted(AD.glob("*_*.py")) if f.stem.split("_", 1)[1] in adlar and f.stem.split("_", 1)[0] in ("test", "canli")]
    if not dosyalar:
        print("çalıştırılacak test bulunamadı")
        return 2
    kotu = []
    kul = ROOT / "sistem" / "ayar" / "kullanici.json"  # temiz klonda yoktur (git'e girmez); bazı testler yedekleyip geri yükler
    if not kul.exists():
        kul.write_text("{}", encoding="utf-8")
    t0 = time.time()
    for f in dosyalar:
        t = time.time()
        cikti = ""
        try:
            r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=ZAMAN,
                               env={**__import__("os").environ, "PYTHONUTF8": "1", "YST_ARKA_YOK": "1"})
            cikti = r.stdout + r.stderr
            iyi, ozet = karar(cikti, r.returncode)
        except subprocess.TimeoutExpired:
            iyi, ozet = False, f"{ZAMAN} sn içinde bitmedi"
        print(f"{'OK  ' if iyi else 'HATA'} {f.stem:24} {time.time() - t:5.1f} sn  {ozet}", flush=True)
        if not iyi:
            kotu.append(f.stem)
            # başarısızlığın nedenini (CI günlüğünde de) görmek için testin çıktısının sonu
            for s in [x for x in cikti.strip().splitlines() if x.strip()][-14:]:
                print("      | " + s[:220], flush=True)
    print(f"\n{len(dosyalar) - len(kotu)}/{len(dosyalar)} test dosyası geçti ({time.time() - t0:.0f} sn)" + (f"; başarısız: {', '.join(kotu)}" if kotu else ""))
    return 1 if kotu else 0


if __name__ == "__main__":
    sys.exit(main())
