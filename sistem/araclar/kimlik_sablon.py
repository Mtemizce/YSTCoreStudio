#!/usr/bin/env python3
"""Kimlik dosyaları (kimlik/PROFIL.md, MARKA.md, marka_kitleri/): kullanıcıya ÖZEL, depoya GİRMEZ (.gitignore). Depoda yalnızca nötr şablonlar vardır
(sistem/sablon/kimlik/); eksik olanlar şablondan kopyalanır, VAR OLAN dosyaya asla dokunulmaz.

  python sistem/araclar/kimlik_sablon.py kur                       eksik kimlik dosyalarını şablondan oluştur
  python sistem/araclar/kimlik_sablon.py durum                     kimlik dolu mu? (JSON)
  python sistem/araclar/kimlik_sablon.py kaydet --ad "Ad Soyad" [--marka "Firma"] [--rol "Mimar"] [--sehir "Şehir"]   ilk kurulum bilgileri

Kurulum (kurulum.py), panel açılışı ve güncelleme bu dosyayı çağırır. Yalnızca standart kütüphane.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("YST_KIMLIK_KOK") or Path(__file__).resolve().parents[2])
SABLON = ROOT / "sistem" / "sablon" / "kimlik"
KIMLIK = ROOT / "kimlik"


def kur() -> list[str]:
    """Eksik kimlik dosyalarını şablondan kopyalar (var olanı ezmez). Oluşturulanların listesini döndürür."""
    yeni: list[str] = []
    if not SABLON.is_dir():
        return yeni
    for k in sorted(p for p in SABLON.rglob("*") if p.is_file()):
        h = KIMLIK / k.relative_to(SABLON)
        if h.exists():
            continue
        h.parent.mkdir(parents=True, exist_ok=True)
        h.write_bytes(k.read_bytes())
        yeni.append(h.relative_to(ROOT).as_posix())
    return yeni


def _profil_alan(metin: str, etiket: str) -> str:
    m = re.search(rf"(?m)^- {re.escape(etiket)}:[ \t]*(.*)$", metin)
    return (m.group(1).strip() if m else "")


def durum() -> dict:
    kur()
    p = KIMLIK / "PROFIL.md"
    metin = p.read_text(encoding="utf-8") if p.exists() else ""
    ad = _profil_alan(metin, "Adım / marka adım")
    try:
        isim = json.loads((KIMLIK / "marka_kitleri" / "varsayilan" / "kit.json").read_text(encoding="utf-8")).get("isim", "")
    except (OSError, ValueError):
        isim = ""
    return {"ad_marka": ad, "kit_isim": isim, "dolu": bool(ad or isim)}


def kaydet(ad: str = "", marka: str = "", rol: str = "", sehir: str = "") -> dict:
    """İlk kurulumda sorulan kısa bilgiler: PROFIL.md §2 ve varsayılan marka kitinin adı. Başka alana dokunmaz."""
    kur()
    ad, marka, rol, sehir = (re.sub(r"[\r\n]+", " ", (x or "")).strip()[:120] for x in (ad, marka, rol, sehir))
    p = KIMLIK / "PROFIL.md"
    s = p.read_text(encoding="utf-8")
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    adm = " / ".join(x for x in (ad, marka) if x)
    for etiket, deger in (("Adım / marka adım", adm), ("Rolüm / işim", rol), ("Şehir / çalıştığım bölge", sehir)):
        if deger:  # boş bırakılan alan mevcut cevabı silmez
            s = re.sub(rf"(?m)^(- {re.escape(etiket)}:).*$", lambda m: f"{m.group(1)} {deger}", s, count=1)
    p.write_text(s.replace("\n", "\r\n") if crlf else s, encoding="utf-8", newline="")
    if marka or ad:
        kp = KIMLIK / "marka_kitleri" / "varsayilan" / "kit.json"
        d = json.loads(kp.read_text(encoding="utf-8"))
        d["isim"] = marka or ad
        kp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return durum()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("komut", choices=["kur", "durum", "kaydet"])
    ap.add_argument("--ad", default="")
    ap.add_argument("--marka", default="")
    ap.add_argument("--rol", default="")
    ap.add_argument("--sehir", default="")
    a = ap.parse_args()
    if a.komut == "kur":
        print(json.dumps({"olusturulan": kur()}, ensure_ascii=False))
    elif a.komut == "durum":
        print(json.dumps(durum(), ensure_ascii=False))
    else:
        print(json.dumps(kaydet(a.ad, a.marka, a.rol, a.sehir), ensure_ascii=False))
