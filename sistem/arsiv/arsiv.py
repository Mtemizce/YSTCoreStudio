#!/usr/bin/env python3
"""Arşiv dizini: harici diskteki (~1 TB) iş arşivini TARAR (yalnızca okur), aranabilir bir yerel dizin (SQLite) kurar,
"şu yıllardaki şu tür işlerden" seçim yapıp projeye kopyalar. Arşive ASLA yazılmaz, hiçbir şey silinmez/taşınmaz.

  python sistem/arsiv/arsiv.py ayarla <arşiv klasörü> [--ad arsiv]   arşiv kökünü ekle/güncelle (birim seri no da kaydedilir; birden çok arşiv: farklı --ad)
  python sistem/arsiv/arsiv.py kokler                        arşivler, bu bilgisayardaki yolları, bağlı mı
  python sistem/arsiv/arsiv.py durum                         bağlı mı, kaç dosya, hangi yıllar/türler
  python sistem/arsiv/arsiv.py tara [--derin] [--ad arsiv]   dizini kur/güncelle (tekrar çalıştırınca yalnızca değişenler; kesilirse devam eder)
  python sistem/arsiv/arsiv.py yapi                          üst klasörlerin özeti (proje derinliğini seçmek için)
  python sistem/arsiv/arsiv.py projeler [--derinlik 1] [--yil 2012-2016] [--kelime "konut cephe"] [--tur foto]
  python sistem/arsiv/arsiv.py ara [--yil 2013-2016] [--tur foto,video,belge] [--kelime "cephe sıva"] [--klasor parça] [--limit 200]
  python sistem/arsiv/arsiv.py kopyala --idler 1,2,3 --hedef projeler/<ad>/kaynak [--en-cok-gb 8] [--video-en-cok-mb 1500]
  python sistem/arsiv/arsiv.py bul "Tarkan Şımarık" --tur muzik [--kopyala projeler/<ad>] [--id 123]   ADLA bul (kullanıcı prompt'ta "şu müziği kullan" dediğinde)

Kategoriler (kullanıcıya gösterilen ad → dizindeki tür): Resim (foto) · Video (video) · Müzik (ses: müzik, kayıt, ses efekti) · Dosya (belge: çizim, PDF, Word, Excel…).
`--tur` her iki adı da kabul eder (resim|foto, muzik|ses, dosya|belge, video); birden çok arşiv eklenebilir (ör. yalnızca müzik klasörün için ayrı bir arşiv).

Dizin yeri: sistem/ortam/arsiv/arsiv.db (git'e girmez; stüdyo klasörüyle birlikte kopyalanır). Kayıtlarda MUTLAK yol yok: (kök + göreli yol).
Kökün bu bilgisayardaki yolu çalışırken çözülür (sistem/araclar/konum.py): bilgisayar adı, disk seri no, ortam değişkeni YST_ARSIV, elle Gözat.
Bulutta-yalnızca (OneDrive/Drive) dosyalar taramada içerik okunmadan (indirmeden) kaydedilir. Tarih önceliği: EXIF > dosya adı (IMG_20130119…) > klasör adındaki yıl > değişiklik tarihi.
Hızlı tarama varsayılan: dosya bilgisi + foto EXIF; `--derin` videolara ffprobe (süre/çözünürlük/çekim tarihi) ekler (yavaş).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
import konum as K  # noqa: E402

DIR = ROOT / "sistem" / "ortam" / "arsiv"
AYAR = DIR / "ayar.json"          # yalnızca eski (v1) kurulumdan göç için okunur
DB = DIR / "arsiv.db"
ILERLEME = DIR / "ilerleme.json"

TURLER = {
    "foto": {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".webp", ".bmp", ".gif", ".avif", ".nef", ".cr2", ".cr3", ".arw", ".dng", ".orf", ".rw2"},
    "video": {".mp4", ".mov", ".mkv", ".avi", ".mts", ".m2ts", ".mxf", ".wmv", ".m4v", ".webm", ".mpg", ".mpeg", ".3gp"},
    "ses": {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".aif", ".aiff", ".wma", ".mka"},
    "belge": {".dwg", ".dxf", ".pdf", ".docx", ".xlsx", ".doc", ".xls", ".pptx", ".skp", ".rvt", ".ifc", ".3ds", ".dgn", ".txt", ".md", ".csv", ".rtf", ".odt"},
}
TUR_ETIKET = {"foto": "Resim", "video": "Video", "ses": "Müzik", "belge": "Dosya"}   # kullanıcıya gösterilen kategori adları
TUR_TAKMA = {"foto": "foto", "resim": "foto", "gorsel": "foto", "fotograf": "foto", "video": "video", "ses": "ses", "muzik": "ses", "sarki": "ses",
             "belge": "belge", "dosya": "belge", "cizim": "belge"}
BUL_GEREKSIZ = {"muzik", "sarki", "ses", "parca", "dosya", "resim", "foto", "video", "belge", "ve", "ile", "bir", "bu", "su", "o", "olsun", "calsin", "kullan",
                "kullanilsin", "arka", "planda", "fon", "icin", "adli", "isimli", "mp3", "wav", "flac", "m4a", "ogg", "mp4"}
UZ2TUR = {u: t for t, us in TURLER.items() for u in us}
ATLA_KLASOR = {"$recycle.bin", "system volume information", ".trash", ".spotlight-v100", ".fseventsd", "recycler", "@eadir", ".thumbnails", "__macosx"}
ATLA_DOSYA = {"thumbs.db", "desktop.ini", ".ds_store"}
TR = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def tur_coz(t: str | None) -> str | None:
    """'muzik' → 'ses', 'resim' → 'foto', 'dosya' → 'belge' (dizindeki tür adı); bilinmeyen ad olduğu gibi döner (hata vermeden boş sonuç)."""
    if not t:
        return t
    return TUR_TAKMA.get(norm(t.strip()), t.strip())


def norm(s: str) -> str:
    """Aranabilir biçim: Türkçe büyük/küçük harf + aksan katlama (Şantiye ≡ santiye, İÇ ≡ ic)."""
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return s.translate(TR)


# ------------------------------------------------------------------ veritabanı
def baglan() -> sqlite3.Connection:
    """Tek veritabanı (sistem/ortam/arsiv/arsiv.db). Klasörle birlikte taşınır: içinde MUTLAK dosya yolu yok (kök + göreli yol)."""
    DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    K.sema_kur(c, AYAR)
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS dosya_fts USING fts5(etiket, tokenize='unicode61')")
    except sqlite3.OperationalError:
        pass  # FTS5 yoksa LIKE ile aranır
    return c


# ------------------------------------------------------------------ kökler (arşivler)
def varsayilan_kok(c=None) -> int | None:
    """İlk arşiv kökü (tek arşivli kullanımda 'arşiv')."""
    c = c or baglan()
    r = c.execute("SELECT id FROM kok WHERE tur='arsiv' ORDER BY id LIMIT 1").fetchone()
    return r[0] if r else None


def kok_coz(kok_id: int | None = None, c=None) -> Path | None:
    """Arşivin BU bilgisayardaki yolu (konum.py sırasıyla: ortam değişkeni, kayıt, başka bilgisayar, disk seri no, sürücü taraması)."""
    c = c or baglan()
    kid = kok_id or varsayilan_kok(c)
    return K.kok_coz(c, kid)["yol"] if kid else None


def mutlak(c, kok_id: int, yol: str) -> Path | None:
    return K.mutlak(c, kok_id, yol)


def arsivler(c=None) -> list[dict]:
    c = c or baglan()
    return [r for r in K.kok_listesi(c) if r["tur"] == "arsiv"]


def fts_var(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='dosya_fts'").fetchone() is not None


# ------------------------------------------------------------------ meta çıkarma
YIL_AD = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(0[1-9]|1[0-2])([0-2]\d|3[01])(?!\d)")
YIL_KL = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")


def foto_meta(yol: str):
    try:
        from PIL import Image
        with Image.open(yol) as im:
            w, h = im.size
            tarih = None
            try:
                ex = im.getexif()
                tarih = ex.get_ifd(0x8769).get(36867) or ex.get(306)
            except Exception:
                pass
        if tarih:
            m = re.match(r"(\d{4}):(\d{2}):(\d{2})", str(tarih))
            if m and 1980 <= int(m.group(1)) <= 2039:
                return w, h, int(m.group(1)), int(m.group(2))
        return w, h, None, None
    except Exception:
        return None, None, None, None


def video_meta(yol: str):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", yol],
                           capture_output=True, text=True, timeout=30)
        j = json.loads(r.stdout)
        v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
        sure = float(j.get("format", {}).get("duration") or 0) or None
        ct = (j.get("format", {}).get("tags") or {}).get("creation_time", "")
        m = re.match(r"(\d{4})-(\d{2})", ct)
        return v.get("width"), v.get("height"), sure, (int(m.group(1)) if m and 1980 <= int(m.group(1)) <= 2039 else None), (int(m.group(2)) if m else None)
    except Exception:
        return None, None, None, None, None


def ses_meta(yol: str):
    """(süre sn, etiket metni): ffprobe ile süre + dosya etiketleri (başlık, sanatçı, albüm, tür). ffprobe yoksa/okunamazsa (None, '')."""
    if not shutil.which("ffprobe"):
        return None, ""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", yol], capture_output=True, text=True, timeout=15)
        f = json.loads(r.stdout).get("format", {})
        sure = float(f.get("duration") or 0) or None
        tag = {k.lower(): v for k, v in (f.get("tags") or {}).items()}
        return sure, " ".join(str(tag.get(k, "")) for k in ("title", "artist", "album_artist", "album", "genre"))
    except Exception:
        return None, ""


def yil_coz(rel: str, mtime: float, exif_yil, exif_ay, video_yil, video_ay):
    if exif_yil:
        return exif_yil, exif_ay, "exif"
    if video_yil:
        return video_yil, video_ay, "video"
    ad = os.path.basename(rel)
    m = YIL_AD.search(ad)
    if m:
        return int(m.group(1)), int(m.group(2)), "ad"
    for parca in reversed(rel.split("/")[:-1]):
        m = YIL_KL.search(parca)
        if m:
            return int(m.group(1)), None, "klasor"
    t = time.localtime(mtime)
    return t.tm_year, t.tm_mon, "mtime"


def etiket_uret(rel: str) -> str:
    parcalar = re.split(r"[/\\._\-\s()\[\]]+", norm(rel))
    return " ".join(sorted({p for p in parcalar if len(p) > 1 and not p.isdigit()}))


# ------------------------------------------------------------------ tarama
def ilerleme_yaz(d: dict) -> None:
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        ILERLEME.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _iso_epoch(s) -> float:
    import datetime as _dt
    try:
        s = re.sub(r"(\.\d{6})\d+", r"\1", str(s).replace("Z", "+00:00"))
        return _dt.datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _tara_uzak(c, kid: int, ad: str, uzak: str, durdur, yazdir) -> dict:
    """Bulut disk (rclone) taraması: yalnızca LİSTE (ad, boyut, tarih). İçerik indirilmez; çözünürlük/keskinlik analiz sırasında ölçülür."""
    baslangic = time.time()
    fts = fts_var(c)
    var_olan = {r["yol"]: (r["boyut"], r["mtime"]) for r in c.execute("SELECT yol, boyut, mtime FROM dosya WHERE kok_id=?", (kid,))}
    sayac = {"gezilen": 0, "yeni": 0, "guncellenen": 0, "ayni": 0, "hata": 0, "bulutta": 0}
    ilerleme_yaz({"durum": "çalışıyor (bulut listesi alınıyor)", "arsiv": ad, **sayac, "sn": 0})
    liste = K._bd().dosyalar(uzak)
    kesildi = False
    bekleyen = 0
    for e in liste:
        if durdur and durdur():
            kesildi = True
            break
        rel = str(e.get("Path", "")).replace("\\", "/")
        parcalar = rel.split("/")
        isim = parcalar[-1]
        if not rel or isim.lower() in ATLA_DOSYA or any(p.lower() in ATLA_KLASOR or p.startswith("$") for p in parcalar[:-1]):
            continue
        uz = os.path.splitext(isim)[1].lower()
        tur = UZ2TUR.get(uz)
        if tur is None:
            continue
        boyut = int(e.get("Size") or 0)
        mtime = _iso_epoch(e.get("ModTime"))
        sayac["gezilen"] += 1
        eski = var_olan.get(rel)
        if eski and eski[0] == boyut and abs(eski[1] - mtime) < 2:
            c.execute("UPDATE dosya SET goruldu=?, cevrimdisi=0 WHERE kok_id=? AND yol=?", (baslangic, kid, rel))
            sayac["ayni"] += 1
        else:
            yil, ay, kay = yil_coz(rel, mtime, None, None, None, None)
            et = etiket_uret(rel)
            klasor = "/".join(parcalar[:-1])
            c.execute("""INSERT INTO dosya(kok_id,yol,klasor,ad,uzanti,tur,boyut,mtime,yil,ay,tarih_kaynagi,etiket,goruldu,cevrimdisi)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)
                         ON CONFLICT(kok_id, yol) DO UPDATE SET boyut=excluded.boyut, mtime=excluded.mtime, yil=excluded.yil, ay=excluded.ay,
                           tarih_kaynagi=excluded.tarih_kaynagi, etiket=excluded.etiket, goruldu=excluded.goruldu, cevrimdisi=0""",
                      (kid, rel, klasor, isim, uz, tur, boyut, mtime, yil, ay, kay, et, baslangic))
            if fts:
                rid = c.execute("SELECT id FROM dosya WHERE kok_id=? AND yol=?", (kid, rel)).fetchone()[0]
                c.execute("DELETE FROM dosya_fts WHERE rowid=?", (rid,))
                c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)", (rid, et + " " + norm(isim)))
            sayac["yeni" if eski is None else "guncellenen"] += 1
        bekleyen += 1
        if bekleyen >= 2000:
            c.commit()
            bekleyen = 0
            ilerleme_yaz({"durum": "çalışıyor", "arsiv": ad, **sayac, "sn": int(time.time() - baslangic)})
            yazdir(f"  {sayac['gezilen']} dosya · yeni {sayac['yeni']} · değişmemiş {sayac['ayni']}")
    return _tara_sonu(c, kid, ad, fts, baslangic, kesildi, sayac)


def _tara_kok(c, kid: int, derin: bool, durdur, yazdir) -> dict:
    kok = kok_coz(kid, c)
    ad, adaptor, uzak = c.execute("SELECT ad, adaptor, uzak FROM kok WHERE id=?", (kid,)).fetchone()
    if kok is None:
        raise RuntimeError(f"'{ad}' arşivi bağlı değil ya da bu bilgisayarda bulunamadı: " + K.kok_coz(c, kid)["not"])
    if adaptor == "rclone":
        return _tara_uzak(c, kid, ad, uzak, durdur, yazdir)
    baslangic = time.time()
    fts = fts_var(c)
    var_olan = {}
    ffp = bool(shutil.which("ffprobe"))
    for r in c.execute("SELECT yol, boyut, mtime, tur, sure FROM dosya WHERE kok_id=?", (kid,)):
        # ses dosyasında süre/etiket henüz okunmadıysa (eski tarama) yeniden işlenir
        var_olan[r["yol"]] = (r["boyut"], r["mtime"]) if not (ffp and r["tur"] == "ses" and r["sure"] is None) else (-1, 0)
    sayac = {"gezilen": 0, "yeni": 0, "guncellenen": 0, "ayni": 0, "hata": 0, "bulutta": 0}
    bekleyen = 0
    yigin = [kok]
    kesildi = False
    ilerleme_yaz({"durum": "çalışıyor", "arsiv": ad, **sayac, "sn": 0})
    try:
        while yigin:
            if durdur and durdur():
                kesildi = True
                break
            d = yigin.pop()
            try:
                girdiler = list(os.scandir(d))
            except OSError:
                sayac["hata"] += 1
                continue
            for e in girdiler:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() not in ATLA_KLASOR and not e.name.startswith("$"):
                            yigin.append(Path(e.path))
                        continue
                    if not e.is_file(follow_symlinks=False) or e.name.lower() in ATLA_DOSYA:
                        continue
                    uz = os.path.splitext(e.name)[1].lower()
                    tur = UZ2TUR.get(uz)
                    if tur is None:
                        continue
                    st = e.stat()
                    rel = Path(e.path).relative_to(kok).as_posix()
                    sayac["gezilen"] += 1
                    eski = var_olan.get(rel)
                    bulut = K.bulutta_mi(st)  # içerik yerelde değil: açmak indirmeyi tetikler, o yüzden okunmaz
                    if eski and eski[0] == st.st_size and abs(eski[1] - st.st_mtime) < 2:
                        c.execute("UPDATE dosya SET goruldu=?, cevrimdisi=? WHERE kok_id=? AND yol=?", (baslangic, 1 if bulut else 0, kid, rel))
                        sayac["ayni"] += 1
                    else:
                        w = h = sure = ey = ea = None
                        ses_et = ""
                        if not bulut:
                            if tur == "foto":
                                w, h, ey, ea = foto_meta(e.path)
                            elif tur == "video" and derin:
                                w, h, sure, ey, ea = video_meta(e.path)
                            elif tur == "ses":
                                sure, ses_et = ses_meta(e.path)
                        else:
                            sayac["bulutta"] += 1
                        yil, ay, kay = yil_coz(rel, st.st_mtime, ey if tur == "foto" else None, ea if tur == "foto" else None,
                                               ey if tur == "video" else None, ea if tur == "video" else None)
                        et = etiket_uret(rel + " " + ses_et) if ses_et else etiket_uret(rel)
                        klasor = rel.rsplit("/", 1)[0] if "/" in rel else ""
                        c.execute("""INSERT INTO dosya(kok_id,yol,klasor,ad,uzanti,tur,boyut,mtime,yil,ay,tarih_kaynagi,genislik,yukseklik,sure,etiket,goruldu,cevrimdisi)
                                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                     ON CONFLICT(kok_id, yol) DO UPDATE SET boyut=excluded.boyut, mtime=excluded.mtime, yil=excluded.yil, ay=excluded.ay,
                                       tarih_kaynagi=excluded.tarih_kaynagi, genislik=excluded.genislik, yukseklik=excluded.yukseklik,
                                       sure=excluded.sure, etiket=excluded.etiket, goruldu=excluded.goruldu, cevrimdisi=excluded.cevrimdisi""",
                                  (kid, rel, klasor, e.name, uz, tur, st.st_size, st.st_mtime, yil, ay, kay, w, h, sure, et, baslangic, 1 if bulut else 0))
                        if fts:
                            rid = c.execute("SELECT id FROM dosya WHERE kok_id=? AND yol=?", (kid, rel)).fetchone()[0]
                            c.execute("DELETE FROM dosya_fts WHERE rowid=?", (rid,))
                            c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)", (rid, et + " " + norm(e.name)))
                        sayac["yeni" if eski is None else "guncellenen"] += 1
                    bekleyen += 1
                    if bekleyen >= 2000:
                        c.commit()
                        bekleyen = 0
                        ilerleme_yaz({"durum": "çalışıyor", "arsiv": ad, **sayac, "sn": int(time.time() - baslangic), "klasor": str(d.relative_to(kok))[:80]})
                        yazdir(f"  {sayac['gezilen']} dosya · yeni {sayac['yeni']} · değişmemiş {sayac['ayni']}")
                except OSError:
                    sayac["hata"] += 1
    except KeyboardInterrupt:
        kesildi = True
    c.commit()
    return _tara_sonu(c, kid, ad, fts, baslangic, kesildi, sayac)


def _tara_sonu(c, kid: int, ad: str, fts: bool, baslangic: float, kesildi: bool, sayac: dict) -> dict:
    if True:
        if kesildi:
            c.commit()
            sayac["sn"] = int(time.time() - baslangic)
            sayac["durum"] = "kesildi (tekrar çalıştırınca devam eder)"
            sayac["arsiv"] = ad
            return sayac
        # bu taramada görülmeyenler arşivden silinmiş/taşınmış: dizinden çıkar (arşive dokunulmaz); yalnızca BU kökün kayıtları
        gidenler = [r[0] for r in c.execute("SELECT id FROM dosya WHERE kok_id=? AND goruldu < ?", (kid, baslangic))]
        for i in gidenler:
            c.execute("DELETE FROM iyilestirme WHERE dosya_id=?", (i,))
            c.execute("DELETE FROM dosya WHERE id=?", (i,))
            if fts:
                c.execute("DELETE FROM dosya_fts WHERE rowid=?", (i,))
        c.execute("DELETE FROM analiz WHERE kok_id=? AND yol NOT IN (SELECT yol FROM dosya WHERE kok_id=?)", (kid, kid))
        sayac["silinen_kayit"] = len(gidenler)
        zaman = time.strftime("%Y-%m-%d %H:%M")
        c.execute("INSERT OR REPLACE INTO meta VALUES ('son_tam_tarama', ?)", (zaman,))
        c.execute("UPDATE kok SET son_tarama=? WHERE id=?", (zaman, kid))
    c.commit()
    sayac["sn"] = int(time.time() - baslangic)
    sayac["durum"] = "kesildi (tekrar çalıştırınca devam eder)" if kesildi else "bitti"
    sayac["arsiv"] = ad
    return sayac


def tara(derin: bool = False, durdur=None, yazdir=print, kok_id: int | None = None) -> dict:
    """Arşiv(ler)i tarar. kok_id verilmezse bağlı olan TÜM arşivler sırayla (bağlı olmayanlar atlanır, kayıtları silinmez)."""
    c = baglan()
    hedef = [kok_id] if kok_id else [a["id"] for a in arsivler(c)]
    if not hedef:
        raise RuntimeError("arşiv tanımlı değil (önce 'ayarla' ya da panel → Ayarlar → Konumlar)")
    sonuclar, atlanan = [], []
    for kid in hedef:
        if durdur and durdur():
            break
        try:
            sonuclar.append(_tara_kok(c, kid, derin, durdur, yazdir))
        except RuntimeError as e:
            if kok_id:
                raise
            atlanan.append(str(e))
    if not sonuclar:
        raise RuntimeError("arşiv bağlı değil: " + "; ".join(atlanan))
    top = {k: sum(s.get(k, 0) for s in sonuclar) for k in ("gezilen", "yeni", "guncellenen", "ayni", "hata", "bulutta", "sn", "silinen_kayit")}
    top["durum"] = sonuclar[-1]["durum"]
    top["arsiv"] = ", ".join(s["arsiv"] for s in sonuclar)
    if atlanan:
        top["atlanan"] = atlanan
    ilerleme_yaz(top)
    return top


# ------------------------------------------------------------------ sorgular
def _yil_araligi(s: str | None):
    if not s:
        return None, None
    m = re.match(r"^\s*(\d{4})\s*(?:[-–:]\s*(\d{4}))?\s*$", s)
    if not m:
        raise ValueError(f"yıl biçimi 2013 ya da 2013-2016 olmalı: {s!r}")
    a = int(m.group(1))
    return a, int(m.group(2) or a)


def _kosul(yil=None, tur=None, kelime=None, klasor=None, c=None, klasor_on=None, kok_id=None):
    w, p = [], []
    if kok_id:
        w.append("d.kok_id = ?")
        p.append(int(kok_id))
    y0, y1 = _yil_araligi(yil)
    if y0:
        w.append("d.yil BETWEEN ? AND ?")
        p += [y0, y1]
    if tur:
        turler = [tur_coz(t) for t in (tur.split(",") if isinstance(tur, str) else tur) if t and t.strip()]
        w.append("d.tur IN (%s)" % ",".join("?" * len(turler)))
        p += turler
    if klasor:
        w.append("d.klasor LIKE ?")
        p.append("%" + klasor + "%")
    if klasor_on is not None:
        w.append("(d.klasor = ? OR d.klasor LIKE ?)")
        p += [klasor_on, klasor_on + "/%"]
    if kelime:
        toks = [t for t in re.split(r"\s+", norm(kelime)) if t]
        if c is not None and fts_var(c):
            w.append("d.id IN (SELECT rowid FROM dosya_fts WHERE dosya_fts MATCH ?)")
            p.append(" ".join('"%s"*' % t.replace('"', "") for t in toks))
        else:
            for t in toks:
                w.append("d.etiket LIKE ?")
                p.append("%" + t + "%")
    return (" WHERE " + " AND ".join(w)) if w else "", p


def ara(yil=None, tur=None, kelime=None, klasor=None, limit=200, klasor_on=None, kok_id=None) -> list[dict]:
    c = baglan()
    wh, p = _kosul(yil, tur, kelime, klasor, c, klasor_on, kok_id)
    sat = c.execute(f"SELECT d.id, d.kok_id, d.yol, d.klasor, d.ad, d.tur, d.yil, d.boyut, d.genislik, d.yukseklik, d.sure, d.cevrimdisi FROM dosya d{wh} "
                    f"ORDER BY d.yil, d.klasor, d.ad LIMIT ?", p + [limit]).fetchall()
    return [dict(r) for r in sat]


def bul(ifade: str, tur: str | None = None, limit: int = 10, kok_id: int | None = None) -> list[dict]:
    """Dosyayı ADIYLA bul (kullanıcı prompt'ta "şu müziği kullan" dediğinde). Dosya adı, klasör adı ve (müzikte) başlık/sanatçı/albüm etiketleri aranır;
    Türkçe aksan/büyük-küçük harf farkı yok. Sonuç: en iyi eşleşme önce; `puan` = ifadedeki anlamlı sözcüklerin kaçı eşleşti (1.0 = hepsi), `tam` = hepsi eşleşti."""
    toks = [t for t in re.split(r"[^a-z0-9]+", norm(ifade)) if t and t not in BUL_GEREKSIZ and len(t) > 1]
    if not toks:
        return []
    c = baglan()
    w, p = ["(" + " OR ".join("d.etiket LIKE ?" for _ in toks) + ")"], ["%" + t + "%" for t in toks]
    if tur:
        turler = [tur_coz(t) for t in (tur.split(",") if isinstance(tur, str) else tur) if t and t.strip()]
        w.append("d.tur IN (%s)" % ",".join("?" * len(turler)))
        p += turler
    if kok_id:
        w.append("d.kok_id = ?")
        p.append(int(kok_id))
    sat = c.execute("SELECT d.id, d.kok_id, d.yol, d.klasor, d.ad, d.tur, d.yil, d.boyut, d.sure, d.cevrimdisi, d.etiket, k.ad AS arsiv FROM dosya d JOIN kok k ON k.id = d.kok_id "
                    "WHERE " + " AND ".join(w) + " LIMIT 3000", p).fetchall()
    sonuc = []
    for r in sat:
        metin = norm(r["ad"] + " " + r["klasor"])
        et = r["etiket"] or ""
        eslesen = sum(1 for t in toks if t in metin or t in et)
        ad_esl = sum(1 for t in toks if t in norm(r["ad"]))
        d = dict(r)
        d.pop("etiket")
        d.update(puan=round(eslesen / len(toks), 2), tam=eslesen == len(toks), _s=(eslesen, ad_esl, -len(r["ad"])))
        sonuc.append(d)
    sonuc.sort(key=lambda x: x["_s"], reverse=True)
    for x in sonuc:
        x.pop("_s")
        x["kategori"] = TUR_ETIKET.get(x["tur"], x["tur"])
    return sonuc[:limit]


def projeye_ekle(proje_klasoru: str, dosya_id: int) -> dict:
    """Arşivdeki dosyayı projenin kaynak/ klasörüne KOPYALAR (müzik → kaynak/ses/) ve kaynak/arsiv_secim.json'a 'kullanici_dosyalari' olarak işler
    (hangi dosya, hangi arşivden, ne zaman: kullanıcının kendi parçası olduğu için lisans sorumluluğu kullanıcıdadır)."""
    kaynak = Path(proje_klasoru) / "kaynak"
    kaynak.mkdir(parents=True, exist_ok=True)
    r = kopyala([dosya_id], str(kaynak), 8.0, 4000.0, True)
    if not r["kopyalanan"]:
        return {"ok": False, "atlanan": r["atlanan"]}
    c = baglan()
    d = c.execute("SELECT d.yol, d.ad, d.tur, k.ad AS arsiv FROM dosya d JOIN kok k ON k.id = d.kok_id WHERE d.id=?", (dosya_id,)).fetchone()
    kay = kaynak / "arsiv_secim.json"
    try:
        j = json.loads(kay.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        j = {}
    hedef_rel = Path(r["ayrinti"][0]["hedef"]).resolve().relative_to(Path(proje_klasoru).resolve()).as_posix()
    j.setdefault("kullanici_dosyalari", []).append({"ad": d["ad"], "kategori": TUR_ETIKET.get(d["tur"], d["tur"]), "arsiv": d["arsiv"], "arsiv_yolu": d["yol"],
                                                    "projede": hedef_rel, "tarih": time.strftime("%Y-%m-%d %H:%M"), "not": "kullanıcının kendi arşivi: lisans/telif kullanıcı sorumluluğunda"})
    kay.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "projede": hedef_rel, "ad": d["ad"], "kategori": TUR_ETIKET.get(d["tur"], d["tur"]), "arsiv": d["arsiv"]}


def projeler(derinlik=1, yil=None, tur=None, kelime=None, limit=300, kok_id=None) -> list[dict]:
    """Klasörleri 'proje' olarak grupla (ilk `derinlik` klasör düzeyi)."""
    c = baglan()
    wh, p = _kosul(yil, tur, kelime, None, c, None, kok_id)
    gruplar: dict[str, dict] = {}
    for r in c.execute(f"SELECT d.id, d.klasor, d.ad, d.tur, d.yil, d.boyut FROM dosya d{wh}", p):
        anahtar = "/".join(r["klasor"].split("/")[:derinlik]) if r["klasor"] else "(kök)"
        g = gruplar.setdefault(anahtar, {"proje": anahtar, "foto": 0, "video": 0, "ses": 0, "belge": 0, "yil_min": None, "yil_max": None, "boyut": 0, "ornek": []})
        g[r["tur"]] += 1
        g["boyut"] += r["boyut"] or 0
        if r["yil"]:
            g["yil_min"] = r["yil"] if g["yil_min"] is None else min(g["yil_min"], r["yil"])
            g["yil_max"] = r["yil"] if g["yil_max"] is None else max(g["yil_max"], r["yil"])
        if len(g["ornek"]) < 3 and r["tur"] == "foto":
            g["ornek"].append(r["id"])
    cikti = sorted(gruplar.values(), key=lambda g: (g["yil_min"] or 9999, g["proje"]))
    return cikti[:limit]


def yapi(derinlik=2, kok_id=None) -> list[dict]:
    c = baglan()
    sat: dict[str, int] = {}
    q, p = "SELECT klasor, COUNT(*) n FROM dosya", []
    if kok_id:
        q, p = q + " WHERE kok_id=?", [kok_id]
    for r in c.execute(q + " GROUP BY klasor", p):
        k = "/".join(r["klasor"].split("/")[:derinlik]) if r["klasor"] else "(kök)"
        sat[k] = sat.get(k, 0) + r["n"]
    return [{"klasor": k, "dosya": n} for k, n in sorted(sat.items(), key=lambda x: -x[1])[:60]]


def durum() -> dict:
    c = baglan()
    ar = arsivler(c)
    ilk = ar[0] if ar else None
    d = {"ayarli": bool(ar), "arsivler": ar, "kayitli_yol": ilk["kayitli_yol"] if ilk else None, "bagli": any(a["bagli"] for a in ar),
         "yol": next((a["yol"] for a in ar if a["bagli"]), None), "disk_etiketi": None, "makine": K.makine()}
    d["toplam"] = c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
    if d["toplam"]:
        d["tur"] = {r[0]: r[1] for r in c.execute("SELECT tur, COUNT(*) FROM dosya GROUP BY tur")}
        d["kategoriler"] = [{"tur": t, "ad": TUR_ETIKET[t], "adet": d["tur"].get(t, 0)} for t in ("foto", "video", "ses", "belge")]
        d["yillar"] = {str(r[0]): r[1] for r in c.execute("SELECT yil, COUNT(*) FROM dosya WHERE yil IS NOT NULL GROUP BY yil ORDER BY yil")}
        d["boyut_gb"] = round((c.execute("SELECT SUM(boyut) FROM dosya").fetchone()[0] or 0) / 1e9, 1)
        d["cevrimdisi"] = c.execute("SELECT COUNT(*) FROM dosya WHERE cevrimdisi=1").fetchone()[0]
        r = c.execute("SELECT v FROM meta WHERE k='son_tam_tarama'").fetchone()
        d["son_tam_tarama"] = r[0] if r else None
    return d


def iyilestirilmis_yol(c, dosya_id: int) -> Path | None:
    """Dosyanın kullanıcı onayıyla seçilmiş (kullan=1) en yeni başarılı iyileştirilmiş sürümü (stüdyo kökü + göreli yol) ya da None."""
    r = c.execute("SELECT cikti_kok, cikti_yol FROM iyilestirme WHERE dosya_id=? AND durum='tamam' AND kullan=1 ORDER BY id DESC LIMIT 1", (dosya_id,)).fetchone()
    if not r or not r["cikti_yol"]:
        return None
    kok = ROOT if r["cikti_kok"] == "studyo" else None
    p = kok.joinpath(*r["cikti_yol"].split("/")) if kok else None
    return p if p and p.is_file() else None


def kopyala(idler: list[int], hedef: str, en_cok_gb: float = 8.0, video_en_cok_mb: float = 1500.0, iyilestirilmisi_kullan: bool = True) -> dict:
    """Dosyaları projeye KOPYALAR (arşiv yalnızca okunur). İyileştirilmiş sürümü olan fotoğraf için o kopyalanır (<ad>_iyi.<uzantı>)."""
    c = baglan()
    hedef_p = Path(hedef)
    kopyalanan, atlanan, toplam, iyi_n = [], [], 0, 0
    cap = en_cok_gb * 1e9
    for i in idler:
        r = c.execute("SELECT kok_id, yol, tur, boyut, ad FROM dosya WHERE id=?", (i,)).fetchone()
        if not r:
            continue
        src = mutlak(c, r["kok_id"], r["yol"])
        iyi = iyilestirilmis_yol(c, i) if (iyilestirilmisi_kullan and r["tur"] == "foto") else None
        if iyi:
            src, ad_hedef = iyi, f"{Path(r['ad']).stem}_iyi{iyi.suffix}"
        else:
            ad_hedef = r["ad"]
        if src is None:
            atlanan.append({"yol": r["yol"], "neden": "arşiv bu bilgisayarda bağlı değil"})
            continue
        if not src.is_file():
            atlanan.append({"yol": r["yol"], "neden": "arşivde bulunamadı"})
            continue
        boyut = src.stat().st_size if iyi else (r["boyut"] or 0)
        if r["tur"] == "video" and boyut > video_en_cok_mb * 1e6:
            atlanan.append({"yol": r["yol"], "neden": f"video {boyut // 1_000_000} MB > sınır {int(video_en_cok_mb)} MB"})
            continue
        if toplam + boyut > cap:
            atlanan.append({"yol": r["yol"], "neden": f"toplam sınır {en_cok_gb} GB aşılır"})
            continue
        klasor = hedef_p / ("foto" if r["tur"] == "foto" else r["tur"])
        klasor.mkdir(parents=True, exist_ok=True)
        dst = klasor / ad_hedef
        n = 2
        while dst.exists():
            dst = klasor / f"{Path(ad_hedef).stem}_{n}{Path(ad_hedef).suffix}"
            n += 1
        shutil.copy2(src, dst)  # arşiv dosyası yalnızca OKUNUR; kopya proje klasörüne gider
        toplam += boyut
        iyi_n += 1 if iyi else 0
        kopyalanan.append({"yol": r["yol"], "hedef": str(dst), "iyilestirilmis": bool(iyi)})
    return {"kopyalanan": len(kopyalanan), "iyilestirilmis": iyi_n, "atlanan": atlanan, "toplam_mb": round(toplam / 1e6, 1), "ayrinti": kopyalanan}


def ayarla_uzak(uzak: str, ad: str = "bulut", gorunen_ad: str | None = None) -> dict:
    """Bulut disk (Google Drive/OneDrive/Dropbox, rclone) klasörünü arşiv olarak ekle. Salt okunur; dosyalar gerektiğinde önbelleğe iner."""
    c = baglan()
    kid = K.uzak_ekle(c, ad, uzak, gorunen_ad)
    z = K.kok_coz(c, kid, True)
    return {"id": kid, "ad": ad, "uzak": uzak, "bagli": z["yol"] is not None, "not": z["not"], "tur_bilgi": {"ad": "bulut disk"}}


def ayarla(yol: str, ad: str = "arsiv", zorla: bool = False) -> dict:
    """Arşiv kökü ekle ya da bu bilgisayardaki yolunu güncelle. Aynı adlı arşivin kayıtlı dosyalarına BENZEMEYEN bir klasör verilirse
    reddedilir (yanlış diski göstermek dizini bozmasın); gerçekten başka içerikse zorla=True: eski dizin kayıtları silinir (dosyalara dokunulmaz)."""
    c = baglan()
    p = Path(yol).expanduser()
    if not K.klasor_var(p, 6):
        raise ValueError(f"klasör yok: {p} (harici disk takılı mı?)")
    kid = (c.execute("SELECT id FROM kok WHERE ad=?", (re.sub(r"[^a-z0-9_-]+", "-", ad.lower()).strip("-") or "arsiv",)).fetchone() or [None])[0]
    if kid:
        var, bak = K.ornek_dogrula(c, kid, Path(os.path.abspath(p)))
        if bak and var * 2 < bak:
            if not zorla:
                raise ValueError(f"bu klasör '{ad}' arşivinin kayıtlı dosyalarına benzemiyor (örnek {bak} dosyanın {var}'i var). "
                                 "Aynı arşivin taşınmış hali değilse yeni bir arşiv olarak (farklı adla) ekle; gerçekten bu arşivin yeni hali ise zorla onayla (eski dizin kayıtları silinir).")
            K.kok_sil(c, kid)
    kid = K.kok_ekle(c, ad, str(p), "arsiv", None)
    K._onbellek.pop(kid, None)
    z = K.kok_coz(c, kid, True)
    return {"id": kid, "ad": ad, "yol": str(z["yol"]) if z["yol"] else None, "tur_bilgi": K.tur_tespit(str(p))}


def onizleme(dosya_id: int, en: int = 360):
    """Fotoğraf küçük resmi (JPEG bayt) ya da None. Arşiv bağlı değilse None. Bulutta-yalnızca dosya indirilmesin diye atlanır."""
    c = baglan()
    r = c.execute("SELECT kok_id, yol, tur, cevrimdisi FROM dosya WHERE id=?", (dosya_id,)).fetchone()
    if not r or r["tur"] != "foto" or r["cevrimdisi"]:
        return None
    yol = mutlak(c, r["kok_id"], r["yol"])
    if yol is None:
        return None
    try:
        import io
        from PIL import Image, ImageOps
        with Image.open(yol) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((en, en))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=80)
            return b.getvalue()
    except Exception:
        return None


# ------------------------------------------------------------------ komut satırı
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    s = sp.add_parser("ayarla")
    s.add_argument("yol")
    s.add_argument("--ad", default="arsiv")
    s.add_argument("--zorla", action="store_true")
    sp.add_parser("kokler")
    sp.add_parser("durum")
    t = sp.add_parser("tara")
    t.add_argument("--derin", action="store_true")
    t.add_argument("--ad")
    y = sp.add_parser("yapi")
    y.add_argument("--derinlik", type=int, default=2)
    for ad in ("projeler", "ara"):
        q = sp.add_parser(ad)
        q.add_argument("--yil")
        q.add_argument("--tur")
        q.add_argument("--kelime")
        q.add_argument("--json", action="store_true")
        q.add_argument("--ad", help="yalnız bu arşiv")
        if ad == "projeler":
            q.add_argument("--derinlik", type=int, default=1)
        else:
            q.add_argument("--klasor")
            q.add_argument("--limit", type=int, default=200)
    b = sp.add_parser("bul", help="dosyayı adıyla bul (ve istenirse projeye ekle)")
    b.add_argument("ifade")
    b.add_argument("--tur")
    b.add_argument("--ad", help="yalnız bu arşiv")
    b.add_argument("--limit", type=int, default=8)
    b.add_argument("--kopyala", metavar="PROJE_KLASORU", help="projeler/<ad>: net tek eşleşme varsa kaynak/ altına kopyalar")
    b.add_argument("--id", type=int, help="aday listesinden seçilen dosya kimliği (--kopyala ile)")
    k = sp.add_parser("kopyala")
    k.add_argument("--idler", required=True)
    k.add_argument("--hedef", required=True)
    k.add_argument("--en-cok-gb", type=float, default=8.0)
    k.add_argument("--video-en-cok-mb", type=float, default=1500.0)
    k.add_argument("--orijinal", action="store_true", help="iyileştirilmiş sürüm varsa bile orijinali kopyala")
    a = ap.parse_args()

    def kid_ad(ad):
        if not ad:
            return None
        r = baglan().execute("SELECT id FROM kok WHERE ad=?", (ad,)).fetchone()
        if not r:
            sys.exit(f"böyle bir arşiv yok: {ad}")
        return r[0]
    if a.k == "ayarla":
        try:
            r = ayarla(a.yol, a.ad, a.zorla)
        except ValueError as e:
            sys.exit(str(e))
        print(f"arşiv ayarlandı: {r['ad']} → {r['yol']}  ({r['tur_bilgi']['ad']})")
        print("Sıradaki adım:  python sistem/arsiv/arsiv.py tara")
    elif a.k == "kokler":
        for r in K.kok_listesi(baglan()):
            print(f"[{r['id']}] {r['ad']:10} {r['tur']:7} {'BAĞLI ' if r['bagli'] else 'YOK   '} {r['yol'] or '-'}  ({r['yontem'] or r['not']})  dosya={r.get('dosya', '-')}")
    elif a.k == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
    elif a.k == "tara":
        r = tara(derin=a.derin, kok_id=kid_ad(a.ad))
        print(json.dumps(r, ensure_ascii=False))
    elif a.k == "yapi":
        for r in yapi(a.derinlik):
            print(f"{r['dosya']:7} {r['klasor']}")
    elif a.k == "projeler":
        r = projeler(a.derinlik, a.yil, a.tur, a.kelime, kok_id=kid_ad(a.ad))
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            for g in r:
                yl = f"{g['yil_min']}-{g['yil_max']}" if g["yil_min"] != g["yil_max"] else str(g["yil_min"])
                print(f"{yl:10} foto {g['foto']:4} video {g['video']:3} belge {g['belge']:3} {g['boyut'] / 1e6:8.0f} MB  {g['proje']}")
    elif a.k == "ara":
        r = ara(a.yil, a.tur, a.kelime, a.klasor, a.limit, kok_id=kid_ad(a.ad))
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            for f in r:
                sure = f" {int(f['sure'] // 60)}:{int(f['sure'] % 60):02d}" if f.get("sure") else ""
                print(f"{f['id']:7} {f['yil'] or '----'} {TUR_ETIKET.get(f['tur'], f['tur']):6}{sure} {f['yol']}")
            print(f"{len(r)} sonuç")
    elif a.k == "bul":
        adaylar = bul(a.ifade, a.tur, a.limit, kok_id=kid_ad(a.ad))
        sec = None
        if a.id:
            sec = next((x for x in adaylar if x["id"] == a.id), None) or {"id": a.id}
        elif adaylar and adaylar[0]["tam"] and (len(adaylar) == 1 or not adaylar[1]["tam"]):
            sec = adaylar[0]
        sonuc = {"adaylar": [{k2: x[k2] for k2 in ("id", "kategori", "ad", "klasor", "arsiv", "sure", "puan", "tam", "cevrimdisi")} for x in adaylar]}
        if a.kopyala and sec:
            sonuc["eklenen"] = projeye_ekle(a.kopyala, sec["id"])
        elif a.kopyala:
            sonuc["not"] = "net tek eşleşme yok: kullanıcıya adayları göster (ya da --id ile seç)" if adaylar else "eşleşme yok: kullanıcıya sor (arşivi taramak ya da adı düzeltmek gerekebilir)"
        print(json.dumps(sonuc, ensure_ascii=False, indent=1))
        return 0 if (adaylar and (sec or not a.kopyala)) else 3
    elif a.k == "kopyala":
        r = kopyala([int(x) for x in a.idler.split(",") if x.strip()], a.hedef, a.en_cok_gb, a.video_en_cok_mb, not a.orijinal)
        print(json.dumps({k: v for k, v in r.items() if k != "ayrinti"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
