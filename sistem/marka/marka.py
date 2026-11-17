#!/usr/bin/env python3
"""Marka kitleri: kimlik/marka_kitleri/<id>/kit.json (+ logo). Her projede seçilir; intro, outro, filigran, iletişim bilgisi açılıp kapanır.

  python sistem/marka/marka.py liste
  python sistem/marka/marka.py goster <kit>
  python sistem/marka/marka.py uygula <proje> [--kit <id>] [--intro 0|1] [--outro 0|1] [--filigran 0|1] [--iletisim 0|1]
      → projeler/<proje>/<format>/media/marka/<logo> ve .../remotion/src/marka.json yazılır (sahne kodundaki MarkaIntro/MarkaOutro/Filigran bunu okur)

Marka kiti ≠ MARKA.md: MARKA.md görsel kimliğin KİLİTLİ KURALLARI (renk, yazı tipi, yasaklar); kit ise ÖĞELERİ (logo, isim, iletişim, imza cümle) ve bu projede kullanılıp kullanılmayacağı.
Hiçbir alan zorunlu değil: logo yoksa isim yazısı kullanılır; iletişim boşsa gösterilmez.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KITLER = ROOT / "kimlik" / "marka_kitleri"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGO_UZ = (".png", ".svg", ".jpg", ".jpeg", ".webp")
KONUMLAR = ("sag-alt", "sol-alt", "sag-ust", "sol-ust")
IL_ALANLAR = ("telefon", "eposta", "web", "instagram", "adres")


def kit_klasoru(kid: str) -> Path:
    if not ID_RE.match(kid or ""):
        raise ValueError("geçersiz kit adı (küçük harf, rakam, tire)")
    return KITLER / kid


def slug(ad: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", ad.translate(tr).lower()).strip("-")[:40] or "kit"


def oku(kid: str) -> dict:
    p = kit_klasoru(kid) / "kit.json"
    if not p.is_file():
        raise ValueError(f"marka kiti yok: {kid}")
    return json.loads(p.read_text(encoding="utf-8"))


def liste() -> list[dict]:
    out = []
    if KITLER.is_dir():
        for d in sorted(KITLER.iterdir()):
            if (d / "kit.json").is_file():
                k = json.loads((d / "kit.json").read_text(encoding="utf-8"))
                out.append({"id": d.name, "ad": k.get("ad", d.name), "isim": k.get("isim", ""), "logo": bool(k.get("logo")), "logo_sayisi": len(k.get("logolar") or []),
                            "kural_sayisi": len(k.get("kullanim") or []), "iletisim_var": any((k.get("iletisim") or {}).values())})
    return out


def _metin(v, n=200) -> str:
    return str(v or "").strip()[:n]


LOGO_TURLERI = ("ana", "simge", "yatay", "koyu-zemin", "acik-zemin", "diger")
METIN_TURLERI = ("isim", "slogan", "iletisim", "cta", "yasal", "diger")
OGE_RE = re.compile(r"^(genel|intro|outro|filigran|kapak|(logo|metin|renk):[a-z0-9-]{1,40})$")
FONT_RE = re.compile(r"^[a-z0-9-]{0,40}$")
LISTE_EN_COK = 30


def _id(v, yedek: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9-]+", "-", str(v or "").translate(tr).lower()).strip("-")[:40]
    return s or yedek


def _benzersiz(liste: list[dict], oneki: str) -> list[dict]:
    """id'leri boşsa üret, yinelenenleri ele."""
    out, gorulen = [], set()
    for i, x in enumerate(liste[:LISTE_EN_COK], 1):
        x["id"] = _id(x.get("id") or x.get("ad"), f"{oneki}{i}")
        if x["id"] in gorulen:
            continue
        gorulen.add(x["id"])
        out.append(x)
    return out


def dogrula(k: dict, eski: dict | None = None) -> dict:
    """Panelden/dışarıdan gelen kit'i temizler: yalnızca bilinen alanlar, sınırlı uzunluk, geçerli renk/konum.
    eski: kayıtlı kit; logo dosyaları panelden gelmez, kimlikle eşlenip eskisinden korunur."""
    eski = eski or {}
    out = {"id": k["id"], "ad": _metin(k.get("ad") or k["id"], 80), "isim": _metin(k.get("isim"), 80), "slogan": _metin(k.get("slogan"), 100),
           "logo": k.get("logo") if (isinstance(k.get("logo"), str) and Path(k["logo"]).name == k["logo"] and k["logo"].lower().endswith(LOGO_UZ)) else None,
           "imza_cumle": _metin(k.get("imza_cumle"), 140),
           "iletisim": {a: _metin((k.get("iletisim") or {}).get(a), 120) for a in IL_ALANLAR}}
    r = k.get("renkler") or {}
    out["renkler"] = {a: (r.get(a) if HEX_RE.match(str(r.get(a) or "")) else d) for a, d in (("zemin", "#0E1013"), ("metin", "#F4EFE6"), ("vurgu", "#C9A24D"))}
    ek = []
    for x in (k.get("ek_renkler") or [])[:12]:
        if isinstance(x, dict) and HEX_RE.match(str(x.get("hex") or "")):
            ek.append({"ad": _metin(x.get("ad"), 30), "hex": x["hex"], "rol": _metin(x.get("rol"), 60)})
    out["ek_renkler"] = ek
    yt = k.get("yazi_tipleri") or {}
    out["yazi_tipleri"] = {a: (str(yt.get(a) or "") if FONT_RE.match(str(yt.get(a) or "")) else "") for a in ("baslik", "govde")}
    for bol, vs in (("intro", 2.5), ("outro", 3.5)):
        b = k.get(bol) or {}
        out[bol] = {"acik": bool(b.get("acik")), "sure": max(1.0, min(8.0, float(b.get("sure") or vs)))}
    f = k.get("filigran") or {}
    out["filigran"] = {"acik": bool(f.get("acik")), "konum": f.get("konum") if f.get("konum") in KONUMLAR else "sag-alt",
                       "opaklik": max(0.1, min(1.0, float(f.get("opaklik") or 0.6))), "boyut": max(0.03, min(0.3, float(f.get("boyut") or 0.09)))}
    out["kapak_filigran"] = bool(k.get("kapak_filigran"))
    # logolar: dosya yalnızca kayıtlı olandan gelir
    kayitli = {x["id"]: x for x in (eski.get("logolar") or []) if isinstance(x, dict) and x.get("id")}
    logolar = []
    for x in _benzersiz([dict(y) for y in (k.get("logolar") or []) if isinstance(y, dict)], "logo"):
        e = kayitli.get(x["id"])
        if not e:
            continue   # dosyası olmayan logo kaydı oluşmaz: önce yükle
        logolar.append({"id": x["id"], "ad": _metin(x.get("ad") or e.get("ad"), 40), "tur": x.get("tur") if x.get("tur") in LOGO_TURLERI else e.get("tur", "diger"), "dosya": e["dosya"]})
    out["logolar"] = logolar
    out["metinler"] = [{"id": x["id"], "ad": _metin(x.get("ad"), 40), "tur": x.get("tur") if x.get("tur") in METIN_TURLERI else "diger", "icerik": _metin(x.get("icerik"), 600)}
                       for x in _benzersiz([dict(y) for y in (k.get("metinler") or []) if isinstance(y, dict)], "metin")]
    kul = []
    for x in _benzersiz([dict(y) for y in (k.get("kullanim") or []) if isinstance(y, dict)], "kural"):
        oge = str(x.get("oge") or "genel")
        kul.append({"id": x["id"], "oge": oge if OGE_RE.match(oge) else "genel", "konum": _metin(x.get("konum"), 80), "ne_zaman": _metin(x.get("ne_zaman"), 200),
                    "nasil": _metin(x.get("nasil"), 500), "yasak": _metin(x.get("yasak"), 300), "acik": x.get("acik") is not False})
    out["kullanim"] = kul
    out["notlar"] = _metin(k.get("notlar"), 1500)
    return out


def kaydet(k: dict) -> dict:
    if not k.get("id"):
        k["id"] = slug(k.get("ad") or k.get("isim") or "kit")
    d = kit_klasoru(k["id"])
    eski = json.loads((d / "kit.json").read_text(encoding="utf-8")) if d.joinpath("kit.json").is_file() else {}
    temiz = dogrula(k, eski)
    if eski:  # mevcut logoyu koru (panel formu logo alanını göndermeyebilir)
        if not temiz["logo"] and eski.get("logo") and "logo" not in k:
            temiz["logo"] = eski["logo"]
        tut = {x["dosya"] for x in temiz["logolar"]} | ({temiz["logo"]} if temiz["logo"] else set())
        for x in eski.get("logolar") or []:   # panelden kaldırılan logoların dosyası da silinir
            if x["dosya"] not in tut and (d / x["dosya"]).is_file():
                (d / x["dosya"]).unlink()
    d.mkdir(parents=True, exist_ok=True)
    (d / "kit.json").write_text(json.dumps(temiz, ensure_ascii=False, indent=2), encoding="utf-8")
    return temiz


def _logo_kontrol(dosya_adi: str, veri: bytes) -> str:
    uz = Path(dosya_adi).suffix.lower()
    if uz not in LOGO_UZ:
        raise ValueError(f"logo biçimi {', '.join(LOGO_UZ)} olmalı")
    if not (100 <= len(veri) <= 5_000_000):
        raise ValueError("logo 5 MB'tan küçük olmalı")
    if uz == ".svg" and re.search(rb"<script|onload=|javascript:", veri, re.I):
        raise ValueError("SVG içinde betik var, kabul edilmedi")
    return uz


def logo_kaydet(kid: str, dosya_adi: str, veri: bytes) -> str:
    """Eski tek logo alanı (sahne kodunun okuduğu `logo`); aynı zamanda 'ana' logo olarak logolar listesine de işlenir."""
    uz = _logo_kontrol(dosya_adi, veri)
    k = oku(kid)
    d = kit_klasoru(kid)
    ad = f"logo{uz}"
    for eski in d.glob("logo.*"):
        eski.unlink()
    (d / ad).write_bytes(veri)
    k["logo"] = ad
    k.setdefault("logolar", [])
    if not any(x["id"] == "ana" for x in k["logolar"]):
        k["logolar"].append({"id": "ana", "ad": "Ana logo", "tur": "ana", "dosya": ad})
    else:
        next(x for x in k["logolar"] if x["id"] == "ana")["dosya"] = ad
    (d / "kit.json").write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8")
    return ad


def logo_ekle(kid: str, lid: str, dosya_adi: str, veri: bytes, ad: str = "", tur: str = "diger") -> dict:
    """Kite adlandırılmış bir logo ekler/yeniler (ana, simge, yatay, koyu/açık zemin…). Dosya kit klasörüne `logo-<id>.<uzantı>` olarak yazılır."""
    uz = _logo_kontrol(dosya_adi, veri)
    k = oku(kid)
    d = kit_klasoru(kid)
    lid = _id(lid or Path(dosya_adi).stem, "logo")
    if len(k.get("logolar") or []) >= 12 and not any(x["id"] == lid for x in k.get("logolar") or []):
        raise ValueError("bir kitte en çok 12 logo olur")
    dosya = f"logo-{lid}{uz}"
    for eski in d.glob(f"logo-{lid}.*"):
        eski.unlink()
    (d / dosya).write_bytes(veri)
    k.setdefault("logolar", [])
    kayit = next((x for x in k["logolar"] if x["id"] == lid), None)
    if kayit is None:
        kayit = {"id": lid, "ad": "", "tur": "diger", "dosya": dosya}
        k["logolar"].append(kayit)
    kayit.update(dosya=dosya, ad=_metin(ad or kayit.get("ad") or lid, 40), tur=tur if tur in LOGO_TURLERI else kayit.get("tur", "diger"))
    if kayit["tur"] == "ana" or not k.get("logo"):
        k["logo"] = dosya
    (d / "kit.json").write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8")
    return kayit


def sil(kid: str) -> None:
    if kid == "varsayilan":
        raise ValueError("varsayılan kit silinemez")
    d = kit_klasoru(kid)
    if d.is_dir():
        shutil.rmtree(d)


def kullanim_md(k: dict, secim: dict | None = None) -> str:
    """Ajanların (senarist, sahne yapımcısı, kapak/sosyal) okuyacağı marka kullanım kılavuzu: kitin ne olduğu + KULLANICININ yazdığı yerleşim ve kullanım kuralları."""
    s = secim or {}
    sat = [f"# Marka kullanım kılavuzu: {k.get('ad', '')}", "",
           "Bu kılavuz kullanıcının kararıdır: her sahnede ve her çıktıda uygula; kuralla çelişen bir tasarım gerekiyorsa uygulamadan önce kullanıcıya sor. "
           "Logo ve renk gibi kimlik öğelerini yeniden çizme, bozma ya da yapay zekâyla üretme.", "", "## Kimlik"]
    for a, e in (("İsim", k.get("isim")), ("Slogan", k.get("slogan")), ("İmza cümle (outro)", k.get("imza_cumle"))):
        sat.append(f"- {a}: {e or '(yok)'}")
    il = {a: v for a, v in (k.get("iletisim") or {}).items() if v}
    sat.append("- İletişim: " + (", ".join(f"{a}: {v}" for a, v in il.items()) if il else "(yok)") + ("" if s.get("iletisim") else "  [bu projede iletişim bilgisi GÖRÜNMEZ]"))
    sat += ["", "## Logolar (dosyalar: media/marka/)"]
    if k.get("logolar"):
        sat += [f"- `{x['id']}` ({x['tur']}): {x['ad']} → {x['dosya']}" for x in k["logolar"]]
    else:
        sat.append(f"- {k['logo']}" if k.get("logo") else "- (logo yok)")
    if k.get("metinler"):
        sat += ["", "## Metinler"] + [f"- `{x['id']}` ({x['tur']}) {x['ad']}: {x['icerik']}" for x in k["metinler"]]
    r = k.get("renkler") or {}
    sat += ["", "## Renkler ve yazı tipleri", f"- Zemin {r.get('zemin')} · Metin {r.get('metin')} · Vurgu {r.get('vurgu')}"]
    sat += [f"- {x['ad'] or x['hex']} {x['hex']}" + (f": {x['rol']}" if x.get("rol") else "") for x in k.get("ek_renkler") or []]
    yt = k.get("yazi_tipleri") or {}
    if yt.get("baslik") or yt.get("govde"):
        sat.append(f"- Yazı tipi: başlık `{yt.get('baslik') or '-'}`, gövde `{yt.get('govde') or '-'}` (list_fonts ile doğrula)")
    for ad, anahtar in (("Intro", "intro"), ("Outro", "outro"), ("Filigran", "filigran")):
        acik = (s.get(anahtar) if anahtar in s else (k.get(anahtar) or {}).get("acik"))
        sat.append(f"- {ad}: bu projede {'AÇIK' if acik else 'KAPALI'}")
    sat += ["", "## Kullanım kuralları (nerede, ne zaman, nasıl)"]
    kurallar = [x for x in k.get("kullanim") or [] if x.get("acik", True)]
    if not kurallar:
        sat.append("- (kullanıcı özel kural yazmamış: yukarıdaki kimlik öğelerini ölçülü, tutarlı kullan)")
    for x in kurallar:
        parca = [f"Nerede: {x['konum']}" if x.get("konum") else "", f"Ne zaman: {x['ne_zaman']}" if x.get("ne_zaman") else "", f"Nasıl: {x['nasil']}" if x.get("nasil") else "",
                 f"YASAK: {x['yasak']}" if x.get("yasak") else ""]
        sat.append(f"- **{x['oge']}** — " + " · ".join(p for p in parca if p))
    if k.get("notlar"):
        sat += ["", "## Genel notlar", k["notlar"]]
    return "\n".join(sat) + "\n"


def coz(kid: str, secim: dict | None = None) -> dict:
    """Kit + bu projedeki açma/kapama seçimi → sahne kodunun okuyacağı birleşik marka verisi."""
    k = oku(kid)
    s = secim or {}
    out = json.loads(json.dumps(k))
    out["kit"] = kid
    for bol, anahtar in (("intro", "intro"), ("outro", "outro"), ("filigran", "filigran")):
        if anahtar in s:
            out[bol]["acik"] = bool(s[anahtar])
    out["iletisim_goster"] = bool(s.get("iletisim", False))
    out["kapak_filigran"] = bool(s.get("kapak_filigran", k.get("kapak_filigran", False)))
    return out


def uygula(proje: str, kid: str | None = None, secim: dict | None = None) -> list[str]:
    """Projedeki her biçim klasörüne marka verisini ve tüm logoları yaz; projeye `marka_kullanimi.md` (ajan kılavuzu) bırak. Döndürür: dokunulan biçimler."""
    pk = ROOT / "projeler" / proje
    if not pk.is_dir():
        raise ValueError("proje yok")
    sec = dict(secim or {})
    kid = kid or sec.pop("kit", None) or "varsayilan"
    m = coz(kid, sec)
    dokunulan = []
    dosyalar = {x["dosya"] for x in m.get("logolar") or []} | ({m["logo"]} if m.get("logo") else set())
    for f in ("ana", "reels", "tiktok", "shorts", "story"):
        fk = pk / f
        if not (fk / "project.json").is_file():
            continue
        (fk / "remotion" / "src").mkdir(parents=True, exist_ok=True)
        (fk / "media" / "marka").mkdir(parents=True, exist_ok=True)
        for dosya in dosyalar:
            if (kit_klasoru(kid) / dosya).is_file():
                shutil.copy2(kit_klasoru(kid) / dosya, fk / "media" / "marka" / dosya)
        (fk / "remotion" / "src" / "marka.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        dokunulan.append(f)
    (pk / "marka_secimi.json").write_text(json.dumps({"kit": kid, **{k: v for k, v in sec.items()}}, ensure_ascii=False, indent=2), encoding="utf-8")
    (pk / "marka_kullanimi.md").write_text(kullanim_md(m, sec), encoding="utf-8")
    return dokunulan


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        if a[0] == "liste":
            for k in liste():
                print(f"{k['id']:20} {k['ad']}  [{k['isim']}]  logo:{'var' if k['logo'] else 'yok'}  iletişim:{'var' if k['iletisim_var'] else 'boş'}")
        elif a[0] == "goster":
            print(json.dumps(oku(a[1]), ensure_ascii=False, indent=2))
        elif a[0] == "uygula":
            kw = {a[i].lstrip("-"): a[i + 1] for i in range(2, len(a) - 1, 2)}
            sec = {k: kw[k] == "1" for k in ("intro", "outro", "filigran", "iletisim") if k in kw}
            d = uygula(a[1], kw.get("kit"), sec)
            print("marka uygulandı:", ", ".join(d) or "(henüz biçim klasörü yok)")
        else:
            print(__doc__)
            return 2
    except ValueError as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
