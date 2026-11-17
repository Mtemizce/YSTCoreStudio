#!/usr/bin/env python3
"""Proje durumu (projeler/<ad>/durum.json): orkestratör aşamayı buraya yazar, panel okuyup gösterir ve "Onaylıyorum"u buna bağlar.

  python sistem/araclar/durum.py goster <proje>
  python sistem/araclar/durum.py ayarla <proje> <aşama> [--not "metin"]
  python sistem/araclar/durum.py asamalar

Aşamalar (sırayla): hazirlaniyor → planlama → plan-onayi-bekliyor → uretiliyor → taslak-hazir → onaylandi → final-render → platform-surumleri → teslim
  taslak-hazir : önizleme Kurgu'da; kullanıcı not bırakabilir ya da panelden "Onaylıyorum" der (onay.json yazılır, aşama 'onaylandi' olur)
  engel        : orkestratör bir karara/izne takıldı (not alanına nedeni yaz)
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASAMALAR = ["hazirlaniyor", "planlama", "plan-onayi-bekliyor", "uretiliyor", "taslak-hazir", "onaylandi", "final-render", "platform-surumleri", "teslim", "engel"]
ETIKET = {"hazirlaniyor": "hazırlanıyor", "planlama": "planlanıyor", "plan-onayi-bekliyor": "plan onayı bekliyor", "uretiliyor": "üretiliyor",
          "taslak-hazir": "taslak hazır: önizle", "onaylandi": "onaylandı", "final-render": "final render", "platform-surumleri": "platform sürümleri",
          "teslim": "teslim edildi", "engel": "engel var"}
AD_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def yol(proje: str) -> Path:
    if not AD_RE.match(proje or ""):
        raise ValueError("geçersiz proje adı")
    return ROOT / "projeler" / proje / "durum.json"


def oku(proje: str) -> dict:
    try:
        return json.loads(yol(proje).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"asama": "hazirlaniyor", "not": "", "guncelleme": None}


def yaz(proje: str, asama: str, not_: str = "") -> dict:
    if asama not in ASAMALAR:
        raise ValueError(f"geçersiz aşama '{asama}' (geçerli: {', '.join(ASAMALAR)})")
    p = yol(proje)
    if not p.parent.is_dir():
        raise ValueError("proje yok")
    d = {"asama": asama, "etiket": ETIKET[asama], "not": not_, "guncelleme": time.strftime("%Y-%m-%d %H:%M:%S")}
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    try:
        if a[:1] == ["asamalar"]:
            print(" → ".join(ASAMALAR[:-1]))
        elif a[:1] == ["goster"] and len(a) > 1:
            print(json.dumps(oku(a[1]), ensure_ascii=False, indent=1))
        elif a[:1] == ["ayarla"] and len(a) > 2:
            print(json.dumps(yaz(a[1], a[2], a[a.index("--not") + 1] if "--not" in a else ""), ensure_ascii=False))
        else:
            print(__doc__)
            return 2
    except ValueError as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
