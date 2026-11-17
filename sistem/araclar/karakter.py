#!/usr/bin/env python3
"""Karakter paketi (dijital ikiz): kişinin boy + yakın portre fotoğrafı, RIZA kaydı ve ses tercihi. B planı ve seri/dizi bu karakteri kullanır.
Yalnızca KENDİ benzerliğin (ya da yazılı izni olan kişi) içindir: rıza onayı ve onaylayanın adı olmadan karakter oluşmaz.

  python sistem/araclar/karakter.py liste
  python sistem/araclar/karakter.py olustur <ad> --veren "Ad Soyad" --onay --boy boy.jpg --portre portre.jpg
  python sistem/araclar/karakter.py goster <ad>        python sistem/araclar/karakter.py sil <ad>

Konum: kimlik/karakterler/<ad>/ (karakter.json + boy.jpg + portre.jpg). Profil dışa aktarmaya kimlik klasörüyle birlikte girer.
Fotoğraflar buluta KENDİLİĞİNDEN gitmez; üretken (bulut) ikiz yalnızca kullanıcı o işlem için onay verirse ve bağlayıcı etkinse kullanılır.
"""
from __future__ import annotations

import base64
import io
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOK = ROOT / "kimlik" / "karakterler"
RIZA_METNI = "Fotoğraflardaki kişi benim (ya da yazılı iznim var). Dijital sunucu / dijital ikiz videolarında benzerliğimin kullanılmasına izin veriyorum; bunu istediğim zaman geri alabilirim."
EN_COK_BAYT = 15_000_000


def slug(ad: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "-", str(ad).translate(tr).lower()).strip("-")[:40]
    if not s:
        raise ValueError("karakter adı gerekli")
    return s


def _foto_kaydet(veri: bytes, hedef: Path, ad: str) -> tuple[int, int]:
    from PIL import Image, ImageOps
    if not veri or len(veri) > EN_COK_BAYT:
        raise ValueError(f"{ad} fotoğrafı boş ya da çok büyük (en çok {EN_COK_BAYT // 1_000_000} MB)")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(veri))).convert("RGB")
    except Exception:  # noqa: BLE001
        raise ValueError(f"{ad}: geçerli bir görüntü dosyası değil") from None
    if min(im.size) < 400:
        raise ValueError(f"{ad} fotoğrafı çok küçük (kısa kenar en az 400 px)")
    im.thumbnail((3000, 3000))
    im.save(hedef, "JPEG", quality=93)
    return im.size


def olustur(ad: str, veren: str, onay: bool, boy: bytes, portre: bytes, ses: dict | None = None) -> dict:
    if not onay:
        raise ValueError("rıza onayı olmadan karakter oluşturulmaz: " + RIZA_METNI)
    veren = (veren or "").strip()
    if len(veren) < 3:
        raise ValueError("rızayı veren kişinin adı soyadı gerekli")
    s = slug(ad)
    d = KOK / s
    if d.exists():
        raise ValueError(f"'{s}' adlı karakter zaten var (önce sil ya da başka ad ver)")
    d.mkdir(parents=True)
    try:
        wb = _foto_kaydet(boy, d / "boy.jpg", "boy")
        wp = _foto_kaydet(portre, d / "portre.jpg", "portre")
        k = {"surum": 1, "ad": ad.strip()[:60], "id": s, "olusturma": time.strftime("%Y-%m-%d %H:%M:%S"),
             "riza": {"veren": veren[:80], "tarih": time.strftime("%Y-%m-%d"), "metin": RIZA_METNI, "kendi_benzerligi": True},
             "fotograflar": {"boy": "boy.jpg", "portre": "portre.jpg", "boy_boyut": list(wb), "portre_boyut": list(wp)},
             "ses": ses or {"kaynak": "ema"}, "etiket": {"varsayilan": False, "metin": "Dijital sunum"}}
        (d / "karakter.json").write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return k


def oku(s: str) -> dict:
    p = KOK / slug(s) / "karakter.json"
    if not p.is_file():
        raise ValueError(f"karakter yok: {s}")
    return json.loads(p.read_text(encoding="utf-8"))


def liste() -> list[dict]:
    out = []
    if KOK.is_dir():
        for p in sorted(KOK.glob("*/karakter.json")):
            try:
                k = json.loads(p.read_text(encoding="utf-8"))
                out.append({"id": k["id"], "ad": k["ad"], "riza": k["riza"]["veren"], "tarih": k["riza"]["tarih"], "ses": k.get("ses", {}), "etiket": k.get("etiket", {}),
                            "hazir": hazir(k["id"])[0]})
            except (OSError, ValueError, KeyError):
                pass
    return out


def hazir(s: str) -> tuple[bool, list[str]]:
    """B planı için karakter hazır mı? (rıza + iki fotoğraf)"""
    eksik = []
    try:
        k = oku(s)
    except ValueError as e:
        return False, [str(e)]
    d = KOK / k["id"]
    if not k.get("riza", {}).get("veren"):
        eksik.append("rıza kaydı yok")
    for f in ("boy.jpg", "portre.jpg"):
        if not (d / f).is_file():
            eksik.append(f"{f} yok")
    return not eksik, eksik


def yollar(s: str) -> dict:
    k = oku(s)
    d = KOK / k["id"]
    return {"boy": str(d / "boy.jpg"), "portre": str(d / "portre.jpg"), "karakter": k}


def sil(s: str) -> None:
    d = KOK / slug(s)
    if d.resolve().parent != KOK.resolve():
        raise ValueError("geçersiz karakter")
    shutil.rmtree(d, ignore_errors=True)


def b64_coz(v: str) -> bytes:
    return base64.b64decode(v.split(",", 1)[-1]) if v else b""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    try:
        if not a or a[0] == "liste":
            for k in liste():
                print(f"{k['id']:20} {k['ad']:24} rıza: {k['riza']} ({k['tarih']})  {'HAZIR' if k['hazir'] else 'EKSİK'}")
        elif a[0] == "olustur":
            g = lambda n, v=None: a[a.index(n) + 1] if n in a else v  # noqa: E731
            k = olustur(a[1], g("--veren", ""), "--onay" in a, Path(g("--boy")).read_bytes(), Path(g("--portre")).read_bytes())
            print("oluşturuldu:", k["id"])
        elif a[0] == "goster":
            print(json.dumps(oku(a[1]), ensure_ascii=False, indent=1))
        elif a[0] == "sil":
            sil(a[1])
            print("silindi")
        else:
            print(__doc__)
            return 2
    except (ValueError, OSError, IndexError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
