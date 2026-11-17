#!/usr/bin/env python3
"""Arşiv fotoğraflarını iyileştirir (çözünürlük + bulanıklık). Orijinal arşiv dosyasına ASLA dokunulmaz: sonuç stüdyo klasöründe
sistem/ortam/arsiv/iyilestirilmis/ altına yazılır, veritabanına (iyilestirme tablosu: kök + göreli yol) işlenir ve "önce/sonra" ölçülür.
Projeye alınırken iyileştirilmiş sürüm varsa o kopyalanır (arsiv.kopyala).

Modeller Ayarlar → "İşler ve modeller"den gelir (iş: gorsel-iyilestirme). Yerel olanlar ücretsiz; bulut olanlar yalnızca bağlayıcı etkin +
anahtar var + işlem başına onay verilirse çalışır, fotoğraf seçilen servise GİDER ve arsiv/bulut_gunlugu.md'ye yazılır.

  python sistem/arsiv/iyilestir.py modeller
  python sistem/arsiv/iyilestir.py adaylar [--yil 2022-2024] [--proje klasör] [--en-cok-puan 6] [--limit 40]      iyileştirmeye değer (düşük puanlı) fotoğraflar
  python sistem/arsiv/iyilestir.py calistir --idler 1,2,3 [--model yerel-realesrgan] [--olcek 2] [--keskinlik 0.5] [--bulut-onay]
  python sistem/arsiv/iyilestir.py liste [--idler 1,2]                                                              yapılmış iyileştirmeler
  python sistem/arsiv/iyilestir.py kullan <iyilestirme_id> evet|hayir                                              projeye alınırken bu sürüm kullanılsın mı

Dürüstlük: Real-ESRGAN gerçekte var olan ayrıntıyı toparlar (hareket bulanıklığını ve çok küçük görüntüleri tam kurtaramaz). Üretken bulut modeller
ayrıntı UYDURABİLİR: müşteriye "gerçek önce/sonra" diye gösterilecek işlerde yerel modeli seç.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "sistem" / "baglayici"))
import arsiv as A  # noqa: E402
import analiz as Z  # noqa: E402
import ortak  # noqa: E402

CIKTI = A.DIR / "iyilestirilmis"
ENHANCE = ROOT / ".claude" / "skills" / "kurgu-video-studio" / "scripts" / "enhance_image.py"
IS = "gorsel-iyilestirme"
ISTEM_BULUT = ("Bu fotoğrafı iyileştir: çözünürlüğü ve netliği artır, bulanıklığı ve sıkıştırma gürültüsünü gider. "
               "İçeriği DEĞİŞTİRME: nesneleri, renkleri, kompozisyonu, yazıları, yüzleri, ışığı olduğu gibi koru; yeni nesne, kişi ya da ayrıntı ekleme; "
               "kırpma yapma, en-boy oranını koru.")
_model_onbellek: dict = {}
BULUT_GIRIS_KENAR = 2048


# ------------------------------------------------------------------ model kaydı
def is_ayari() -> dict:
    return (ortak.ayar_modul().coz().get("isler") or {}).get(IS) or {}


def _yerel_hazir(motor: str) -> tuple[bool, str]:
    if motor == "klasik":
        try:
            import PIL  # noqa: F401
            return True, ""
        except ImportError:
            return False, "Pillow yok"
    for paket in ("torch", "spandrel"):  # içe aktarmadan bak: torch'u yüklemek saniyeler sürer, liste hızlı açılmalı
        if importlib.util.find_spec(paket) is None:
            return False, f"{paket} kurulu değil (kurulum tamamlanmadı mı?)"
    if not ENHANCE.is_file():
        return False, "enhance_image.py bulunamadı (skill kurulumu eksik)"
    return True, ""


def modeller() -> dict:
    """Açılır liste için: etkin olanlar + her birinin kullanılabilirliği ve nedeni. {'varsayilan','modeller':[…]}"""
    a = is_ayari()
    kat = ortak.katalog()["saglayicilar"]
    out = []
    for mid, m in (a.get("modeller") or {}).items():
        sid = m.get("saglayici", "yerel")
        yerel = sid == "yerel"
        ok, neden = (_yerel_hazir(m.get("motor", "")) if yerel else (True, ""))
        if not yerel:
            k = kat.get(sid)
            if not k:
                ok, neden = False, "sağlayıcı kataloğda yok"
            else:
                b = ortak.baglayici_durumu(sid)
                if not b["etkin"]:
                    ok, neden = False, "bağlayıcı kapalı (Ayarlar → Bağlayıcılar)"
                elif b["anahtar_var"] is False:
                    ok, neden = False, "API anahtarı yok (Ayarlar → Bağlayıcılar)"
        out.append({"id": mid, "ad": m.get("ad", mid), "motor": m.get("motor"), "saglayici": sid, "yerel": yerel, "ucretli": (not yerel) and bool(kat.get(sid, {}).get("ucretli")),
                    "model": m.get("model", ""), "etkin": bool(m.get("etkin")), "kullanilabilir": ok, "neden": neden, "not": m.get("not", ""),
                    "gonderilen": None if yerel else kat.get(sid, {}).get("gonderilen")})
    return {"varsayilan": a.get("varsayilan"), "ad": a.get("ad"), "modeller": out}


# ------------------------------------------------------------------ adaylar
def adaylar(yil: str | None = None, proje: str | None = None, en_cok_puan: float = 6.0, limit: int = 60, kok_id: int | None = None, yapilmislar: bool = False) -> list[dict]:
    """İyileştirmeye değer fotoğraflar: puanı eşiğin altında olan ya da 'düşük çözünürlük / bulanık / iyileştirme gerekir' denmiş olanlar.
    Çok düşük çözünürlük (<400 px) kurtarılamaz sayılır, listelenmez."""
    c = A.baglan()
    wh, p = A._kosul(yil, "foto", None, None, c, proje, kok_id)
    kos = [wh.replace(" WHERE ", "", 1)] if wh else []
    kos += ["d.cevrimdisi = 0", "(COALESCE(a.c_puan, a.oto_puan) < ? OR COALESCE(a.oto_neden,'') LIKE '%iyileştirme gerekir%' OR COALESCE(a.oto_neden,'') LIKE '%bulanık%' OR COALESCE(a.oto_neden,'') LIKE '%düşük çözünürlük%')", "COALESCE(a.oto_neden,'') NOT LIKE '%çok düşük çözünürlük%'", "a.kopya_of IS NULL"]
    p = list(p) + [en_cok_puan]
    if not yapilmislar:
        kos.append("NOT EXISTS (SELECT 1 FROM iyilestirme i WHERE i.dosya_id=d.id AND i.durum='tamam')")
    sat = c.execute(f"""SELECT d.id, d.kok_id, d.yol, d.klasor, d.ad, d.yil, d.genislik, d.yukseklik, COALESCE(a.c_puan, a.oto_puan) puan, a.oto_neden neden, a.keskinlik
                        FROM dosya d JOIN analiz a ON {Z.GECERLI} WHERE {' AND '.join(kos)}
                        ORDER BY COALESCE(a.c_puan, a.oto_puan), d.klasor, d.ad LIMIT ?""", p + [limit]).fetchall()
    return [dict(r) for r in sat]


# ------------------------------------------------------------------ motorlar
def _enhance_modul():
    if "enhance" not in _model_onbellek:
        spec = importlib.util.spec_from_file_location("yst_enhance_image", ENHANCE)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _model_onbellek["enhance"] = m
    return _model_onbellek["enhance"]


def _aygit() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _motor_realesrgan(girdi: Path, cikti: Path, olcek: float, keskinlik: float) -> dict:
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
    es = _enhance_modul()
    dev = _aygit()
    if dev not in _model_onbellek:
        _model_onbellek[dev] = es.load_model("realesrgan-x4plus", dev)
    model = _model_onbellek[dev]
    im = ImageOps.exif_transpose(Image.open(girdi)).convert("RGB")
    w, h = im.size
    max_giris = 1800 if dev == "cuda" else 1100  # bellek/süre: büyük girdi önce küçültülür (bulanık fotoğrafta kayıp azdır)
    k = min(1.0, max_giris / max(w, h))
    if k < 1:
        im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    t = time.time()
    buyuk = es.upscale_tiled(model, np.asarray(im, dtype=np.float32) / 255.0, dev, tile=256 if dev == "cuda" else 128)
    res = Image.fromarray((buyuk * 255 + 0.5).astype("uint8"))
    hedef_w, hedef_h = round(w * olcek), round(h * olcek)
    kenar = 3840 / max(hedef_w, hedef_h)
    if kenar < 1:
        hedef_w, hedef_h = round(hedef_w * kenar), round(hedef_h * kenar)
    hedef_w, hedef_h = min(hedef_w, res.width), min(hedef_h, res.height)  # girdi küçültüldüyse modelin ürettiğinden büyük çıktı istenemez
    if (hedef_w, hedef_h) != res.size:
        res = res.resize((hedef_w, hedef_h), Image.LANCZOS)
    if keskinlik > 0:
        res = res.filter(ImageFilter.UnsharpMask(radius=1.0, percent=int(25 + 90 * keskinlik), threshold=2))
    cikti.parent.mkdir(parents=True, exist_ok=True)
    res.save(cikti, quality=95, subsampling=0)
    return {"cihaz": dev, "girdi_kuculdu": k < 1, "sn": round(time.time() - t, 1)}


def _motor_klasik(girdi: Path, cikti: Path, olcek: float, keskinlik: float) -> dict:
    from PIL import Image, ImageFilter, ImageOps
    im = ImageOps.exif_transpose(Image.open(girdi)).convert("RGB")
    w, h = im.size
    kenar = min(1.0, 3840 / max(w * olcek, h * olcek))
    tw, th = max(1, round(w * olcek * kenar)), max(1, round(h * olcek * kenar))
    if (tw, th) != im.size:
        im = im.resize((tw, th), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=int(60 + 160 * keskinlik), threshold=3))
    cikti.parent.mkdir(parents=True, exist_ok=True)
    im.save(cikti, quality=95, subsampling=0)
    return {"cihaz": "cpu"}


def _motor_bulut(sid: str, mdl: dict, girdi: Path, cikti: Path, bulut_onay: bool) -> dict:
    if not bulut_onay:
        raise ortak.IzinHatasi("bulut modeli için bu işleme onay vermelisin (fotoğraflar seçtiğin servise gönderilir)")
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(girdi)).convert("RGB")
    if max(im.size) > BULUT_GIRIS_KENAR:
        im.thumbnail((BULUT_GIRIS_KENAR, BULUT_GIRIS_KENAR), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=92)
    if ortak.katalog()["saglayicilar"].get(sid, {}).get("ozel"):  # kullanıcı tanımlı sağlayıcı: yetenek çekirdeği (bildirimsel manifest)
        import yetenek
        b64 = base64.b64encode(b.getvalue()).decode("ascii")
        r = yetenek.cagir("gorsel-duzenle", {"istem": ISTEM_BULUT, "gorsel_bayt": b.getvalue(), "gorsel_b64": b64, "gorsel_data_uri": "data:image/jpeg;base64," + b64, "mime": "image/jpeg",
                                              **({"model": mdl["model"]} if mdl.get("model") else {})}, cikti.with_suffix(".bulut"), tercih=sid, onay=True, yedek=False)
        with Image.open(r["dosya"]) as sonuc:
            sonuc.convert("RGB").save(cikti, quality=95, subsampling=0)
        Path(r["dosya"]).unlink(missing_ok=True)
        return {"cihaz": "bulut", "bulut_model": r.get("model") or "", "tahmin": r.get("maliyet")}
    ctx = ortak.izin_kontrol_arsiv(sid, "gorsel-duzenle")
    if mdl.get("model"):
        ctx["model"] = mdl["model"]
    from uret import sag_modul
    m = sag_modul(sid)
    if not hasattr(m, "duzenle"):
        raise ortak.IzinHatasi(f"{sid} fotoğraf düzenlemeyi desteklemiyor")
    gecici = cikti.with_suffix(".bulut")
    r = m.duzenle(ctx, ISTEM_BULUT, b.getvalue(), "image/jpeg", gecici)
    # servis PNG/JPEG döndürebilir; standart JPEG'e çevir
    with Image.open(r["dosya"]) as sonuc:
        sonuc.convert("RGB").save(cikti, quality=95, subsampling=0)
    Path(r["dosya"]).unlink(missing_ok=True)
    ortak.arsiv_gunluk(sid, "gorsel-duzenle", f"1 fotoğraf ({im.size[0]}x{im.size[1]}, {len(b.getvalue()) // 1024} KB) ← {girdi.name}", f"model={r['model']}")
    return {"cihaz": "bulut", "bulut_model": r["model"]}


# ------------------------------------------------------------------ iş
def _olc(yol: Path):
    ks, pr, _ = Z._foto_olc(str(yol))
    return ks, pr


def iyilestir(idler: list[int], model_id: str | None = None, olcek: float = 2.0, keskinlik: float = 0.5, bulut_onay: bool = False,
              durdur=None, ilerleme=None) -> dict:
    """Seçilen dosyaları iyileştirir. ilerleme(dict) her dosyadan sonra çağrılır. Dönüş: {'tamam','hata','sonuclar':[…]}"""
    a = is_ayari()
    mid = model_id or a.get("varsayilan")
    mdl = (a.get("modeller") or {}).get(mid)
    if not mdl:
        raise ValueError(f"model tanımlı değil: {mid}")
    if not mdl.get("etkin"):
        raise ValueError(f"'{mdl.get('ad', mid)}' Ayarlar'da listeye açık değil")
    olcek = max(1.0, min(float(olcek), 4.0))
    keskinlik = max(0.0, min(float(keskinlik), 1.0))
    sid = mdl.get("saglayici", "yerel")
    if sid == "yerel":
        ok, neden = _yerel_hazir(mdl.get("motor", ""))
        if not ok:
            raise RuntimeError(neden)
    c = A.baglan()
    sonuc = {"tamam": 0, "hata": 0, "sonuclar": [], "model": mid}
    for sira, i in enumerate(idler, 1):
        if durdur and durdur():
            break
        r = c.execute("""SELECT d.id, d.kok_id, d.yol, d.tur, d.cevrimdisi, k.ad kok_ad, COALESCE(a.c_puan, a.oto_puan) puan, a.keskinlik
                         FROM dosya d JOIN kok k ON k.id=d.kok_id LEFT JOIN analiz a ON a.kok_id=d.kok_id AND a.yol=d.yol WHERE d.id=?""", (i,)).fetchone()
        kayit = {"dosya_id": i, "durum": "hata", "hata": None}
        try:
            if not r or r["tur"] != "foto":
                raise ValueError("fotoğraf değil / kayıt yok")
            if r["cevrimdisi"]:
                raise ValueError("dosya bulutta-yalnızca (indirilmemiş): önce bilgisayara indir")
            kaynak = A.mutlak(c, r["kok_id"], r["yol"])
            if kaynak is None or not kaynak.is_file():
                raise ValueError("kaynak arşivde bulunamadı (disk bağlı mı?)")
            ad = f"{i}_{mid}.jpg"
            rel = f"sistem/ortam/arsiv/iyilestirilmis/{r['kok_ad']}/{ad}"
            hedef = ROOT.joinpath(*rel.split("/"))
            once_keskin = r["keskinlik"]
            if once_keskin is None:
                once_keskin, _ = _olc(kaynak)
            t0 = time.time()
            if sid != "yerel":
                ek = _motor_bulut(sid, mdl, kaynak, hedef, bulut_onay)
            elif mdl["motor"] == "realesrgan":
                ek = _motor_realesrgan(kaynak, hedef, olcek, keskinlik)
            else:
                ek = _motor_klasik(kaynak, hedef, olcek, keskinlik)
            ek["toplam_sn"] = round(time.time() - t0, 1)
            from PIL import Image
            with Image.open(hedef) as im:
                w, h = im.size
            sonra_keskin, parlak = _olc(hedef)
            ok_, puan, neden = Z.degerlendir("foto", w, h, None, sonra_keskin, parlak)
            c.execute("UPDATE iyilestirme SET kullan=0 WHERE dosya_id=?", (i,))  # bir dosya için aynı anda tek sürüm kullanılır: en yenisi
            iy_id = c.execute("""INSERT INTO iyilestirme(dosya_id,model,saglayici,parametre,cikti_kok,cikti_yol,genislik,yukseklik,onceki_keskin,sonraki_keskin,onceki_puan,sonraki_puan,
                         sonraki_kullanilabilir,durum,tarih,kullan) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                      (i, mid, sid, json.dumps({"olcek": olcek, "keskinlik": keskinlik, **ek}, ensure_ascii=False), "studyo", rel, w, h, once_keskin, sonra_keskin,
                       r["puan"], puan, 1 if ok_ else 0, "tamam", time.strftime("%Y-%m-%d %H:%M"))).lastrowid
            c.commit()
            kayit.update({"iy_id": iy_id, "durum": "tamam", "cikti_yol": rel, "genislik": w, "yukseklik": h, "onceki_puan": r["puan"], "sonraki_puan": puan,
                          "onceki_keskin": round(once_keskin or 0, 1), "sonraki_keskin": round(sonra_keskin, 1), "sn": ek["toplam_sn"]})
            sonuc["tamam"] += 1
        except Exception as e:  # noqa: BLE001  (tek dosya hatası tüm işi durdurmaz)
            kayit["hata"] = f"{type(e).__name__}: {ortak.maskele(str(e))}"[:220]
            sonuc["hata"] += 1
            try:
                c.execute("INSERT INTO iyilestirme(dosya_id,model,saglayici,durum,hata,tarih,kullan) VALUES (?,?,?,?,?,?,0)",
                          (i, mid, sid, "hata", kayit["hata"], time.strftime("%Y-%m-%d %H:%M")))
                c.commit()
            except Exception:  # noqa: BLE001
                pass
        sonuc["sonuclar"].append(kayit)
        if ilerleme:
            ilerleme({"sira": sira, "toplam": len(idler), "tamam": sonuc["tamam"], "hata": sonuc["hata"], "son": kayit})
    return sonuc


def liste(idler: list[int] | None = None) -> list[dict]:
    c = A.baglan()
    q = """SELECT i.*, d.yol, d.klasor, d.ad, d.genislik ow, d.yukseklik oh FROM iyilestirme i JOIN dosya d ON d.id=i.dosya_id"""
    p: list = []
    if idler:
        q += " WHERE i.dosya_id IN (%s)" % ",".join("?" * len(idler))
        p = list(idler)
    return [dict(r) for r in c.execute(q + " ORDER BY i.id DESC LIMIT 500", p).fetchall()]


def kullan(iy_id: int, evet: bool) -> dict:
    c = A.baglan()
    r = c.execute("SELECT dosya_id, durum FROM iyilestirme WHERE id=?", (iy_id,)).fetchone()
    if not r or r["durum"] != "tamam":
        raise ValueError("böyle bir başarılı iyileştirme yok")
    if evet:  # bir dosya için aynı anda tek sürüm kullanılır
        c.execute("UPDATE iyilestirme SET kullan=0 WHERE dosya_id=?", (r["dosya_id"],))
    c.execute("UPDATE iyilestirme SET kullan=? WHERE id=?", (1 if evet else 0, iy_id))
    c.commit()
    return {"ok": True}


def sil(iy_id: int) -> dict:
    c = A.baglan()
    r = c.execute("SELECT cikti_yol FROM iyilestirme WHERE id=?", (iy_id,)).fetchone()
    if r and r["cikti_yol"]:
        p = ROOT.joinpath(*r["cikti_yol"].split("/")).resolve()
        if CIKTI.resolve() in p.parents:
            p.unlink(missing_ok=True)
    c.execute("DELETE FROM iyilestirme WHERE id=?", (iy_id,))
    c.commit()
    return {"ok": True}


def onizleme(iy_id: int, en: int = 360):
    """İyileştirilmiş görüntünün küçük resmi (JPEG bayt)."""
    c = A.baglan()
    r = c.execute("SELECT cikti_yol FROM iyilestirme WHERE id=? AND durum='tamam'", (iy_id,)).fetchone()
    if not r or not r["cikti_yol"]:
        return None
    p = ROOT.joinpath(*r["cikti_yol"].split("/"))
    if not p.is_file():
        return None
    from PIL import Image
    with Image.open(p) as im:
        im = im.convert("RGB")
        im.thumbnail((en, en))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=82)
        return b.getvalue()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    sp.add_parser("modeller")
    ad = sp.add_parser("adaylar")
    ad.add_argument("--yil")
    ad.add_argument("--proje")
    ad.add_argument("--en-cok-puan", type=float, default=6.0)
    ad.add_argument("--limit", type=int, default=40)
    ca = sp.add_parser("calistir")
    ca.add_argument("--idler", required=True)
    ca.add_argument("--model")
    ca.add_argument("--olcek", type=float, default=2.0)
    ca.add_argument("--keskinlik", type=float, default=0.5)
    ca.add_argument("--bulut-onay", action="store_true")
    li = sp.add_parser("liste")
    li.add_argument("--idler")
    ku = sp.add_parser("kullan")
    ku.add_argument("id", type=int)
    ku.add_argument("deger", choices=["evet", "hayir"])
    a = ap.parse_args()
    try:
        if a.k == "modeller":
            for m in modeller()["modeller"]:
                print(f"{m['id']:18} {'LİSTEDE ' if m['etkin'] else 'kapalı  '}{'hazır ' if m['kullanilabilir'] else 'YOK   '} {m['ad']}  {m['neden']}")
        elif a.k == "adaylar":
            for r in adaylar(a.yil, a.proje, a.en_cok_puan, a.limit):
                print(f"{r['id']:7} puan {r['puan']:>4} {r['genislik']}x{r['yukseklik']} {r['yol']}  {r['neden'] or ''}")
        elif a.k == "calistir":
            r = iyilestir([int(x) for x in a.idler.split(",") if x.strip()], a.model, a.olcek, a.keskinlik, a.bulut_onay,
                          ilerleme=lambda d: print(f"  {d['sira']}/{d['toplam']} {d['son']['durum']} {d['son'].get('hata') or ''}", file=sys.stderr))
            print(json.dumps(r, ensure_ascii=False, indent=1))
        elif a.k == "liste":
            print(json.dumps(liste([int(x) for x in a.idler.split(",")] if a.idler else None), ensure_ascii=False, indent=1))
        elif a.k == "kullan":
            print(json.dumps(kullan(a.id, a.deger == "evet")))
    except (ValueError, RuntimeError, ortak.IzinHatasi, ortak.AgHatasi) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
