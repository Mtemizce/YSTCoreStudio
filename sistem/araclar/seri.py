#!/usr/bin/env python3
"""Seri / sezon / bölüm: dizi, kısa film, kurumsal seri. Seri kitabı (karakterler, stil, ton, **model seti**, sezonlar, bölümler, süreklilik) tek yerde durur;
her bölüm normal bir proje olarak açılır; senarist ve sahne ajanları önceki bölümlerin özetini, karakterleri ve **bölümde görünen model görsellerini** bağlam olarak alır.

Model seti = dizinin "proje kiti": karakter, nesne ve mekânların sabit görselleri (görsel kütüphanesinden onaylı görseller) ve sabit istem eki. Her bölümde hangi modellerin
göründüğü bölümde işaretlenir; o bölümün projesine görseller ve tarif kopyalanır (projeler/<proje>/kaynak/foto/model-*.png ve seri_model_seti.md).

  python sistem/araclar/seri.py liste
  python sistem/araclar/seri.py olustur <ad> [--tur dizi|kisa-film|kurumsal] [--aciklama "…"] [--karakter id,…] [--stil "…"] [--gorsel-stil anime-aksiyon]
  python sistem/araclar/seri.py bolum <seri> <sezon> "<bölüm adı>" [--ozet "…"] [--senaryo "…"] [--gorunenler m1,m2]
  python sistem/araclar/seri.py duzenle <seri> <sezon> <bolum> [--ad "…"] [--ozet "…"] [--senaryo "…"] [--gorunenler m1,m2] [--durum planlandi|proje-acildi|bitti]
  python sistem/araclar/seri.py model <seri> <tur karakter|nesne|mekan> "<ad>" [--aciklama "…"] [--istem-eki "…"]
  python sistem/araclar/seri.py model-gorsel <seri> <model-id> <görsel-id> [--ana]
  python sistem/araclar/seri.py ozet <seri> <sezon> <bolum> "<bitmiş bölümün özeti>"   süreklilik: sonraki bölüm bunu okur
  python sistem/araclar/seri.py baglam <seri> <sezon> <bolum>                        ajan bağlamı (projeler/<proje>/seri_baglami.md'ye de yazılır)

Konum: kimlik/seriler/<ad>/seri.json (kullanıcı verisi: git'e girmez, profil dışa aktarmaya girer). Karakter (kişi/ses) paketleri: sistem/araclar/karakter.py. Görseller: gorsel_kutuphane.py.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOK = ROOT / "kimlik" / "seriler"
TURLER = ("dizi", "kisa-film", "kurumsal")
MODEL_TURLERI = ("karakter", "nesne", "mekan")
DURUMLAR = ("planlandi", "proje-acildi", "bitti")
sys.path.insert(0, str(ROOT / "sistem" / "araclar"))


def slug(ad: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = re.sub(r"[^a-z0-9]+", "-", str(ad).translate(tr).lower()).strip("-")[:40]
    if not s:
        raise ValueError("ad gerekli")
    return s


def _yol(s: str) -> Path:
    return KOK / slug(s) / "seri.json"


def oku(s: str) -> dict:
    p = _yol(s)
    if not p.is_file():
        raise ValueError(f"seri yok: {s}")
    k = json.loads(p.read_text(encoding="utf-8"))
    k.setdefault("gorsel_stil", "")
    k.setdefault("model_seti", [])
    for z in k.get("sezonlar", []):
        for b in z.get("bolumler", []):
            b.setdefault("senaryo", "")
            b.setdefault("gorunenler", [])
    return k


def _yaz(k: dict) -> None:
    p = _yol(k["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    tmp.write_text(json.dumps(k, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def _gorsel_stil_kontrol(stil: str) -> str:
    stil = str(stil or "")
    if stil:
        import gorsel_kutuphane
        if stil not in gorsel_kutuphane.STIL:
            raise ValueError("bilinmeyen görsel stil")
    return stil


def olustur(ad: str, tur: str = "dizi", aciklama: str = "", karakterler: list[str] | None = None, stil: str = "", gorsel_stil: str = "") -> dict:
    if tur not in TURLER:
        raise ValueError(f"tür {TURLER} olmalı")
    s = slug(ad)
    if _yol(s).exists():
        raise ValueError(f"'{s}' serisi zaten var")
    if karakterler:
        import karakter
        for c in karakterler:
            karakter.oku(c)  # yoksa ValueError
    k = {"surum": 2, "id": s, "ad": ad.strip()[:80], "tur": tur, "aciklama": aciklama[:1500], "karakterler": karakterler or [], "stil": stil[:1500],
         "gorsel_stil": _gorsel_stil_kontrol(gorsel_stil), "model_seti": [], "olusturma": time.strftime("%Y-%m-%d"), "sezonlar": []}
    _yaz(k)
    return k


def guncelle(seri: str, ad: str | None = None, aciklama: str | None = None, stil: str | None = None, gorsel_stil: str | None = None, karakterler: list[str] | None = None) -> dict:
    """Seri bilgisini düzenler (kimlik, bölümler ve model seti korunur)."""
    k = oku(seri)
    if ad is not None:
        k["ad"] = ad.strip()[:80] or k["ad"]
    if aciklama is not None:
        k["aciklama"] = aciklama[:1500]
    if stil is not None:
        k["stil"] = stil[:1500]
    if gorsel_stil is not None:
        k["gorsel_stil"] = _gorsel_stil_kontrol(gorsel_stil)
    if karakterler is not None:
        import karakter
        for c in karakterler:
            karakter.oku(c)
        k["karakterler"] = karakterler
    _yaz(k)
    return k


def liste() -> list[dict]:
    out = []
    if KOK.is_dir():
        for p in sorted(KOK.glob("*/seri.json")):
            try:
                k = oku(p.parent.name)
                out.append({"id": k["id"], "ad": k["ad"], "tur": k["tur"], "karakterler": k["karakterler"], "gorsel_stil": k["gorsel_stil"], "model": len(k["model_seti"]),
                            "sezon": len(k["sezonlar"]), "bolum": sum(len(z["bolumler"]) for z in k["sezonlar"])})
            except (OSError, ValueError, KeyError):
                pass
    return out


def bolumler(seri: str) -> list[dict]:
    """Tüm bölümler düz liste: {sezon, no, ad, proje, durum, ...}"""
    k = oku(seri)
    return [{"sezon": z["no"], **b} for z in k["sezonlar"] for b in z["bolumler"]]


def proje_adi(seri: str, sezon: int, bolum: int) -> str:
    return f"{slug(seri)}-s{int(sezon):02d}b{int(bolum):02d}"[:60]


# ------------------------------------------------------------------ model seti (proje kiti)
def _model(k: dict, mid: str) -> dict:
    m = next((x for x in k["model_seti"] if x["id"] == mid), None)
    if not m:
        raise ValueError(f"model yok: {mid}")
    return m


def _gorsel_bagla(m: dict, gid: str, ana: bool = False) -> None:
    import gorsel_kutuphane as G
    o = G.al(gid)
    if o["durum"] != "onayli":
        raise ValueError("yalnızca onaylı (kütüphaneye eklenmiş) görsel modele bağlanır: önce görseli beğenip onayla")
    if gid not in m["gorseller"]:
        m["gorseller"].append(gid)
    if ana or not m["ana"]:
        m["ana"] = gid


def model_ekle(seri: str, tur: str, ad: str, aciklama: str = "", istem_eki: str = "", gorseller: list[str] | None = None) -> dict:
    """Karakter/nesne/mekân ekler. aciklama: görünüş tarifi (insan okur); istem_eki: görsel üretirken sabit eklenen İngilizce tarif (kıyafet, saç, renk…)."""
    if tur not in MODEL_TURLERI:
        raise ValueError(f"tür {MODEL_TURLERI} olmalı")
    k = oku(seri)
    mid = slug(ad)
    if any(x["id"] == mid for x in k["model_seti"]):
        raise ValueError(f"'{mid}' modeli zaten var")
    m = {"id": mid, "tur": tur, "ad": ad.strip()[:60], "aciklama": aciklama[:800], "istem_eki": istem_eki[:600], "gorseller": [], "ana": ""}
    for g in gorseller or []:
        _gorsel_bagla(m, g, ana=not m["ana"])
    k["model_seti"].append(m)
    _yaz(k)
    return m


def model_gorsel(seri: str, mid: str, gid: str, ana: bool = False, kaldir: bool = False) -> dict:
    k = oku(seri)
    m = _model(k, mid)
    if kaldir:
        m["gorseller"] = [g for g in m["gorseller"] if g != gid]
        if m["ana"] == gid:
            m["ana"] = m["gorseller"][0] if m["gorseller"] else ""
    else:
        _gorsel_bagla(m, gid, ana)
    _yaz(k)
    return m


def model_guncelle(seri: str, mid: str, ad: str | None = None, aciklama: str | None = None, istem_eki: str | None = None) -> dict:
    k = oku(seri)
    m = _model(k, mid)
    if ad is not None:
        m["ad"] = ad.strip()[:60] or m["ad"]
    if aciklama is not None:
        m["aciklama"] = aciklama[:800]
    if istem_eki is not None:
        m["istem_eki"] = istem_eki[:600]
    _yaz(k)
    return m


def model_sil(seri: str, mid: str) -> None:
    k = oku(seri)
    _model(k, mid)
    k["model_seti"] = [x for x in k["model_seti"] if x["id"] != mid]
    for z in k["sezonlar"]:
        for b in z["bolumler"]:
            b["gorunenler"] = [g for g in b.get("gorunenler", []) if g != mid]
    _yaz(k)


def model_istemi(seri: str, mid: str, istem: str) -> tuple[str, str | None]:
    """Modelin sabit istem ekiyle birleştirilmiş istem ve serinin görsel stili (görsel üretiminde kullanılır)."""
    k = oku(seri)
    m = _model(k, mid)
    eki = ", ".join(x for x in (str(istem).strip(), m["istem_eki"].strip()) if x)
    return eki, (k.get("gorsel_stil") or None)


# ------------------------------------------------------------------ bölümler
def _bolum(k: dict, sezon: int, bolum: int) -> tuple[dict, dict]:
    for z in k["sezonlar"]:
        for b in z["bolumler"]:
            if z["no"] == int(sezon) and b["no"] == int(bolum):
                return z, b
    raise ValueError("bölüm yok")


def _gorunen_kontrol(k: dict, ids: list[str]) -> list[str]:
    var = {m["id"] for m in k["model_seti"]}
    out = []
    for i in ids:
        i = str(i).strip()
        if i not in var:
            raise ValueError(f"model seti'nde yok: {i}")
        if i not in out:
            out.append(i)
    return out


def _proje_dosyalari(k: dict, sezon: int, b: dict) -> None:
    """Bölüm projesi varsa: senaryoyu kaynak/belge/senaryo.md'ye yazar, bölümde görünen modellerin görsellerini kaynak/foto/ altına kopyalar ve seri_model_seti.md'yi yazar."""
    pr = ROOT / "projeler" / b["proje"]
    if not pr.is_dir():
        return
    if b.get("senaryo"):
        (pr / "kaynak" / "belge").mkdir(parents=True, exist_ok=True)
        (pr / "kaynak" / "belge" / "senaryo.md").write_text(f"# Senaryo: {k['ad']} S{sezon:02d}B{b['no']:02d} {b['ad']}\n\n{b['senaryo']}\n", encoding="utf-8")
    sat = [f"# Model seti: {k['ad']} S{sezon:02d}B{b['no']:02d}", "",
           "Bu bölümde görünen karakter/nesne/mekânlar. **Görselleri değiştirme ve bu tariflerle tutarlı çiz/üret**: onaylı görseller `kaynak/foto/model-*.png` olarak projededir. "
           "Yeni görsel üretirken `istem eki`ni her seferinde aynen ekle (`python sistem/araclar/gorsel_kutuphane.py uret ...`).", ""]
    if not b.get("gorunenler"):
        sat.append("- (bu bölüm için model işaretlenmemiş)")
    import gorsel_kutuphane as G
    for mid in b.get("gorunenler", []):
        m = next((x for x in k["model_seti"] if x["id"] == mid), None)
        if not m:
            continue
        dosyalar = []
        for gid in m["gorseller"]:
            try:
                src = G.yol(gid)
            except ValueError:
                continue
            ad = f"model-{mid}-{gid}.png"
            (pr / "kaynak" / "foto").mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, pr / "kaynak" / "foto" / ad)
            dosyalar.append(ad + (" (ana görsel)" if gid == m["ana"] else ""))
        sat += [f"## {m['ad']} ({m['tur']})", f"- Görünüş: {m['aciklama'] or '(tarif yok)'}", f"- Sabit istem eki: `{m['istem_eki'] or '-'}`",
                f"- Görseller: {', '.join(dosyalar) if dosyalar else '(henüz görsel eklenmemiş: önce üretip onaylat)'}", ""]
    (pr / "seri_model_seti.md").write_text("\n".join(sat) + "\n", encoding="utf-8")


def bolum_ekle(seri: str, sezon: int, ad: str, ozet: str = "", proje_ac: bool = True, senaryo: str = "", gorunenler: list[str] | None = None) -> dict:
    k = oku(seri)
    sezon = int(sezon)
    if not 1 <= sezon <= 50:
        raise ValueError("sezon 1-50 olmalı")
    gorunenler = _gorunen_kontrol(k, gorunenler or [])
    z = next((x for x in k["sezonlar"] if x["no"] == sezon), None)
    if z is None:
        z = {"no": sezon, "bolumler": []}
        k["sezonlar"].append(z)
        k["sezonlar"].sort(key=lambda x: x["no"])
    no = max([b["no"] for b in z["bolumler"]] or [0]) + 1
    proje = proje_adi(k["id"], sezon, no)
    b = {"no": no, "ad": ad.strip()[:120], "proje": proje, "ozet_plan": ozet[:1500], "ozet_biten": "", "durum": "planlandi", "senaryo": senaryo[:20000], "gorunenler": gorunenler}
    if proje_ac:
        tarif = f"{k['ad']} ({k['tur']}) sezon {sezon} bölüm {no}: {ad}. {ozet}".strip()[:3800]
        r = subprocess.run([sys.executable, str(ROOT / "sistem" / "araclar" / "yeni_proje.py"), proje, "--tarif", tarif, "--format", "ana"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        if r.returncode != 0:
            raise RuntimeError("proje açılamadı: " + (r.stdout + r.stderr)[-300:])
        up = ROOT / "projeler" / proje / "uretim.json"
        u = json.loads(up.read_text(encoding="utf-8")) if up.is_file() else {}
        u["seri"] = {"id": k["id"], "ad": k["ad"], "sezon": sezon, "bolum": no, "bolum_adi": ad, "gorsel_stil": k.get("gorsel_stil", "")}
        up.write_text(json.dumps(u, ensure_ascii=False, indent=2), encoding="utf-8")
        b["durum"] = "proje-acildi"
    z["bolumler"].append(b)
    _yaz(k)
    _proje_dosyalari(k, sezon, b)
    if proje_ac:
        baglam(k["id"], sezon, no)
    return b


def bolum_guncelle(seri: str, sezon: int, bolum: int, ad: str | None = None, ozet: str | None = None, senaryo: str | None = None, gorunenler: list[str] | None = None,
                   durum: str | None = None) -> dict:
    """Mevcut bölümü düzenler; proje açıksa senaryo ve model görselleri projeye de işlenir, bağlam dosyası yenilenir."""
    k = oku(seri)
    z, b = _bolum(k, sezon, bolum)
    if ad is not None:
        b["ad"] = ad.strip()[:120] or b["ad"]
    if ozet is not None:
        b["ozet_plan"] = ozet[:1500]
    if senaryo is not None:
        b["senaryo"] = senaryo[:20000]
    if gorunenler is not None:
        b["gorunenler"] = _gorunen_kontrol(k, gorunenler)
    if durum is not None:
        if durum not in DURUMLAR:
            raise ValueError(f"durum {DURUMLAR} olmalı")
        b["durum"] = durum
    _yaz(k)
    _proje_dosyalari(k, int(sezon), b)
    baglam(k["id"], sezon, bolum)
    return b


def ozet_yaz(seri: str, sezon: int, bolum: int, ozet: str) -> dict:
    k = oku(seri)
    _, b = _bolum(k, sezon, bolum)
    b["ozet_biten"], b["durum"] = ozet[:3000], "bitti"
    _yaz(k)
    return b


def baglam(seri: str, sezon: int, bolum: int) -> str:
    """Senarist/ajan bağlamı: seri kitabı + görsel stil + karakterler + bölümde görünen model seti + önceki bölüm özetleri (bitmişse biten özet, değilse plan)."""
    k = oku(seri)
    sat = [f"# Seri bağlamı: {k['ad']} ({k['tur']})", "", f"Şimdi yazılacak: sezon {int(sezon)}, bölüm {int(bolum)}", "", "## Seri hakkında", k["aciklama"] or "(açıklama yok)", "",
           "## Stil / ton", k["stil"] or "(belirtilmemiş: kimlik/zevk.md ve MARKA.md geçerli)"]
    if k.get("gorsel_stil"):
        import gorsel_kutuphane as G
        s = G.STIL.get(k["gorsel_stil"])
        if s:
            sat += ["", "## Görsel stil (serinin tamamında aynı)", f"- {s['ad']}: {s['aciklama']}", f"- Görsel üretirken istemin sonuna: `{s['ek']}`"]
    sat += ["", "## Karakterler (kişi/ses paketi)"]
    if k["karakterler"]:
        import karakter
        for c in k["karakterler"]:
            try:
                kk = karakter.oku(c)
                sat.append(f"- **{kk['ad']}** (kimlik/karakterler/{kk['id']}/: boy.jpg, portre.jpg; ses: {kk.get('ses', {}).get('kaynak', 'ema')})")
            except ValueError:
                sat.append(f"- {c} (karakter dosyası bulunamadı)")
    else:
        sat.append("- (tanımlı karakter yok)")
    sat += ["", "## Model seti (sabit görsel kimlik)"]
    try:
        _, bu = _bolum(k, sezon, bolum)
        gor = bu.get("gorunenler", [])
    except ValueError:
        bu, gor = {}, []
    if not k["model_seti"]:
        sat.append("- (model seti boş)")
    for m in k["model_seti"]:
        isaret = "BU BÖLÜMDE GÖRÜNÜR" if m["id"] in gor else "bu bölümde görünmez"
        sat.append(f"- **{m['ad']}** ({m['tur']}; {isaret}): {m['aciklama'] or '-'} | sabit istem eki: `{m['istem_eki'] or '-'}` | {len(m['gorseller'])} görsel")
    if bu.get("senaryo"):
        sat += ["", "## Bu bölümün senaryosu (kullanıcı verdi; temel al)", bu["senaryo"]]
    sat += ["", "## Önceki bölümler (süreklilik: bunlarla çelişme)"]
    onceki = [(z["no"], b) for z in k["sezonlar"] for b in z["bolumler"] if (z["no"], b["no"]) < (int(sezon), int(bolum))]
    if not onceki:
        sat.append("- (ilk bölüm)")
    for zn, b in onceki:
        sat.append(f"- S{zn:02d}B{b['no']:02d} {b['ad']}: {b['ozet_biten'] or b['ozet_plan'] or '(özet yok)'}" + ("" if b["ozet_biten"] else "  [PLAN; henüz üretilmedi]"))
    sat += ["", "Kural: bu bağlamda olmayan olay/kişi uydurma; model setindeki görselleri ve tarifleri değiştirme; çelişki görürsen kullanıcıya sor."]
    metin = "\n".join(sat) + "\n"
    pr = ROOT / "projeler" / proje_adi(seri, sezon, bolum)
    if pr.is_dir():
        (pr / "seri_baglami.md").write_text(metin, encoding="utf-8")
    return metin


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    g = lambda n, v="": a[a.index(n) + 1] if n in a else v  # noqa: E731
    liste_ = lambda n: [x for x in g(n).split(",") if x]  # noqa: E731
    try:
        if not a or a[0] == "liste":
            for s in liste():
                print(f"{s['id']:24} {s['tur']:10} {s['sezon']} sezon, {s['bolum']} bölüm, {s['model']} model  görsel stil: {s['gorsel_stil'] or '-'}  karakterler: {', '.join(s['karakterler']) or '-'}")
        elif a[0] == "olustur":
            print(json.dumps(olustur(a[1], g("--tur", "dizi"), g("--aciklama"), liste_("--karakter"), g("--stil"), g("--gorsel-stil")), ensure_ascii=False))
        elif a[0] == "bolum":
            print(json.dumps(bolum_ekle(a[1], int(a[2]), a[3], g("--ozet"), True, g("--senaryo"), liste_("--gorunenler")), ensure_ascii=False))
        elif a[0] == "duzenle":
            alan = {"ad": g("--ad") or None, "ozet": g("--ozet") or None, "senaryo": g("--senaryo") or None, "durum": g("--durum") or None,
                    "gorunenler": liste_("--gorunenler") if "--gorunenler" in a else None}
            print(json.dumps(bolum_guncelle(a[1], int(a[2]), int(a[3]), **alan), ensure_ascii=False))
        elif a[0] == "model":
            print(json.dumps(model_ekle(a[1], a[2], a[3], g("--aciklama"), g("--istem-eki")), ensure_ascii=False))
        elif a[0] == "model-gorsel":
            print(json.dumps(model_gorsel(a[1], a[2], a[3], "--ana" in a), ensure_ascii=False))
        elif a[0] == "ozet":
            print(json.dumps(ozet_yaz(a[1], int(a[2]), int(a[3]), a[4]), ensure_ascii=False))
        elif a[0] == "baglam":
            print(baglam(a[1], int(a[2]), int(a[3])))
        else:
            print(__doc__)
            return 2
    except (ValueError, RuntimeError, IndexError, OSError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
