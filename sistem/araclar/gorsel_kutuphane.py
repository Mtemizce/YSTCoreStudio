#!/usr/bin/env python3
"""Görsel kütüphanesi: yerel model (Z-Image-Turbo) ile görsel üret, kontrol et, beğenileni kütüphaneye (arşive) ekle, projelerde ve bölümlerde kaynak olarak kullan.

Akış: üret (taslak) → kalite ölçütleri + gözle kontrol → beğendiysen **onayla** (kütüphaneye ve arşive girer) · beğenmediysen **yeniden üret** (yeni tohum) ya da **reddet**.
Onaylanan görsel `kimlik/gorseller/onayli/` altındadır; bu klasör "Üretilen görseller" adıyla arşiv köküne eklenir: "arşivden bul" ve elle seçimde çıkar.

  python sistem/araclar/gorsel_kutuphane.py stiller
  python sistem/araclar/gorsel_kutuphane.py uret "<istem>" [--stil anime-aksiyon] [--genislik 1024 --yukseklik 576] [--adet 2] [--tohum N] [--seri ID --sezon 1 --bolum 2] [--bekle]
  python sistem/araclar/gorsel_kutuphane.py liste [--durum taslak|onayli|reddedildi] [--seri ID]
  python sistem/araclar/gorsel_kutuphane.py onayla|reddet|sil|yeniden <id>
  python sistem/araclar/gorsel_kutuphane.py projeye <id> <proje> [--format ana]     görseli projenin kaynak/foto ve Kurgu media klasörüne kopyalar
  python sistem/araclar/gorsel_kutuphane.py kalite <dosya>

Konum: kimlik/gorseller/ (kullanıcı verisi: git'e girmez). Model kurulu değilse üretim yapılmaz (panel → Ayarlar → Servisler ve modeller → Yerel görsel üretim).
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KOK = ROOT / "kimlik" / "gorseller"
TASLAK, ONAYLI = KOK / "taslak", KOK / "onayli"
INDEKS = KOK / "index.json"
ID_RE = re.compile(r"^g[0-9a-f]{10}$")
PROJE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
BOYUTLAR = {"yatay": (1024, 576), "dikey": (576, 1024), "kare": (768, 768), "genis": (1280, 512)}
EN_COK_ADET = 4
kilit = threading.RLock()
IS: dict = {"calisiyor": False, "toplam": 0, "tamam": 0, "hata": None, "idler": [], "mesaj": ""}

# Stil ön ayarları: istemin sonuna eklenir. Marka/sanatçı adı yok; yalnızca görsel özellik tarifleri.
STILLER = [
    {"id": "sinematik", "grup": "genel", "ad": "Sinematik", "aciklama": "Film karesi: sığ alan derinliği, yumuşak ışık, hafif gren", "renk": ["#1b2735", "#c9a24d"],
     "ek": "cinematic film still, shallow depth of field, soft natural light, subtle film grain, high detail"},
    {"id": "fotogercekci", "grup": "genel", "ad": "Fotogerçekçi", "aciklama": "Gerçek fotoğraf gibi, doğal renk ve ışık", "renk": ["#3a4a3f", "#d8d2c0"],
     "ek": "photorealistic photograph, natural colors, sharp focus, realistic lighting, high resolution"},
    {"id": "mimari-gorsel", "grup": "genel", "ad": "Mimari görselleştirme", "aciklama": "Temiz, gün ışıklı iç/dış mekân sunumu", "renk": ["#e6e2d8", "#7d8a96"],
     "ek": "architectural visualization, clean composition, daylight, realistic materials, wide angle, professional render"},
    {"id": "sulu-boya", "grup": "genel", "ad": "Sulu boya", "aciklama": "Akışkan lekeler, kâğıt dokusu", "renk": ["#bcd4e6", "#f2c9c9"],
     "ek": "watercolor painting, soft washes, visible paper texture, gentle color bleeding"},
    {"id": "kara-kalem", "grup": "genel", "ad": "Kara kalem", "aciklama": "Grafit eskiz, tarama çizgileri", "renk": ["#efebe0", "#333333"],
     "ek": "graphite pencil sketch, cross hatching, detailed linework, paper texture, monochrome"},
    {"id": "duz-illustrasyon", "grup": "genel", "ad": "Düz illüstrasyon", "aciklama": "Sade vektör şekiller, sınırlı palet", "renk": ["#ffd166", "#118ab2"],
     "ek": "flat vector illustration, simple shapes, limited color palette, clean edges"},
    {"id": "anime-aksiyon", "grup": "anime", "ad": "Anime: aksiyon", "aciklama": "Kalın çizgi, hız çizgileri, canlı renkler, dinamik kadraj", "renk": ["#ff4d4d", "#2b2d42"],
     "ek": "anime style, dynamic action pose, bold line art, speed lines, vivid saturated colors, dramatic angle, cel shading"},
    {"id": "anime-duygusal", "grup": "anime", "ad": "Anime: duygusal", "aciklama": "Pastel renkler, iri ifadeli gözler, yumuşak parlama", "renk": ["#ffc8dd", "#a2d2ff"],
     "ek": "anime style, soft pastel colors, large expressive eyes, gentle glow, sparkles, delicate line art, romantic mood"},
    {"id": "anime-retro-90", "grup": "anime", "ad": "Anime: 90'lar retro", "aciklama": "Eski hücre animasyonu, sönük palet, film grenli", "renk": ["#c9b79c", "#5f6f52"],
     "ek": "1990s retro anime style, hand painted cel animation look, muted palette, film grain, slight halation"},
    {"id": "anime-karanlik", "grup": "anime", "ad": "Anime: karanlık", "aciklama": "Yüksek kontrast, gölgeli, olgun ton", "renk": ["#0d1b2a", "#8d0801"],
     "ek": "dark anime style, high contrast, deep shadows, moody lighting, detailed line art, mature tone"},
    {"id": "anime-fantastik", "grup": "anime", "ad": "Anime: fantastik macera", "aciklama": "Boyama arka planlar, geniş manzara", "renk": ["#3a86ff", "#8338ec"],
     "ek": "anime fantasy adventure style, painterly detailed background, epic landscape, vibrant sky, cel shaded characters"},
    {"id": "anime-bilimkurgu", "grup": "anime", "ad": "Anime: bilim kurgu", "aciklama": "Neon ışıklar, fütüristik şehir", "renk": ["#00f5d4", "#7209b7"],
     "ek": "anime cyberpunk style, neon lights, futuristic city, rain reflections, sharp line art, cinematic composition"},
    {"id": "anime-gunluk", "grup": "anime", "ad": "Anime: günlük yaşam", "aciklama": "Sıcak ışık, sakin sahneler, ayrıntılı mekân", "renk": ["#ffd6a5", "#fdffb6"],
     "ek": "anime slice of life style, warm afternoon light, calm everyday scene, detailed interior, soft shading"},
    {"id": "anime-chibi", "grup": "anime", "ad": "Anime: chibi", "aciklama": "Büyük kafalı sevimli karakterler", "renk": ["#ffafcc", "#bde0fe"],
     "ek": "chibi anime style, cute oversized head, tiny body, simple clean line art, bright pastel colors"},
]
STIL = {s["id"]: s for s in STILLER}


# ------------------------------------------------------------------ depo
def _oku() -> dict:
    try:
        d = json.loads(INDEKS.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("ogeler"), list) else {"surum": 1, "ogeler": []}
    except (OSError, ValueError):
        return {"surum": 1, "ogeler": []}


def _yaz(d: dict) -> None:
    KOK.mkdir(parents=True, exist_ok=True)
    tmp = INDEKS.with_suffix(".part")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(INDEKS)


def _yol(o: dict) -> Path:
    return (ONAYLI if o["durum"] == "onayli" else TASLAK) / o["dosya"]


def _kontrol_id(gid: str) -> str:
    if not ID_RE.match(str(gid or "")):
        raise ValueError("geçersiz görsel kimliği")
    return gid


def liste(durum: str | None = None, seri: str | None = None) -> list[dict]:
    with kilit:
        out = [dict(o) for o in _oku()["ogeler"]]
    if durum:
        out = [o for o in out if o["durum"] == durum]
    if seri:
        out = [o for o in out if (o.get("seri") or {}).get("id") == seri]
    return sorted(out, key=lambda o: o["tarih"], reverse=True)


def al(gid: str) -> dict:
    _kontrol_id(gid)
    for o in liste():
        if o["id"] == gid:
            return o
    raise ValueError("görsel yok")


def yol(gid: str) -> Path:
    p = _yol(al(gid))
    if not p.is_file():
        raise ValueError("görsel dosyası yok")
    return p


# ------------------------------------------------------------------ kalite
def kalite_olc(dosya) -> dict:
    """Basit, hızlı ölçütler (bilgi verir, engellemez): boşluk/düzlük, bulanıklık (Laplace varyansı), pozlama. durum: iyi | orta | zayif."""
    import numpy as np
    from PIL import Image
    im = Image.open(dosya).convert("L")
    im.thumbnail((640, 640))
    a = np.asarray(im, dtype="float32")
    ort, std = float(a.mean()), float(a.std())
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    keskin = float(lap.var())
    ipucu, puan = [], 0
    if std < 12:
        ipucu.append("neredeyse düz: model bir şey çizmemiş olabilir, yeniden üret")
        puan += 2
    if keskin < 25:
        ipucu.append("bulanık görünüyor: adım sayısını artır ya da yeniden üret")
        puan += 1
    if ort < 25:
        ipucu.append("çok karanlık")
        puan += 1
    elif ort > 235:
        ipucu.append("çok aydınlık, ayrıntı kaybı olabilir")
        puan += 1
    return {"durum": "iyi" if puan == 0 else ("orta" if puan == 1 else "zayif"), "ortalama": round(ort, 1), "kontrast": round(std, 1), "keskinlik": round(keskin, 1), "ipucu": ipucu}


# ------------------------------------------------------------------ üretim
def _uretici():
    """Gerçek üretici yerel_gorsel.uret; YST_GORSEL_SAHTE=1 yalnızca testler içindir (modeli kurmadan arayüzü ve akışı denemek için gradyan resim yazar)."""
    if os.environ.get("YST_GORSEL_SAHTE"):
        def sahte(istem, cikti, genislik=1024, yukseklik=576, tohum=None, adim=8, zaman=1800):
            from PIL import Image, ImageDraw
            r = random.Random(tohum or 0)
            im = Image.new("RGB", (genislik, yukseklik))
            d = ImageDraw.Draw(im)
            c1, c2 = [tuple(r.randint(30, 220) for _ in range(3)) for _ in range(2)]
            for y in range(yukseklik):
                t = y / max(1, yukseklik - 1)
                d.line([(0, y), (genislik, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
            for _ in range(14):
                x, y, w = r.randint(0, genislik), r.randint(0, yukseklik), r.randint(30, 160)
                d.ellipse([x, y, x + w, y + w], outline=(255, 255, 255), width=3)
            im.save(cikti)
            return {"dosya": str(cikti), "model": "sahte", "sn": 0.0, "yerel": True}
        return sahte
    import importlib.util
    sp = importlib.util.spec_from_file_location("yst_yerel_gorsel_k", ROOT / "sistem" / "araclar" / "yerel_gorsel.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m.uret


def kurulu_mu() -> bool:
    if os.environ.get("YST_GORSEL_SAHTE"):
        return True
    import importlib.util
    sp = importlib.util.spec_from_file_location("yst_yerel_gorsel_d", ROOT / "sistem" / "araclar" / "yerel_gorsel.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return bool(m.durum()["kurulu"])


def istem_olustur(istem: str, stil: str | None) -> str:
    istem = str(istem or "").strip()
    if not 3 <= len(istem) <= 1500:
        raise ValueError("istem 3-1500 karakter olmalı")
    if stil:
        if stil not in STIL:
            raise ValueError("bilinmeyen stil")
        return f"{istem}, {STIL[stil]['ek']}"[:2000]
    return istem


def _ekle(o: dict) -> dict:
    with kilit:
        d = _oku()
        d["ogeler"].append(o)
        _yaz(d)
    return o


def uret_tek(istem: str, stil: str | None = None, genislik: int = 1024, yukseklik: int = 576, tohum: int | None = None, adim: int = 8,
             seri: dict | None = None, kaynak_id: str | None = None) -> dict:
    """Tek görsel üretir; taslak olarak kütüphaneye yazar. Model kurulu değilse RuntimeError."""
    tam = istem_olustur(istem, stil)
    genislik, yukseklik = max(256, min(int(genislik), 1536)) // 64 * 64, max(256, min(int(yukseklik), 1536)) // 64 * 64
    tohum = int(tohum) if tohum is not None else random.randint(1, 2**31 - 1)
    gid = "g" + os.urandom(5).hex()
    TASLAK.mkdir(parents=True, exist_ok=True)
    hedef = TASLAK / f"{gid}.png"
    s = _uretici()(tam, str(hedef), genislik, yukseklik, tohum, adim)
    if not hedef.is_file():
        raise RuntimeError("üretim dosya bırakmadı")
    o = {"id": gid, "dosya": f"{gid}.png", "istem": str(istem).strip(), "stil": stil or "", "tohum": tohum, "genislik": genislik, "yukseklik": yukseklik, "adim": int(adim),
         "durum": "taslak", "kalite": kalite_olc(hedef), "not": "", "tarih": time.strftime("%Y-%m-%d %H:%M:%S"), "sn": s.get("sn"), "model": s.get("model"),
         "seri": seri or None, "kaynak": kaynak_id}
    return _ekle(o)


def is_baslat(istem: str, stil: str | None = None, genislik: int = 1024, yukseklik: int = 576, adet: int = 1, tohum: int | None = None, adim: int = 8,
              seri: dict | None = None, kaynak_id: str | None = None) -> dict:
    """Arka planda `adet` görsel üretir (her biri ayrı tohum). Panel durumu IS üzerinden okur."""
    istem_olustur(istem, stil)
    adet = max(1, min(int(adet), EN_COK_ADET))
    if not kurulu_mu():
        raise RuntimeError("yerel görsel üretim kurulu değil: panel → Ayarlar → Servisler ve modeller → Yerel görsel üretim → Kur")
    with kilit:
        if IS["calisiyor"]:
            raise ValueError("başka bir görsel üretiliyor, bitmesini bekle")
        IS.update(calisiyor=True, toplam=adet, tamam=0, hata=None, idler=[], mesaj="başladı", bas=time.time())

    def is_():
        try:
            temel = int(tohum) if tohum is not None else random.randint(1, 2**31 - 100)
            for i in range(adet):
                IS["mesaj"] = f"{i + 1}/{adet} üretiliyor…"
                o = uret_tek(istem, stil, genislik, yukseklik, temel + i, adim, seri, kaynak_id)
                IS["idler"].append(o["id"])
                IS["tamam"] = i + 1
            IS["mesaj"] = "bitti"
        except Exception as e:  # noqa: BLE001  (arka plan işi: hata kullanıcıya iletilir)
            IS["hata"] = str(e)[:300]
            IS["mesaj"] = "hata"
        finally:
            IS["calisiyor"] = False

    threading.Thread(target=is_, daemon=True, name="gorsel-uret").start()
    return {"ok": True, "adet": adet}


def is_durum() -> dict:
    with kilit:
        return {k: IS.get(k) for k in ("calisiyor", "toplam", "tamam", "hata", "idler", "mesaj")}


def yeniden(gid: str) -> dict:
    """Aynı istem, stil ve boyutla yeni tohumla üretim başlatır (beğenilmeyen görselin yerine)."""
    o = al(gid)
    return is_baslat(o["istem"], o["stil"] or None, o["genislik"], o["yukseklik"], 1, None, o["adim"], o.get("seri"), o["id"])


# ------------------------------------------------------------------ onay / arşiv
def _arsive_ekle() -> bool:
    """`kimlik/gorseller/onayli` klasörünü 'uretilen-gorseller' arşiv kökü olarak kaydeder (bir kez) ve taratır. Başarısızlık onayı engellemez."""
    if os.environ.get("YST_GORSEL_SAHTE"):
        return False
    try:
        sys.path.insert(0, str(ROOT / "sistem" / "arsiv"))
        sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
        import arsiv
        ONAYLI.mkdir(parents=True, exist_ok=True)
        r = arsiv.ayarla(str(ONAYLI), "uretilen-gorseller")
        arsiv.tara(kok_id=r["id"], yazdir=lambda *_: None)
        return True
    except Exception:  # noqa: BLE001
        return False


def onayla(gid: str, arsive: bool = True) -> dict:
    with kilit:
        d = _oku()
        o = next((x for x in d["ogeler"] if x["id"] == _kontrol_id(gid)), None)
        if not o:
            raise ValueError("görsel yok")
        if o["durum"] != "onayli":
            kaynak = TASLAK / o["dosya"]
            if not kaynak.is_file():
                raise ValueError("görsel dosyası yok")
            ONAYLI.mkdir(parents=True, exist_ok=True)
            shutil.move(str(kaynak), str(ONAYLI / o["dosya"]))
            o["durum"] = "onayli"
            o["onay_tarihi"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _yaz(d)
    o = dict(o)
    o["arsivde"] = _arsive_ekle() if arsive else False
    return o


def reddet(gid: str) -> dict:
    with kilit:
        d = _oku()
        o = next((x for x in d["ogeler"] if x["id"] == _kontrol_id(gid)), None)
        if not o:
            raise ValueError("görsel yok")
        if o["durum"] == "onayli":
            raise ValueError("onaylı görsel reddedilemez: silmek için 'sil'")
        o["durum"] = "reddedildi"
        _yaz(d)
        return dict(o)


def sil(gid: str) -> None:
    with kilit:
        d = _oku()
        o = next((x for x in d["ogeler"] if x["id"] == _kontrol_id(gid)), None)
        if not o:
            raise ValueError("görsel yok")
        _yol(o).unlink(missing_ok=True)
        d["ogeler"] = [x for x in d["ogeler"] if x["id"] != gid]
        _yaz(d)


def not_yaz(gid: str, metin: str) -> dict:
    with kilit:
        d = _oku()
        o = next((x for x in d["ogeler"] if x["id"] == _kontrol_id(gid)), None)
        if not o:
            raise ValueError("görsel yok")
        o["not"] = str(metin)[:300]
        _yaz(d)
        return dict(o)


def projeye(gid: str, proje: str, fmt: str = "ana") -> dict:
    """Görseli projeye kaynak olarak kopyalar: kaynak/foto/ (orijinal kaynak) ve <biçim>/media/foto/ (Kurgu'da hemen kullanılabilir)."""
    if not PROJE_RE.match(str(proje or "")):
        raise ValueError("geçersiz proje adı")
    if not re.fullmatch(r"[a-z0-9-]{1,20}", str(fmt or "ana")):
        raise ValueError("geçersiz biçim")
    p = ROOT / "projeler" / proje
    if not p.is_dir():
        raise ValueError("proje yok")
    src = yol(gid)
    o = al(gid)
    ad = f"uretilen-{gid}.png"
    k1 = p / "kaynak" / "foto"
    k1.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, k1 / ad)
    sonuc = {"kaynak": f"kaynak/foto/{ad}", "media": None}
    if (p / fmt).is_dir():
        k2 = p / fmt / "media" / "foto"
        k2.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, k2 / ad)
        sonuc["media"] = f"{fmt}/media/foto/{ad}"
    return {"id": gid, "istem": o["istem"], **sonuc}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    g = lambda n, v=None: a[a.index(n) + 1] if n in a else v  # noqa: E731
    try:
        if not a or a[0] == "stiller":
            for s in STILLER:
                print(f"{s['id']:18} {s['grup']:6} {s['ad']}: {s['aciklama']}")
        elif a[0] == "uret":
            seri = {"id": g("--seri"), "sezon": int(g("--sezon", 1)), "bolum": int(g("--bolum", 1))} if g("--seri") else None
            adet = int(g("--adet", 1))
            tohum = int(g("--tohum")) if g("--tohum") else None
            if "--bekle" in a:
                temel = tohum if tohum is not None else random.randint(1, 2**31 - 100)
                if not kurulu_mu():
                    raise RuntimeError("yerel görsel üretim kurulu değil")
                for i in range(max(1, min(adet, EN_COK_ADET))):
                    o = uret_tek(a[1], g("--stil"), int(g("--genislik", 1024)), int(g("--yukseklik", 576)), temel + i, int(g("--adim", 8)), seri)
                    print(json.dumps(o, ensure_ascii=False))
            else:
                print(json.dumps(is_baslat(a[1], g("--stil"), int(g("--genislik", 1024)), int(g("--yukseklik", 576)), adet, tohum, int(g("--adim", 8)), seri)))
        elif a[0] == "liste":
            for o in liste(g("--durum"), g("--seri")):
                print(f"{o['id']} {o['durum']:11} {o['genislik']}x{o['yukseklik']} {o['kalite']['durum']:5} {o['istem'][:60]}")
        elif a[0] == "onayla":
            print(json.dumps(onayla(a[1]), ensure_ascii=False))
        elif a[0] == "reddet":
            print(json.dumps(reddet(a[1]), ensure_ascii=False))
        elif a[0] == "sil":
            sil(a[1])
            print("silindi")
        elif a[0] == "yeniden":
            print(json.dumps(yeniden(a[1])))
        elif a[0] == "projeye":
            print(json.dumps(projeye(a[1], a[2], g("--format", "ana")), ensure_ascii=False))
        elif a[0] == "kalite":
            print(json.dumps(kalite_olc(a[1]), ensure_ascii=False))
        else:
            print(__doc__)
            return 2
    except (ValueError, RuntimeError, IndexError, OSError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
