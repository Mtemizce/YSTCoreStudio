#!/usr/bin/env python3
"""SFX bulucu ve yerleştirici (Wyzowl SFX Kit, CC0): ekrandaki ANA göre ses seç, zaman çizgisine doğru yerleştir.

  python sistem/araclar/sfx_bul.py ara "title slam" [--kategori impacts] [--en-cok 8]     anahtar kelimeyle (use_for/tags/ad) ara
  python sistem/araclar/sfx_bul.py kategoriler                                              28 kategori ve sayıları
  python sistem/araclar/sfx_bul.py bilgi whoosh-fast-hard                                   tek sesin tüm verisi
  python sistem/araclar/sfx_bul.py yerlestir whoosh-fast-hard --an 12.40 [--konusma]        başlangıç = an − sync.at ; konuşma varsa gain önerisi

Kural (kitin GUIDE.md'si): sesi, "senkron noktası" ekrandaki olayla (geçişin tepe anı, başlığın çarptığı kare…) buluşacak şekilde
başlat: başlangıç = olay zamanı − sync.at. Riser'ın senkron noktası SONUDUR. Konuşmanın altında `under_voiceover_db` kadar kıs.
Marka: ses efekti her geçişe değil, nedenli; yoğunluğu `kimlik/MARKA.md` ve `ogrenilenler.md`'ye göre ayarla.
Kit yoksa: python sistem/varlik/varlik.py indir --tur sfx
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "sistem" / "kit" / "sfx-wyzowl"


def yukle() -> dict:
    p = KIT / "sounds.json"
    if not p.exists():
        sys.exit("SFX kiti yok (isteğe bağlı). Panelde Müzik ve ses efektleri → İndir ya da: python sistem/araclar/arka_indirme.py ses")
    j = json.loads(p.read_text(encoding="utf-8"))
    s = j["sounds"]
    return s if isinstance(s, dict) else {x["id"]: x for x in s}


def kucuk(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def puan(e: dict, kelimeler: list[str]) -> int:
    metin = " ".join([e["id"], e["name"], e.get("description", ""), " ".join(e.get("use_for", [])), " ".join(e.get("tags", [])), e.get("category", "")]).lower()
    avoid = " ".join(e.get("avoid_for", [])).lower()
    p = 0
    for k in kelimeler:
        if k in e["id"].lower():
            p += 4
        if k in " ".join(e.get("use_for", [])).lower():
            p += 3
        if k in " ".join(e.get("tags", [])).lower():
            p += 2
        if k in metin:
            p += 1
        if k in avoid:
            p -= 2
    return p


def satir(e: dict) -> str:
    f = KIT / e["file"]
    return (f"{e['id']:34} {e['category']:16} {e['duration']:5.2f}s  sync@{e['sync']['at']:.2f}s  konuşma altı {e.get('under_voiceover_db', 0):+d} dB  "
            f"{'' if f.exists() else '[DOSYA YOK] '}\n    {e['description'][:110]}\n    uygun: {', '.join(e.get('use_for', [])[:3])}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    a = sp.add_parser("ara")
    a.add_argument("kelime")
    a.add_argument("--kategori")
    a.add_argument("--en-cok", type=int, default=8)
    sp.add_parser("kategoriler")
    b = sp.add_parser("bilgi")
    b.add_argument("id")
    y = sp.add_parser("yerlestir")
    y.add_argument("id")
    y.add_argument("--an", type=float, required=True, help="ekrandaki olayın zaman çizgisindeki saniyesi")
    y.add_argument("--konusma", action="store_true", help="aynı anda konuşma var")
    o = ap.parse_args()
    s = yukle()
    if o.k == "kategoriler":
        sayac: dict[str, int] = {}
        for e in s.values():
            sayac[e["category"]] = sayac.get(e["category"], 0) + 1
        for k, v in sorted(sayac.items()):
            print(f"{v:3} {k}")
    elif o.k == "ara":
        kel = [k for k in kucuk(o.kelime).split() if k]
        sonuc = sorted(((puan(e, kel), e) for e in s.values() if not o.kategori or e["category"] == o.kategori), key=lambda x: -x[0])
        for p, e in [x for x in sonuc if x[0] > 0][: o.en_cok]:
            print(satir(e) + "\n")
    elif o.k == "bilgi":
        e = s.get(o.id)
        if not e:
            sys.exit("böyle bir ses yok; 'ara' ile ara")
        e["dosya_yolu"] = str(KIT / e["file"])
        print(json.dumps(e, ensure_ascii=False, indent=1))
    elif o.k == "yerlestir":
        e = s.get(o.id)
        if not e:
            sys.exit("böyle bir ses yok")
        bas = max(0.0, o.an - e["sync"]["at"])
        r = {"ses": o.id, "dosya": str(KIT / e["file"]), "baslangic_sn": round(bas, 3), "bitis_sn": round(bas + e["timing"]["audible_end"], 3),
             "senkron": f"{e['sync']['meets']} @ {e['sync']['at']} sn", "gain_db": e.get("under_voiceover_db", 0) if o.konusma else 0,
             "not": e["sync"]["how"]}
        if o.an < e["sync"]["at"]:
            r["uyari"] = "olay sesin senkron noktasından önce: ses sıfırdan başlatıldı, senkron kayar (olayı geciktir ya da daha kısa bir ses seç)"
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
