#!/usr/bin/env python3
"""Arşiv analizi: dizindeki her dosyanın KULLANILABİLİRLİĞİNİ ve ne olduğunu veritabanına yazar; sonra video istenince arşive hiç gitmeden
doğrudan veritabanından uygun dosyalar seçilir. Dosyalar arşivde olduğu yerde durur; bu araç arşive YALNIZCA okur.

İki katman:
  1) OTOMATİK (yerel, ücretsiz, hızlı): çözünürlük, keskinlik, parlaklık, yinelenen (dhash), video süre/çözünürlük → kullanılabilir + puan + neden
  2) CLAUDE (anlamsal): fotoğraf kontakt sayfalarına bakıp aşama (öncesi/yapim/sonrasi/tasarim/diger), konu, açıklama, etiketleri yazar

  python sistem/arsiv/analiz.py oto [--limit N] [--proje klasör-önek] [--yil 2022-2024]     otomatik analiz (kesilirse devam eder)
  python sistem/arsiv/analiz.py bekleyen [--proje …] [--yil …] [--n 24]                       Claude için kontakt sayfası + eşleme JSON üretir
  python sistem/arsiv/analiz.py yaz <sonuc.json>                                              Claude'un bulgularını kaydeder
  python sistem/arsiv/analiz.py proje-yaz <klasor> --ozet "tek cümle" [--tur villa]           klasör (proje) için Claude özeti
  python sistem/arsiv/analiz.py uygun --yil 2022-2024 [--kelime villa] [--asama yapim] [--tur foto] [--proje …] [--en-az-puan 6] [--limit 60] [--analizsizler]
  python sistem/arsiv/analiz.py ozet [--derinlik 2]                                           kapsama: kaç dosya analiz edildi, kaçı kullanılabilir
  python sistem/arsiv/analiz.py kopya-listesi --idler 1,2,3 --hedef projeler/<ad>/kaynak      kopyalanan dosyaların analizini kaynak/arsiv_analiz.json'a yazar

Bir dosya arşivde değişirse (boyut/tarih) analizi geçersiz sayılır ve yeniden yapılır.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arsiv as A  # noqa: E402

SHEETS = A.DIR / "analiz_sayfalari"
ASAMALAR = ("oncesi", "yapim", "sonrasi", "tasarim", "diger")
ESIKLER = {"keskin_iyi": 60.0, "keskin_orta": 25.0, "keskin_kotu": 8.0, "karanlik": 28.0, "parlak": 235.0}
try:  # sistem/ortam/arsiv/esikler.json ile bu arşive göre ayarlanabilir (örn. {"keskin_kotu": 12})
    ESIKLER.update({k: float(v) for k, v in json.loads((A.DIR / "esikler.json").read_text(encoding="utf-8")).items() if k in ESIKLER})
except (OSError, ValueError):
    pass


GECERLI = "a.kok_id=d.kok_id AND a.yol=d.yol AND a.boyut=d.boyut AND ABS(a.mtime-d.mtime)<2"


def baglan():
    """Tek veritabanı: şema (analiz, iyilestirme dahil) arsiv.baglan() içinde, sürüm denetimli."""
    return A.baglan()


# ------------------------------------------------------------------ otomatik analiz
def _gri_ol(im) -> tuple[float, float, str]:
    """Gri küçük resimden (keskinlik, parlaklık, dhash). Keskinlik = kenar haritasının varyansı (512 px'e normalize)."""
    from PIL import ImageFilter, ImageStat
    g = im.convert("L")
    g.thumbnail((512, 512))
    kenar = g.filter(ImageFilter.FIND_EDGES)
    keskin = float(ImageStat.Stat(kenar).var[0])
    parlak = float(ImageStat.Stat(g).mean[0])
    k = g.resize((9, 8))
    px = list(k.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (1 if px[y * 9 + x] > px[y * 9 + x + 1] else 0)
    return keskin, parlak, f"{bits:016x}"


def _foto_olc(yol: str):
    from PIL import Image
    with Image.open(yol) as im:
        try:
            im.draft("RGB", (1024, 1024))  # JPEG'de hızlı küçük çözme
        except Exception:
            pass
        im.load()
        return _gri_ol(im)


def _video_kare_olc(yol: str, sure: float | None):
    """Videonun %20'sinden tek kare alıp keskinlik/parlaklık ölçer (ffmpeg gerekir; yoksa None)."""
    try:
        from PIL import Image
        t = max(0.0, (sure or 0) * 0.2)
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", yol, "-frames:v", "1", "-vf", "scale=640:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True, timeout=25, creationflags=A.NW, stdin=subprocess.DEVNULL)
        if r.returncode != 0 or not r.stdout:
            return None
        return _gri_ol(Image.open(io.BytesIO(r.stdout)))
    except Exception:
        return None


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def degerlendir(tur: str, w, h, sure, keskin, parlak) -> tuple[int, float, str]:
    """(kullanılabilir, puan 0-10, neden). Düşük çözünürlük 'kullanılamaz' değil 'iyileştirme gerekir' (Real-ESRGAN var); çok düşükse kullanılamaz."""
    puan, notlar = 10.0, []
    ok = 1
    kisa = min(w or 0, h or 0)
    if tur == "foto":
        if kisa and kisa < 400:
            return 0, 1.0, f"çok düşük çözünürlük ({w}x{h})"
        if kisa and kisa < 800:
            puan -= 3
            notlar.append(f"düşük çözünürlük ({w}x{h}): iyileştirme gerekir")
        elif kisa and kisa < 1280:
            puan -= 1
            notlar.append(f"orta çözünürlük ({w}x{h})")
    elif tur == "video":
        if sure is not None and sure < 1.5:
            return 0, 1.0, f"çok kısa ({sure:.1f} sn)"
        if kisa and kisa < 480:
            return 0, 1.0, f"çok düşük çözünürlük ({w}x{h})"
        if kisa and kisa < 720:
            puan -= 3
            notlar.append(f"düşük çözünürlük ({w}x{h})")
        elif kisa and kisa < 1080:
            puan -= 1
    else:
        return 1, 5.0, "belge/ses: bilgi ve ses kaynağı"
    if keskin is not None:
        if keskin < ESIKLER["keskin_kotu"]:
            puan -= 5
            notlar.append("çok bulanık")
        elif keskin < ESIKLER["keskin_orta"]:
            puan -= 2
            notlar.append("hafif bulanık")
        elif keskin < ESIKLER["keskin_iyi"]:
            puan -= 0.5
    if parlak is not None:
        if parlak < ESIKLER["karanlik"]:
            puan -= 4
            notlar.append("çok karanlık")
        elif parlak > ESIKLER["parlak"]:
            puan -= 4
            notlar.append("patlamış/çok parlak")
    puan = max(0.0, min(10.0, puan))
    if puan < 3:
        ok = 0
    return ok, round(puan, 1), "; ".join(notlar)


def _bagil_bulaniklik(c, klasorler: set) -> int:
    """Aynı klasördeki (aynı kamera/sahne) fotoğrafların medyanına göre çok bulanık olanları işaretle (mutlak eşik kalibre edilmemiş arşivlerde güvenilir).
    klasorler: {(kok_id, klasor)}"""
    import statistics
    n = 0
    for kid, k in klasorler:
        sat = c.execute("""SELECT a.yol, a.keskinlik, a.oto_puan, a.oto_neden FROM analiz a JOIN dosya d ON d.yol=a.yol AND d.kok_id=a.kok_id
                           WHERE d.kok_id=? AND d.klasor=? AND d.tur='foto' AND a.keskinlik IS NOT NULL AND a.keskinlik>=? AND a.kopya_of IS NULL""",
                        (kid, k, ESIKLER["keskin_kotu"])).fetchall()
        if len(sat) < 5:
            continue
        med = statistics.median(r["keskinlik"] for r in sat)
        for r in sat:
            if r["keskinlik"] < 0.2 * med and "klasörün" not in (r["oto_neden"] or ""):
                puan = max(0.0, (r["oto_puan"] or 0) - 4)
                neden = ((r["oto_neden"] + "; ") if r["oto_neden"] else "") + "klasörün geri kalanına göre çok bulanık"
                c.execute("UPDATE analiz SET oto_puan=?, oto_neden=?, oto_kullanilabilir=? WHERE kok_id=? AND yol=?", (puan, neden, 0 if puan < 3 else 1, kid, r["yol"]))
                n += 1
    return n


def oto(limit: int | None = None, proje: str | None = None, yil: str | None = None, durdur=None, yazdir=print, kok_id: int | None = None) -> dict:
    c = baglan()
    kokler = {a["id"]: Path(a["yol"]) for a in A.arsivler(c) if a["bagli"] and (not kok_id or a["id"] == kok_id)}
    if not kokler:
        raise RuntimeError("arşiv bağlı değil: harici diski tak ya da panel → Ayarlar → Konumlar'dan yolunu göster")
    wh, p = A._kosul(yil, "foto,video,ses,belge", None, None, c, proje, kok_id)
    sat = c.execute(f"""SELECT d.id, d.kok_id, d.yol, d.klasor, d.tur, d.boyut, d.mtime, d.genislik, d.yukseklik, d.sure, d.cevrimdisi FROM dosya d
                        LEFT JOIN analiz a ON {GECERLI}
                        {wh}{' AND ' if wh else ' WHERE '}a.yol IS NULL ORDER BY d.kok_id, d.klasor, d.ad""", p).fetchall()
    sat = [r for r in sat if r["kok_id"] in kokler]
    bulutta = [r for r in sat if r["cevrimdisi"] and r["tur"] in ("foto", "video")]
    sat = [r for r in sat if not (r["cevrimdisi"] and r["tur"] in ("foto", "video"))]  # bulutta-yalnızca: açmak indirmeyi tetikler, atlanır
    uzak_idler = {a["id"] for a in A.arsivler(c) if a.get("adaptor") == "rclone"}  # bulut disk: foto tek tek indirilir; büyük videolar indirilmez
    buyuk = {r["id"] for r in sat if r["kok_id"] in uzak_idler and r["tur"] == "video" and (r["boyut"] or 0) > 300e6}
    if buyuk:
        bulutta += [r for r in sat if r["id"] in buyuk]
        sat = [r for r in sat if r["id"] not in buyuk]
    if limit:
        sat = sat[:limit]
    # klasör içi yinelenen tespiti için mevcut dhash'ler
    gorulen: dict[tuple, list[tuple[str, str]]] = {}
    for r in c.execute("SELECT d.kok_id, d.klasor, a.dhash, a.yol FROM analiz a JOIN dosya d ON d.yol=a.yol AND d.kok_id=a.kok_id WHERE a.dhash IS NOT NULL"):
        gorulen.setdefault((r["kok_id"], r["klasor"]), []).append((r["dhash"], r["yol"]))
    sayac = {"islenen": 0, "kullanilabilir": 0, "kullanilamaz": 0, "hata": 0, "yinelenen": 0, "toplam_bekleyen": len(sat), "bulutta_atlanan": len(bulutta)}
    bas = time.time()
    son_ilerleme = time.monotonic()
    A.ilerleme_aktar(A.ilerleme_yaz, "analiz", "Dosyalar analiz ediliyor", bas, sayac)
    try:
        for i, r in enumerate(sat, 1):
            if durdur and durdur():
                break
            kid = r["kok_id"]
            anahtar = (kid, r["klasor"])
            keskin = parlak = dh = kopya = None
            w, h, sure = r["genislik"], r["yukseklik"], r["sure"]
            try:
                m_yol = A.mutlak(c, kid, r["yol"])  # bulut disk arşivinde dosyayı önbelleğe indirir
                if m_yol is None:
                    raise OSError("dosya alınamadı")
                mut = str(m_yol)
                if r["tur"] == "foto":
                    keskin, parlak, dh = _foto_olc(mut)
                elif r["tur"] == "video":
                    if sure is None or not w:
                        w, h, sure, *_ = A.video_meta(mut)
                        c.execute("UPDATE dosya SET genislik=?, yukseklik=?, sure=? WHERE id=?", (w, h, sure, r["id"]))
                    o = _video_kare_olc(mut, sure)
                    if o:
                        keskin, parlak, dh = o
                piksel = (w or 0) * (h or 0)
                if dh and (keskin or 0) >= ESIKLER["keskin_kotu"]:  # yapısız (düz/siyah/aşırı bulanık) görüntünün parmak izi anlamsızdır
                    for d2, y2 in gorulen.get(anahtar, []):
                        if _hamming(dh, d2) <= 2:
                            kopya = y2
                            break
                    gorulen.setdefault(anahtar, []).append((dh, r["yol"]))
                ok, puan, neden = degerlendir(r["tur"], w, h, sure, keskin, parlak)
                if kopya:
                    # en yüksek çözünürlüklü (eşitse en büyük dosya) KORUNUR; diğeri yinelenen sayılır
                    m = c.execute("SELECT d.genislik*d.yukseklik px, d.boyut FROM dosya d WHERE d.kok_id=? AND d.yol=?", (kid, kopya)).fetchone()
                    bu_daha_iyi = (piksel, r["boyut"] or 0) > ((m["px"] or 0) if m else 0, (m["boyut"] or 0) if m else 0)
                    if bu_daha_iyi:
                        c.execute("""UPDATE analiz SET kopya_of=?, oto_kullanilabilir=0, oto_puan=MIN(COALESCE(oto_puan,2),2),
                                     c_kullanilabilir=CASE WHEN c_kullanilabilir IS NULL THEN NULL ELSE 0 END,
                                     oto_neden=CASE WHEN oto_neden IS NULL OR oto_neden='' THEN ? ELSE oto_neden || '; ' || ? END WHERE kok_id=? AND yol=?""",
                                  (r["yol"], f"yinelenen ({r['yol']})", f"yinelenen ({r['yol']})", kid, kopya))
                        sayac["yinelenen"] += 1
                        kopya = None
                    else:
                        ok, puan = 0, min(puan, 2.0)
                        neden = (neden + "; " if neden else "") + f"yinelenen ({kopya})"
                        sayac["yinelenen"] += 1
                c.execute("""INSERT INTO analiz(kok_id,yol,boyut,mtime,keskinlik,parlaklik,dhash,kopya_of,oto_kullanilabilir,oto_puan,oto_neden,oto_tarih)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                             ON CONFLICT(kok_id, yol) DO UPDATE SET boyut=excluded.boyut, mtime=excluded.mtime, keskinlik=excluded.keskinlik, parlaklik=excluded.parlaklik,
                               dhash=excluded.dhash, kopya_of=excluded.kopya_of, oto_kullanilabilir=excluded.oto_kullanilabilir, oto_puan=excluded.oto_puan,
                               oto_neden=excluded.oto_neden, oto_tarih=excluded.oto_tarih,
                               c_kullanilabilir=NULL, c_puan=NULL, c_neden=NULL, asama=NULL, konu=NULL, aciklama=NULL, etiketler=NULL, c_tarih=NULL""",
                          (kid, r["yol"], r["boyut"], r["mtime"], keskin, parlak, dh, kopya, ok, puan, neden, time.strftime("%Y-%m-%d %H:%M")))
                sayac["kullanilabilir" if ok else "kullanilamaz"] += 1
            except Exception as e:  # bozuk dosya: kullanılamaz olarak işaretle, taramayı durdurma
                c.execute("""INSERT OR REPLACE INTO analiz(kok_id,yol,boyut,mtime,oto_kullanilabilir,oto_puan,oto_neden,oto_tarih) VALUES (?,?,?,?,?,?,?,?)""",
                          (kid, r["yol"], r["boyut"], r["mtime"], 0, 0.0, f"açılamadı: {type(e).__name__}", time.strftime("%Y-%m-%d %H:%M")))
                sayac["hata"] += 1
            sayac["islenen"] += 1
            if i % 200 == 0:
                c.commit()
                yazdir(f"  analiz {i}/{len(sat)}")
            if time.monotonic() - son_ilerleme >= 0.5:
                A.ilerleme_aktar(A.ilerleme_yaz, "analiz", "Dosyalar analiz ediliyor", bas, sayac,
                                 dosya=r["yol"].rsplit("/", 1)[-1])
                son_ilerleme = time.monotonic()
    finally:
        c.commit()
    if durdur and durdur():
        sayac["sn"] = int(time.time() - bas)
        A.ilerleme_aktar(A.ilerleme_yaz, "analiz", "Analiz durduruldu", bas, sayac)
        return sayac
    A.ilerleme_aktar(A.ilerleme_yaz, "analiz", "Son kalite kontrolleri yapılıyor", bas, sayac)
    sayac["bagil_bulanik"] = _bagil_bulaniklik(c, {(r["kok_id"], r["klasor"]) for r in sat[: sayac["islenen"]] if r["tur"] in ("foto", "video")})
    c.commit()
    sayac["sn"] = int(time.time() - bas)
    A.ilerleme_aktar(A.ilerleme_yaz, "analiz", "Analiz tamamlandı", bas, sayac)
    return sayac


# ------------------------------------------------------------------ Claude katmanı
def bekleyen(proje: str | None = None, yil: str | None = None, n: int = 24, tur: str = "foto", kok_id: int | None = None) -> dict:
    """Claude'un bakacağı bir kontakt sayfası: otomatik olarak kullanılabilir olan, henüz anlamlandırılmamış fotoğraflar (proje başına dengeli)."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    c = baglan()
    kokler = {a["id"]: Path(a["yol"]) for a in A.arsivler(c) if a["bagli"] and (not kok_id or a["id"] == kok_id)}
    if not kokler:
        raise RuntimeError("arşiv bağlı değil: harici diski tak")
    wh, p = A._kosul(yil, tur, None, None, c, proje, kok_id)
    sat = c.execute(f"""SELECT d.id, d.kok_id, d.yol, d.klasor FROM dosya d JOIN analiz a ON {GECERLI}
                        {wh}{' AND ' if wh else ' WHERE '}a.oto_kullanilabilir=1 AND a.c_tarih IS NULL AND d.cevrimdisi=0
                        ORDER BY d.klasor, a.oto_puan DESC, d.ad LIMIT 4000""", p).fetchall()
    sat = [r for r in sat if r["kok_id"] in kokler]
    toplam_kalan = c.execute(f"""SELECT COUNT(*) FROM dosya d JOIN analiz a ON {GECERLI}
                        {wh}{' AND ' if wh else ' WHERE '}a.oto_kullanilabilir=1 AND a.c_tarih IS NULL AND d.cevrimdisi=0""", p).fetchone()[0]
    if not sat:
        return {"sayfa": None, "oge": [], "kalan": 0, "mesaj": "bu kapsamda bekleyen fotoğraf yok (önce 'oto' çalıştır ya da hepsi anlamlandırıldı)"}
    # klasörler arasında dönüşümlü seç: bir sayfada tek klasör baskın olmasın
    gruplar: dict[str, list] = {}
    for r in sat:
        gruplar.setdefault(r["klasor"], []).append(r)
    secilen = []
    while len(secilen) < n and any(gruplar.values()):
        for k in list(gruplar):
            if gruplar[k] and len(secilen) < n:
                secilen.append(gruplar[k].pop(0))
    cols = 6
    rows = (len(secilen) + cols - 1) // cols
    tw, th = 300, 225
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:
        font = ImageFont.load_default()
    oge = []
    for i, r in enumerate(secilen, 1):
        try:
            m_yol = A.mutlak(c, r["kok_id"], r["yol"])
            if m_yol is None:
                raise OSError("dosya alınamadı")
            with Image.open(m_yol) as im:
                try:
                    im.draft("RGB", (640, 640))
                except Exception:
                    pass
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((tw - 4, th - 4))
                x, y = ((i - 1) % cols) * tw, ((i - 1) // cols) * th
                sheet.paste(im, (x + 2, y + 2))
        except Exception:
            continue
        dr.rectangle([x + 2, y + 2, x + 46, y + 34], fill=(0, 0, 0))
        dr.text((x + 6, y + 3), str(i), fill=(255, 230, 120), font=font)
        oge.append({"no": i, "id": r["id"], "klasor": r["klasor"], "ad": r["yol"].rsplit("/", 1)[-1]})
    SHEETS.mkdir(parents=True, exist_ok=True)
    yol = SHEETS / f"sayfa_{int(time.time())}.jpg"
    sheet.save(yol, "JPEG", quality=82)
    for eski in sorted(SHEETS.glob("sayfa_*.jpg"))[:-10]:
        eski.unlink(missing_ok=True)
    return {"sayfa": str(yol), "oge": oge, "kalan": max(0, toplam_kalan - len(oge)),
            "yonerge": "Sayfadaki her numara için: asama (oncesi|yapim|sonrasi|tasarim|diger), konu (cephe|ic-mekan|detay|kaba-yapi|ince-isler|peyzaj|plan-cizim|insan|diger), "
                       "aciklama (<=140 karakter, gördüğün şey), etiketler (3-6 kelime), puan (0-10: video için işe yararlık), kullanilabilir (true/false), neden (kısa)."}


def _temiz(s, n):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def yaz(satirlar: list[dict], eden: str = "claude") -> dict:
    c = baglan()
    fts = A.fts_var(c)
    yazilan, hata = 0, []
    for s in satirlar:
        try:
            r = c.execute("SELECT id, kok_id, yol, boyut, mtime, etiket FROM dosya WHERE id=?", (int(s["id"]),)).fetchone()
            if not r:
                raise ValueError("dosya yok")
            asama = _temiz(s.get("asama"), 20).lower() or "diger"
            if asama not in ASAMALAR:
                raise ValueError(f"asama {ASAMALAR} olmalı")
            puan = float(s.get("puan", 5))
            if not 0 <= puan <= 10:
                raise ValueError("puan 0-10")
            et = s.get("etiketler") or []
            et = ", ".join(_temiz(x, 30) for x in (et if isinstance(et, list) else str(et).split(",")) if _temiz(x, 30))[:200]
            konu, acik = _temiz(s.get("konu"), 40), _temiz(s.get("aciklama"), 200)
            ku = 1 if s.get("kullanilabilir", True) else 0
            ex = c.execute("SELECT 1 FROM analiz WHERE kok_id=? AND yol=?", (r["kok_id"], r["yol"])).fetchone()
            if not ex:  # otomatik analizden önce Claude bakmış olabilir: iskelet satır aç
                c.execute("INSERT INTO analiz(kok_id,yol,boyut,mtime,oto_kullanilabilir,oto_puan,oto_neden,oto_tarih) VALUES (?,?,?,?,?,?,?,?)",
                          (r["kok_id"], r["yol"], r["boyut"], r["mtime"], 1, None, "otomatik analiz yok", None))
            c.execute("""UPDATE analiz SET c_kullanilabilir=?, c_puan=?, c_neden=?, asama=?, konu=?, aciklama=?, etiketler=?, c_tarih=?, boyut=?, mtime=? WHERE kok_id=? AND yol=?""",
                      (ku, puan, _temiz(s.get("neden"), 160), asama, konu, acik, et, time.strftime("%Y-%m-%d %H:%M") + f" ({eden})", r["boyut"], r["mtime"], r["kok_id"], r["yol"]))
            if fts:  # anahtar kelime aramasında açıklama ve etiketler de bulunsun
                c.execute("DELETE FROM dosya_fts WHERE rowid=?", (r["id"],))
                c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)", (r["id"], " ".join([r["etiket"] or "", A.norm(" ".join([konu, asama, acik, et]))])))
            yazilan += 1
        except (ValueError, KeyError, TypeError) as e:
            hata.append({"id": s.get("id") if isinstance(s, dict) else None, "hata": str(e)})
    c.commit()
    return {"yazilan": yazilan, "hata": hata}


def proje_yaz(klasor: str, ozet: str, tur: str = "", kok_id: int | None = None) -> dict:
    klasor = klasor.strip().strip("/")
    if not klasor:
        raise ValueError("klasör gerekli")
    c = baglan()
    c.execute("INSERT OR REPLACE INTO proje_notu(kok_id,klasor,ozet,tur,tarih) VALUES (?,?,?,?,?)",
              (kok_id or A.varsayilan_kok(c) or 1, klasor, _temiz(ozet, 300), _temiz(tur, 40), time.strftime("%Y-%m-%d")))
    c.commit()
    return {"klasor": klasor}


# ------------------------------------------------------------------ sorgu
def uygun(yil=None, kelime=None, asama=None, tur="foto", proje=None, en_az_puan=6.0, limit=60, analizsizler=False, kok_id=None) -> list[dict]:
    """Taramasız seçim: veritabanındaki kullanılabilir dosyalar, puana göre. Claude analizi varsa o, yoksa otomatik puan geçerli."""
    c = baglan()
    wh, p = A._kosul(yil, tur, kelime, None, c, proje, kok_id)
    kos = [wh.replace(" WHERE ", "", 1)] if wh else []
    pr = list(p)
    if asama:
        kos.append("a.asama = ?")
        pr.append(asama)
    join = "LEFT JOIN" if analizsizler else "JOIN"
    gecerli = GECERLI
    if not analizsizler:
        # orijinali yeterli olan VEYA iyileştirilmiş sürümü kullanılabilir çıkan dosyalar
        kos.append("(COALESCE(a.c_kullanilabilir, a.oto_kullanilabilir) = 1 AND COALESCE(a.c_puan, a.oto_puan, 0) >= ? OR iy.sonraki_puan >= ?)")
        pr += [en_az_puan, en_az_puan]
    w2 = (" WHERE " + " AND ".join(k for k in kos if k)) if kos else ""
    sat = c.execute(f"""SELECT d.id, d.kok_id, d.yol, d.klasor, d.ad, d.tur, d.yil, d.genislik, d.yukseklik, d.sure,
                               COALESCE(iy.sonraki_puan, a.c_puan, a.oto_puan) puan, a.asama, a.konu, a.aciklama, a.etiketler, a.oto_neden, a.c_neden,
                               a.c_tarih IS NOT NULL anlamlandirildi, a.yol IS NOT NULL analizli, iy.id iyilestirme_id, iy.sonraki_puan iyilestirilmis_puan
                        FROM dosya d {join} analiz a ON {gecerli}
                        LEFT JOIN iyilestirme iy ON iy.id = (SELECT MAX(i2.id) FROM iyilestirme i2 WHERE i2.dosya_id=d.id AND i2.durum='tamam' AND i2.kullan=1){w2}
                        ORDER BY COALESCE(iy.sonraki_puan, a.c_puan, a.oto_puan, 0) DESC, d.yil, d.klasor, d.ad LIMIT ?""", pr + [limit]).fetchall()
    return [dict(r) for r in sat]


def proje_say(gruplar: list[str], yil=None, kok_id=None) -> dict:
    """Panelde grup kartları için: klasör başına fotoğraf sayısı, analizli ve kullanılabilir olanlar (yıl filtresiyle)."""
    c = baglan()
    y0, y1 = A._yil_araligi(yil)
    gecerli = GECERLI
    out = {}
    for g in gruplar:
        kos, pr = ["d.tur='foto'", "(d.klasor=? OR d.klasor LIKE ?)"], ["" if g == "(kök)" else g, ("" if g == "(kök)" else g) + "/%"]
        if kok_id:
            kos.append("d.kok_id=?")
            pr.append(kok_id)
        if y0:
            kos.append("d.yil BETWEEN ? AND ?")
            pr += [y0, y1]
        r = c.execute(f"""SELECT COUNT(*) n, SUM(a.yol IS NOT NULL) analizli, SUM(a.c_tarih IS NOT NULL) claude,
                          SUM(COALESCE(a.c_kullanilabilir, a.oto_kullanilabilir)=1) kullanilabilir
                          FROM dosya d LEFT JOIN analiz a ON {gecerli} WHERE {' AND '.join(kos)}""", pr).fetchone()
        out[g] = {"foto": r["n"] or 0, "analizli": r["analizli"] or 0, "claude": r["claude"] or 0, "kullanilabilir": r["kullanilabilir"] or 0}
    return out


def ozet(derinlik: int = 2) -> dict:
    c = baglan()
    gecerli = GECERLI
    toplam = {}
    for r in c.execute(f"""SELECT d.tur, COUNT(*) n, SUM(a.yol IS NOT NULL) oto, SUM(a.c_tarih IS NOT NULL) claude,
                           SUM(COALESCE(a.c_kullanilabilir, a.oto_kullanilabilir)=1) kullanilabilir
                           FROM dosya d LEFT JOIN analiz a ON {gecerli} GROUP BY d.tur"""):
        toplam[r["tur"]] = {"dosya": r["n"], "otomatik_analiz": r["oto"] or 0, "claude_analiz": r["claude"] or 0, "kullanilabilir": r["kullanilabilir"] or 0}
    notlar = {r["klasor"]: dict(r) for r in c.execute("SELECT * FROM proje_notu")}
    gr: dict[str, dict] = {}
    for r in c.execute(f"""SELECT d.klasor, d.yil, d.tur, a.yol IS NOT NULL oto, a.c_tarih IS NOT NULL cl,
                           COALESCE(a.c_kullanilabilir, a.oto_kullanilabilir)=1 ku FROM dosya d LEFT JOIN analiz a ON {gecerli}"""):
        k = "/".join((r["klasor"] or "(kök)").split("/")[:derinlik])
        g = gr.setdefault(k, {"proje": k, "dosya": 0, "analiz": 0, "claude": 0, "kullanilabilir": 0, "yil_min": None, "yil_max": None})
        g["dosya"] += 1
        g["analiz"] += 1 if r["oto"] else 0
        g["claude"] += 1 if r["cl"] else 0
        g["kullanilabilir"] += 1 if r["ku"] else 0
        if r["yil"]:
            g["yil_min"] = r["yil"] if g["yil_min"] is None else min(g["yil_min"], r["yil"])
            g["yil_max"] = r["yil"] if g["yil_max"] is None else max(g["yil_max"], r["yil"])
    for k, g in gr.items():
        g["not"] = (notlar.get(k) or {}).get("ozet")
    return {"turler": toplam, "projeler": sorted(gr.values(), key=lambda g: (g["yil_min"] or 9999, g["proje"]))[:400]}


def kopya_listesi(idler: list[int], hedef: str) -> dict:
    """Projeye alınan dosyaların analiz bilgisini kaynak/arsiv_analiz.json'a yazar (senarist/sahne ajanı neyin ne olduğunu buradan okur)."""
    c = baglan()
    sonuc = []
    for i in idler:
        r = c.execute("""SELECT d.ad, d.yol, d.tur, d.yil, a.asama, a.konu, a.aciklama, a.etiketler, COALESCE(a.c_puan,a.oto_puan) puan, a.oto_neden
                         FROM dosya d LEFT JOIN analiz a ON a.yol=d.yol AND a.kok_id=d.kok_id WHERE d.id=?""", (i,)).fetchone()
        if r:
            sonuc.append(dict(r))
    Path(hedef).mkdir(parents=True, exist_ok=True)
    (Path(hedef) / "arsiv_analiz.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"yazilan": len(sonuc)}


# ------------------------------------------------------------------ komut satırı
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    o = sp.add_parser("oto")
    o.add_argument("--limit", type=int)
    o.add_argument("--proje")
    o.add_argument("--yil")
    b = sp.add_parser("bekleyen")
    b.add_argument("--proje")
    b.add_argument("--yil")
    b.add_argument("--n", type=int, default=24)
    b.add_argument("--tur", default="foto")
    sp.add_parser("yaz").add_argument("dosya")
    py = sp.add_parser("proje-yaz")
    py.add_argument("klasor")
    py.add_argument("--ozet", required=True)
    py.add_argument("--tur", default="")
    u = sp.add_parser("uygun")
    u.add_argument("--yil")
    u.add_argument("--kelime")
    u.add_argument("--asama")
    u.add_argument("--tur", default="foto")
    u.add_argument("--proje")
    u.add_argument("--en-az-puan", type=float, default=6.0)
    u.add_argument("--limit", type=int, default=60)
    u.add_argument("--analizsizler", action="store_true")
    u.add_argument("--json", action="store_true")
    z = sp.add_parser("ozet")
    z.add_argument("--derinlik", type=int, default=2)
    kl = sp.add_parser("kopya-listesi")
    kl.add_argument("--idler", required=True)
    kl.add_argument("--hedef", required=True)
    a = ap.parse_args()
    try:
        if a.k == "oto":
            print(json.dumps(oto(a.limit, a.proje, a.yil), ensure_ascii=False))
        elif a.k == "bekleyen":
            print(json.dumps(bekleyen(a.proje, a.yil, a.n, a.tur), ensure_ascii=False, indent=1))
        elif a.k == "yaz":
            print(json.dumps(yaz(json.loads(Path(a.dosya).read_text(encoding="utf-8"))), ensure_ascii=False))
        elif a.k == "proje-yaz":
            print(json.dumps(proje_yaz(a.klasor, a.ozet, a.tur), ensure_ascii=False))
        elif a.k == "uygun":
            r = uygun(a.yil, a.kelime, a.asama, a.tur, a.proje, a.en_az_puan, a.limit, a.analizsizler)
            if a.json:
                print(json.dumps(r, ensure_ascii=False))
            else:
                for f in r:
                    print(f"{f['id']:7} {f['yil'] or '----'} {f['puan'] if f['puan'] is not None else '-':>4} {(f['asama'] or '-'):8} {f['yol']}  {f['aciklama'] or f['oto_neden'] or ''}")
                print(f"-- {len(r)} sonuç", file=sys.stderr)
        elif a.k == "ozet":
            print(json.dumps(ozet(a.derinlik), ensure_ascii=False, indent=1))
        elif a.k == "kopya-listesi":
            print(json.dumps(kopya_listesi([int(x) for x in a.idler.split(",") if x.strip()], a.hedef), ensure_ascii=False))
    except (ValueError, RuntimeError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
