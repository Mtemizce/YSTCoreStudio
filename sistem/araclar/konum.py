#!/usr/bin/env python3
"""Konum çözümleme: klasör nerede olursa olsun çalışsın (taşınabilirlik çekirdeği).

İlke: veritabanında ve proje dosyalarında MUTLAK yol tutulmaz. Her kayıt  (kök adı + göreli yol)  olarak durur;
mutlak yol çalışırken "kök" + "göreli yol" birleştirilerek bulunur. Kökler iki türdür:
  studyo : bu klasörün kendisi (Başlat.cmd her açılışta bulunduğu yeri algılayıp günceller; elle bir şey yapılmaz)
  arsiv  : arşiv klasörleri (harici disk, ağ, Google Drive/OneDrive eşitleme klasörü). Otomatik BULUNAMAYAN tek şey budur.

Bir arşiv kökü bu bilgisayarda şu sırayla aranır (ilk doğrulanan kazanır):
  1. ortam değişkeni  YST_<AD> (örn. YST_ARSIV=D:\\Arsiv)            elle belirleme
  2. bu bilgisayar için kayıtlı yol (bilgisayar adıyla saklanır)
  3. başka bilgisayarda kaydedilmiş yol (aynı yerdeyse; klasör kopyalanıp taşındığında)
  4. aynı disk (birim seri numarası) → sürücü harfi değişmiş olabilir
  5. tüm sürücülerde aynı alt yol / aynı klasör adı
  6. bulunamazsa None → panel "Ayarlar → Konumlar → Gözat" ile sorar
"Doğrulama": dizindeki bilinen dosyalardan örnek alınıp o klasörde gerçekten var mı diye bakılır (yanlış klasörü sessizce kabul etmemek için).

  python sistem/araclar/konum.py durum                 kökler ve bu bilgisayardaki çözümlemeleri
  python sistem/araclar/konum.py denetle [--duzelt]     mutlak yol (yalnızca eski kök) kalmış mı diye proje/ayar dosyalarını tarar
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import re
import socket
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORTAM = ROOT / "sistem" / "ortam"
YEREL = ORTAM / "yerel"
DAMGA = YEREL / "konum.json"
SEMA_SURUMU = 3

# Windows dosya öznitelikleri: bulutta-yalnızca (içeriği açınca indirilir) dosyalar
ATTR_OFFLINE = 0x1000
ATTR_RECALL_OPEN = 0x40000
ATTR_RECALL_DATA = 0x400000
BULUT_KLASOR_IPUCU = ("google drive", "googledrive", "drive'ım", "drive'im", "my drive", "onedrive", "dropbox", "icloud", "yandex.disk", "mega")


def makine() -> str:
    return (os.environ.get("YST_MAKINE") or socket.gethostname() or "bilinmeyen").strip().lower()


# ------------------------------------------------------------------ sürücü / disk bilgisi
def _zamanli(fn, zaman: float = 4.0, varsayilan=None):
    """Kopuk ağ sürücüsü/yanıtsız disk dakikalarca takılabilir: zaman aşımıyla sor."""
    sonuc = [varsayilan]

    def is_():
        try:
            sonuc[0] = fn()
        except OSError:
            pass

    t = threading.Thread(target=is_, daemon=True)
    t.start()
    t.join(zaman)
    return sonuc[0]


def klasor_var(p, zaman: float = 4.0) -> bool:
    return bool(_zamanli(lambda: os.path.isdir(p), zaman, False))


def suruculer() -> list[str]:
    if os.name != "nt":
        return [x for x in ("/", "/mnt", "/media", "/Volumes") if os.path.isdir(x)]
    if hasattr(os, "listdrives"):
        try:
            return list(os.listdrives())
        except OSError:
            pass
    out = []
    for h in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        d = f"{h}:\\"
        if _zamanli(lambda d=d: os.path.exists(d), 1.5, False):
            out.append(d)
    return out


def birim_bilgi(yol: str) -> dict:
    """{'etiket','seri','tur'}: tur = yerel|harici|ag|cd|bilinmiyor. Windows dışında yalnızca tur."""
    d = {"etiket": None, "seri": None, "tur": "bilinmiyor", "fs": None}
    if os.name != "nt":
        return d
    yol = os.path.abspath(str(yol))
    if yol.startswith("\\\\"):
        d["tur"] = "ag"
        return d
    kok = os.path.splitdrive(yol)[0] + "\\"
    try:
        k32 = ctypes.windll.kernel32
        t = k32.GetDriveTypeW(kok)  # 2 çıkarılabilir, 3 sabit, 4 ağ, 5 cd
        d["tur"] = {2: "harici", 3: "yerel", 4: "ag", 5: "cd"}.get(t, "bilinmiyor")
        etiket = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        seri = ctypes.c_uint32()
        if k32.GetVolumeInformationW(kok, etiket, 261, ctypes.byref(seri), None, None, fs, 261):
            d["etiket"], d["seri"], d["fs"] = etiket.value, int(seri.value), fs.value
    except OSError:
        pass
    return d


def tur_tespit(yol: str) -> dict:
    """Arşiv türü (yalnızca bilgi için): disk / ağ / bulut eşitleme klasörü. Adaptör hepsini 'klasör' olarak okur."""
    b = birim_bilgi(yol)
    kucuk = str(yol).lower()
    etiket = (b.get("etiket") or "").lower()
    bulut = next((k for k in BULUT_KLASOR_IPUCU if k in kucuk or k in etiket), None)
    if bulut:
        ad = {"google drive": "Google Drive", "googledrive": "Google Drive", "drive'ım": "Google Drive", "drive'im": "Google Drive", "my drive": "Google Drive",
              "onedrive": "OneDrive", "dropbox": "Dropbox", "icloud": "iCloud Drive"}.get(bulut, bulut)
        return {"tur": "bulut-esitleme", "ad": ad, "not": "bulutta-yalnızca dosyalar okunurken indirilir; tarama içerik okumadan yapılır"}
    ad = {"ag": "ağ paylaşımı", "harici": "harici/çıkarılabilir disk", "yerel": "yerel disk", "cd": "optik sürücü"}.get(b["tur"], "klasör")
    return {"tur": b["tur"], "ad": ad, "not": ""}


def bulutta_mi(st) -> bool:
    """Dosyanın içeriği yerelde değil mi (OneDrive/Drive 'çevrimdışı değil' yer tutucu)? os.stat sonucundan."""
    a = getattr(st, "st_file_attributes", 0)
    return bool(a & (ATTR_OFFLINE | ATTR_RECALL_OPEN | ATTR_RECALL_DATA))


# ------------------------------------------------------------------ veritabanı şeması (arsiv.db)
DDL_V3 = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS kok (
  id INTEGER PRIMARY KEY, ad TEXT UNIQUE NOT NULL, tur TEXT NOT NULL DEFAULT 'arsiv', gorunen_ad TEXT,
  adaptor TEXT NOT NULL DEFAULT 'klasor', uzak TEXT, son_tarama TEXT, olusturma TEXT);
CREATE TABLE IF NOT EXISTS kok_yol (
  kok_id INTEGER NOT NULL REFERENCES kok(id) ON DELETE CASCADE, makine TEXT NOT NULL, yol TEXT NOT NULL,
  seri INTEGER, etiket TEXT, alt TEXT, surucu_turu TEXT, son_dogrulama REAL, PRIMARY KEY (kok_id, makine));
CREATE TABLE IF NOT EXISTS dosya (
  id INTEGER PRIMARY KEY, kok_id INTEGER NOT NULL DEFAULT 1, yol TEXT NOT NULL, klasor TEXT, ad TEXT, uzanti TEXT, tur TEXT,
  boyut INTEGER, mtime REAL, yil INTEGER, ay INTEGER, tarih_kaynagi TEXT,
  genislik INTEGER, yukseklik INTEGER, sure REAL, etiket TEXT, goruldu REAL, cevrimdisi INTEGER NOT NULL DEFAULT 0,
  UNIQUE (kok_id, yol));
CREATE INDEX IF NOT EXISTS ix_yil ON dosya(yil);
CREATE INDEX IF NOT EXISTS ix_tur ON dosya(tur);
CREATE INDEX IF NOT EXISTS ix_klasor ON dosya(klasor);
CREATE TABLE IF NOT EXISTS analiz (
  kok_id INTEGER NOT NULL DEFAULT 1, yol TEXT NOT NULL, boyut INTEGER, mtime REAL,
  keskinlik REAL, parlaklik REAL, dhash TEXT, kopya_of TEXT,
  oto_kullanilabilir INTEGER, oto_puan REAL, oto_neden TEXT, oto_tarih TEXT,
  c_kullanilabilir INTEGER, c_puan REAL, c_neden TEXT, asama TEXT, konu TEXT, aciklama TEXT, etiketler TEXT, c_tarih TEXT,
  PRIMARY KEY (kok_id, yol));
CREATE INDEX IF NOT EXISTS ix_analiz_asama ON analiz(asama);
CREATE TABLE IF NOT EXISTS proje_notu (kok_id INTEGER NOT NULL DEFAULT 1, klasor TEXT NOT NULL, ozet TEXT, tur TEXT, tarih TEXT, PRIMARY KEY (kok_id, klasor));
CREATE TABLE IF NOT EXISTS iyilestirme (
  id INTEGER PRIMARY KEY, dosya_id INTEGER NOT NULL, model TEXT NOT NULL, saglayici TEXT, parametre TEXT,
  cikti_kok TEXT NOT NULL DEFAULT 'studyo', cikti_yol TEXT, genislik INTEGER, yukseklik INTEGER,
  onceki_keskin REAL, sonraki_keskin REAL, onceki_puan REAL, sonraki_puan REAL, sonraki_kullanilabilir INTEGER,
  durum TEXT NOT NULL DEFAULT 'bekliyor', hata TEXT, tarih TEXT, kullan INTEGER NOT NULL DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_iyi_dosya ON iyilestirme(dosya_id);
"""


def _tablo_var(c, ad: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (ad,)).fetchone() is not None


def _kolonlar(c, ad: str) -> set[str]:
    return {r[1] for r in c.execute(f"PRAGMA table_info({ad})")}


def sema_kur(c: sqlite3.Connection, eski_ayar: Path | None = None) -> None:
    """Şemayı kurar ya da eski sürümden yükseltir (veri kaybı olmadan). PRAGMA user_version = SEMA_SURUMU."""
    if _tablo_var(c, "kok") and "uzak" not in _kolonlar(c, "kok"):  # bulut disk (rclone) arşivleri için: uzak = 'hesap:klasör'
        c.execute("ALTER TABLE kok ADD COLUMN uzak TEXT")
        c.commit()
    v = c.execute("PRAGMA user_version").fetchone()[0]
    if v >= SEMA_SURUMU:
        return
    eski_var = _tablo_var(c, "dosya") and "kok_id" not in _kolonlar(c, "dosya")
    if eski_var:  # v1 → v3: tabloları kok_id'li biçime yeniden kur, kimlikleri (id) koru
        c.execute("BEGIN")
        for t in ("dosya", "analiz", "proje_notu"):
            if _tablo_var(c, t):
                c.execute(f"ALTER TABLE {t} RENAME TO {t}_v1")
        for ix in ("ix_yil", "ix_tur", "ix_klasor", "ix_analiz_asama"):
            c.execute(f"DROP INDEX IF EXISTS {ix}")
        c.commit()
    c.executescript(DDL_V3)
    if eski_var:
        kol_d = ("id", "yol", "klasor", "ad", "uzanti", "tur", "boyut", "mtime", "yil", "ay", "tarih_kaynagi", "genislik", "yukseklik", "sure", "etiket", "goruldu")
        c.execute(f"INSERT INTO dosya(kok_id,{','.join(kol_d)}) SELECT 1,{','.join(kol_d)} FROM dosya_v1")
        c.execute("DROP TABLE dosya_v1")
        if _tablo_var(c, "analiz_v1"):
            kol_a = [k for k in _kolonlar(c, "analiz") if k != "kok_id"]
            ortak = [k for k in kol_a if k in _kolonlar(c, "analiz_v1")]
            c.execute(f"INSERT OR IGNORE INTO analiz(kok_id,{','.join(ortak)}) SELECT 1,{','.join(ortak)} FROM analiz_v1")
            c.execute("DROP TABLE analiz_v1")
        if _tablo_var(c, "proje_notu_v1"):
            c.execute("INSERT OR IGNORE INTO proje_notu(kok_id,klasor,ozet,tur,tarih) SELECT 1,klasor,ozet,tur,tarih FROM proje_notu_v1")
            c.execute("DROP TABLE proje_notu_v1")
        # eski ayar.json (tek arşiv, mutlak yol) → kok + bu bilgisayarın yolu
        a = {}
        try:
            a = json.loads(eski_ayar.read_text(encoding="utf-8")) if eski_ayar else {}
        except (OSError, ValueError):
            pass
        c.execute("INSERT OR IGNORE INTO kok(id,ad,tur,gorunen_ad,olusturma) VALUES (1,'arsiv','arsiv','Arşiv',?)", (time.strftime("%Y-%m-%d %H:%M"),))
        if a.get("kok"):
            c.execute("INSERT OR REPLACE INTO kok_yol(kok_id,makine,yol,seri,etiket,alt,son_dogrulama) VALUES (1,?,?,?,?,?,?)",
                      (makine(), a["kok"], a.get("seri"), a.get("etiket"), a.get("alt"), None))
    else:
        # eski ayar.json yalnız v1 veritabanı olmayan kurulumda (hiç tarama yapılmamış) da taşınır
        try:
            a = json.loads(eski_ayar.read_text(encoding="utf-8")) if eski_ayar and eski_ayar.exists() else {}
        except (OSError, ValueError):
            a = {}
        if a.get("kok") and not c.execute("SELECT 1 FROM kok").fetchone():
            c.execute("INSERT INTO kok(id,ad,tur,gorunen_ad,olusturma) VALUES (1,'arsiv','arsiv','Arşiv',?)", (time.strftime("%Y-%m-%d %H:%M"),))
            c.execute("INSERT OR REPLACE INTO kok_yol(kok_id,makine,yol,seri,etiket,alt) VALUES (1,?,?,?,?,?)", (makine(), a["kok"], a.get("seri"), a.get("etiket"), a.get("alt")))
    c.execute("INSERT OR REPLACE INTO meta VALUES ('sema_surumu', ?)", (str(SEMA_SURUMU),))
    c.execute(f"PRAGMA user_version={SEMA_SURUMU}")
    c.commit()


# ------------------------------------------------------------------ kök kayıtları
def env_adi(ad: str) -> str:
    return "YST_" + re.sub(r"[^A-Z0-9]+", "_", ad.upper()).strip("_")


def alt_yol(yol: Path | str) -> str:
    """Sürücü kökünden sonraki parça (taşınabilir ipucu): D:\\Is\\Arsiv → Is/Arsiv ; UNC için sunucu/paylaşım sonrası."""
    s = os.path.abspath(str(yol))
    if os.name == "nt":
        s = os.path.splitdrive(s)[1] if not s.startswith("\\\\") else "\\".join(s.split("\\")[4:])
    return s.strip("\\/").replace("\\", "/")


def kok_ekle(c, ad: str, yol: str, tur: str = "arsiv", gorunen_ad: str | None = None) -> int:
    """Kök oluştur (varsa yolu güncelle) ve BU bilgisayarın yolunu kaydet. Klasör yoksa ValueError."""
    ad = re.sub(r"[^a-z0-9_-]+", "-", (ad or "arsiv").lower()).strip("-") or "arsiv"
    p = Path(yol).expanduser()
    if not klasor_var(p, 6):
        raise ValueError(f"klasör yok ya da erişilemiyor: {p} (harici disk/ağ bağlı mı?)")
    p = Path(os.path.abspath(p))
    r = c.execute("SELECT id FROM kok WHERE ad=?", (ad,)).fetchone()
    if r:
        kid = r[0]
        if gorunen_ad:
            c.execute("UPDATE kok SET gorunen_ad=? WHERE id=?", (gorunen_ad, kid))
    else:
        kid = c.execute("INSERT INTO kok(ad,tur,gorunen_ad,adaptor,olusturma) VALUES (?,?,?,?,?)",
                        (ad, tur, gorunen_ad or ad, "klasor", time.strftime("%Y-%m-%d %H:%M"))).lastrowid
    _yol_yaz(c, kid, p)
    c.commit()
    return kid


def _yol_yaz(c, kid: int, p: Path) -> None:
    b = birim_bilgi(str(p))
    c.execute("INSERT OR REPLACE INTO kok_yol(kok_id,makine,yol,seri,etiket,alt,surucu_turu,son_dogrulama) VALUES (?,?,?,?,?,?,?,?)",
              (kid, makine(), str(p), b["seri"], b["etiket"], alt_yol(p), b["tur"], time.time()))


def kok_sil(c, kid: int) -> int:
    """Kökü ve onun dizin kayıtlarını siler (DOSYALARA DOKUNULMAZ: yalnızca veritabanı). Silinen dosya kaydı sayısı."""
    n = c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0]
    for r in c.execute("SELECT id FROM dosya WHERE kok_id=?", (kid,)).fetchall():
        c.execute("DELETE FROM iyilestirme WHERE dosya_id=?", (r[0],))
        try:
            c.execute("DELETE FROM dosya_fts WHERE rowid=?", (r[0],))
        except sqlite3.OperationalError:
            pass
    for t in ("dosya", "analiz", "proje_notu"):
        c.execute(f"DELETE FROM {t} WHERE kok_id=?", (kid,))
    c.execute("DELETE FROM kok_yol WHERE kok_id=?", (kid,))
    c.execute("DELETE FROM kok WHERE id=?", (kid,))
    c.commit()
    return n


def ornek_dogrula(c, kid: int, p: Path, en_cok: int = 8) -> tuple[int, int]:
    """Dizindeki bilinen dosyalardan örnek al, p altında var mı say → (bulunan, bakılan). Kayıt yoksa (0, 0)."""
    n = c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0]
    if not n:
        return 0, 0
    ofs = sorted(random.sample(range(n), min(en_cok, n)))
    var = bak = 0
    for o in ofs:
        r = c.execute("SELECT yol FROM dosya WHERE kok_id=? LIMIT 1 OFFSET ?", (kid, o)).fetchone()
        bak += 1
        if _zamanli(lambda y=r[0]: os.path.exists(os.path.join(str(p), *y.split("/"))), 4.0, False):
            var += 1
    return var, bak


def _uygun_mu(c, kid: int, p: Path) -> bool:
    var, bak = ornek_dogrula(c, kid, p)
    return bak == 0 or var * 2 >= bak  # en az yarısı bulunmalı


_onbellek: dict[int, tuple[float, dict]] = {}


def kok_coz(c, kid: int, yeniden: bool = False) -> dict:
    """Kökün BU bilgisayardaki yolu: {'yol': Path|None, 'yontem': ..., 'not': ...}. Bulursa bu bilgisayarın kaydını günceller."""
    simdi = time.time()
    if not yeniden and kid in _onbellek and simdi - _onbellek[kid][0] < _onbellek[kid][1].get("ttl", 15):  # bulunamayan kök de 15 sn önbellekte: panel her 2 sn'de sorarken tüm sürücüleri taramasın
        return _onbellek[kid][1]
    r = c.execute("SELECT ad, tur FROM kok WHERE id=?", (kid,)).fetchone()
    if not r:
        return {"yol": None, "yontem": None, "not": "kök kaydı yok"}
    ad, tur = r
    sonuc = _coz(c, kid, ad, tur)
    _onbellek[kid] = (simdi, sonuc)
    return sonuc


def _bd():
    import importlib.util as _u
    if "yst_bulut_disk" not in sys.modules:
        sp = _u.spec_from_file_location("yst_bulut_disk", Path(__file__).with_name("bulut_disk.py"))
        m = _u.module_from_spec(sp)
        sys.modules["yst_bulut_disk"] = m
        sp.loader.exec_module(m)
    return sys.modules["yst_bulut_disk"]


def _coz_uzak(ad: str, uzak: str) -> dict:
    """Bulut disk (rclone) arşivi: 'yol' = yerel ÖNBELLEK klasörü; dosyalar gerektiğinde oraya iner."""
    bd = _bd()
    if not bd.rclone():
        return {"ttl": 3, "yol": None, "yontem": None, "not": "rclone kurulu değil: Ayarlar → Konumlar → Bulut disk"}
    hesap = uzak.split(":", 1)[0] + ":"
    if hesap not in bd.uzaklar_liste():
        return {"ttl": 3, "yol": None, "yontem": None, "not": f"'{hesap[:-1]}' hesabı bu bilgisayarda bağlı değil: Ayarlar → Konumlar → Bulut disk → Hesap bağla"}
    return {"ttl": 3, "yol": bd.onbellek_yolu(ad), "yontem": "rclone", "not": f"{uzak} (bulut, salt okunur; dosyalar gerektiğinde önbelleğe iner)"}


def _coz(c, kid: int, ad: str, tur: str) -> dict:
    ad_uzak = c.execute("SELECT adaptor, uzak FROM kok WHERE id=?", (kid,)).fetchone()
    if ad_uzak and ad_uzak[0] == "rclone" and ad_uzak[1]:
        return _coz_uzak(ad, ad_uzak[1])
    ben = makine()
    # 1) ortam değişkeni (elle)
    ev = os.environ.get(env_adi(ad))
    if ev:
        if klasor_var(ev, 6):
            return {"yol": Path(os.path.abspath(ev)), "yontem": "ortam-degiskeni", "not": f"{env_adi(ad)} ile belirlendi"}
        return {"yol": None, "yontem": "ortam-degiskeni", "not": f"{env_adi(ad)}={ev} bulunamadı"}
    if tur == "studyo":
        return {"yol": ROOT, "yontem": "otomatik", "not": "bu klasör"}
    satirlar = c.execute("SELECT makine, yol, seri, etiket, alt FROM kok_yol WHERE kok_id=?", (kid,)).fetchall()
    kendi = [s for s in satirlar if s[0] == ben]
    digerleri = [s for s in satirlar if s[0] != ben]
    # 2) bu bilgisayar için kayıtlı yol
    for _, yol, *_ in kendi:
        if klasor_var(yol, 6):
            if _uygun_mu(c, kid, Path(yol)):
                return {"yol": Path(yol), "yontem": "kayit", "not": ""}
            return {"yol": None, "yontem": "kayit", "not": f"{yol} bulundu ama kayıtlı arşivdeki dosyalara benzemiyor (yanlış klasör/disk?)"}
    # 3) başka bilgisayarda kaydedilen yol aynı yerdeyse
    for _, yol, *_ in digerleri:
        if klasor_var(yol, 4) and _uygun_mu(c, kid, Path(yol)):
            _yol_yaz(c, kid, Path(yol))
            c.commit()
            return {"yol": Path(yol), "yontem": "baska-bilgisayar-yolu", "not": "başka bilgisayarın kaydı bu bilgisayarda da geçerliydi"}
    # 4) aynı birim seri numarası: sürücü harfi değişmiş olabilir
    surucu = suruculer()
    seriler = {s[2]: s for s in satirlar if s[2]}
    if seriler and os.name == "nt":
        for d in surucu:
            seri = birim_bilgi(d)["seri"]
            if seri in seriler:
                alt = seriler[seri][4] or ""
                aday = Path(d) / alt if alt else Path(d)
                if klasor_var(aday, 4) and _uygun_mu(c, kid, aday):
                    _yol_yaz(c, kid, aday)
                    c.commit()
                    return {"yol": aday, "yontem": "disk-seri-no", "not": f"aynı disk {d} olarak takılı"}
    # 5) tüm sürücülerde aynı alt yol / aynı klasör adı
    ipuclari = []
    for s in satirlar:
        if s[4]:
            ipuclari.append(s[4])
        son = os.path.basename(str(s[1]).rstrip("\\/"))
        if son:
            ipuclari.append(son)
    for d in surucu:
        for ip in dict.fromkeys(ipuclari):
            aday = Path(d) / ip
            if klasor_var(aday, 2) and _uygun_mu(c, kid, aday):
                _yol_yaz(c, kid, aday)
                c.commit()
                return {"yol": aday, "yontem": "surucu-taramasi", "not": f"{aday} bulundu"}
    return {"yol": None, "yontem": None, "not": "bu bilgisayarda bulunamadı: Ayarlar → Konumlar → Gözat ile göster (ya da " + env_adi(ad) + " ortam değişkeni)"}


def uzak_ekle(c, ad: str, uzak: str, gorunen_ad: str | None = None) -> int:
    """Bulut disk arşivi ekle (rclone 'hesap:klasör'). Hesap bağlı değilse ValueError."""
    ad = re.sub(r"[^a-z0-9_-]+", "-", (ad or "bulut").lower()).strip("-") or "bulut"
    bd = _bd()
    bd.uzak_kontrol(uzak)
    if uzak.split(":", 1)[0] + ":" not in bd.uzaklar_liste():
        raise ValueError(f"'{uzak.split(':', 1)[0]}' hesabı bağlı değil (önce Hesap bağla)")
    r = c.execute("SELECT id FROM kok WHERE ad=?", (ad,)).fetchone()
    if r:
        kid = r[0]
        c.execute("UPDATE kok SET adaptor='rclone', uzak=?, gorunen_ad=COALESCE(?, gorunen_ad) WHERE id=?", (uzak, gorunen_ad, kid))
    else:
        kid = c.execute("INSERT INTO kok(ad,tur,gorunen_ad,adaptor,uzak,olusturma) VALUES (?,?,?,?,?,?)",
                        (ad, "arsiv", gorunen_ad or ad, "rclone", uzak, time.strftime("%Y-%m-%d %H:%M"))).lastrowid
    c.commit()
    _onbellek.pop(kid, None)
    return kid


def mutlak(c, kid: int, yol_rel: str) -> Path | None:
    """(kök, göreli yol) → bu bilgisayardaki mutlak yol. Kök bulunamazsa None. Bulut disk arşivinde dosya gerekirse önbelleğe indirilir (None: indirilemedi)."""
    k = kok_coz(c, kid)["yol"]
    uz = c.execute("SELECT adaptor, uzak, ad FROM kok WHERE id=?", (kid,)).fetchone()
    if k and uz and uz[0] == "rclone" and yol_rel:
        try:
            return _bd().getir(uz[1], yol_rel, uz[2])
        except (RuntimeError, ValueError, OSError):
            return None
    return (k.joinpath(*yol_rel.split("/")) if yol_rel else k) if k else None


def studyo_guncelle(c) -> dict:
    """Başlat.cmd her açılışta çağırır: bu klasörün şimdiki yerini 'studyo' kökü olarak bu bilgisayar adına yazar."""
    r = c.execute("SELECT id FROM kok WHERE ad='studyo'").fetchone()
    if r:
        kid = r[0]
    else:
        kid = c.execute("INSERT INTO kok(ad,tur,gorunen_ad,olusturma) VALUES ('studyo','studyo','Stüdyo klasörü',?)", (time.strftime("%Y-%m-%d %H:%M"),)).lastrowid
    eski = c.execute("SELECT yol FROM kok_yol WHERE kok_id=? AND makine=?", (kid, makine())).fetchone()
    _yol_yaz(c, kid, ROOT)
    c.commit()
    return {"onceki": eski[0] if eski else None, "simdi": str(ROOT), "degisti": bool(eski) and os.path.normcase(eski[0]) != os.path.normcase(str(ROOT))}


def kok_listesi(c) -> list[dict]:
    out = []
    for kid, ad, tur, gad, adaptor, st, uzak in c.execute("SELECT id, ad, tur, gorunen_ad, adaptor, son_tarama, uzak FROM kok ORDER BY (tur='studyo') DESC, id").fetchall():
        z = kok_coz(c, kid)
        d = {"id": kid, "ad": ad, "tur": tur, "gorunen_ad": gad, "adaptor": adaptor, "son_tarama": st, "env": env_adi(ad),
             "bagli": z["yol"] is not None, "yol": str(z["yol"]) if z["yol"] else None, "yontem": z["yontem"], "not": z["not"], "uzak": uzak}
        kayit = c.execute("SELECT yol, makine FROM kok_yol WHERE kok_id=? ORDER BY (makine=?) DESC", (kid, makine())).fetchone()
        d["kayitli_yol"] = kayit[0] if kayit else None
        d["kayitli_makine"] = kayit[1] if kayit else None
        if tur == "arsiv":
            d["dosya"] = c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0]
            if adaptor == "rclone":
                d["tur_bilgi"] = {"tur": "bulut-disk", "ad": "bulut disk (" + (uzak or "") + ")", "not": "salt okunur; tarama yalnızca liste alır, dosyalar analiz/önizleme/kopyalama sırasında önbelleğe iner"}
            elif z["yol"]:
                d["tur_bilgi"] = tur_tespit(str(z["yol"]))
        out.append(d)
    return out


# ------------------------------------------------------------------ klasör seçici (panel "Gözat")
def gozat(yol: str | None) -> dict:
    """Panelin klasör seçicisi için: yol boşsa sürücüler; değilse alt KLASÖRLER (dosya içeriği ya da adı dönmez)."""
    if not yol:
        satir = []
        for d in suruculer():
            b = birim_bilgi(d)
            satir.append({"ad": d + ((" — " + b["etiket"]) if b.get("etiket") else ""), "yol": d, "tur": b["tur"]})
        ev = Path.home()
        for ad in ("Desktop", "Documents", "Downloads"):
            if (ev / ad).is_dir():
                satir.append({"ad": f"~ {ad}", "yol": str(ev / ad), "tur": "kisayol"})
        return {"yol": "", "ust": None, "girdiler": satir}
    p = Path(yol)
    if not klasor_var(p, 6):
        raise ValueError("klasör bulunamadı")
    p = Path(os.path.abspath(p))
    girdiler = []

    def listele():
        with os.scandir(p) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False) and not e.name.startswith("$") and e.name.lower() not in ("system volume information", "$recycle.bin"):
                        girdiler.append({"ad": e.name, "yol": e.path})
                except OSError:
                    pass
        return True

    _zamanli(listele, 8.0, False)
    girdiler.sort(key=lambda g: g["ad"].lower())
    ust = str(p.parent) if p.parent != p else ""
    return {"yol": str(p), "ust": ust, "girdiler": girdiler[:800], "kesildi": len(girdiler) > 800}


# ------------------------------------------------------------------ taşınma denetimi
YOL_RE_WIN = re.compile(r"[A-Za-z]:[\\/]{1,2}(?:Users|users|Kullanıcılar)[\\/]{1,2}[^\\/\"'<>|\r\n]+")


def metin_dosyalar():
    """Taşınmada mutlak yol taşıyabilecek küçük metin dosyaları (venv/node_modules/.git/kurgu hariç)."""
    atla = {"venv", "node_modules", ".git", "kurgu", "modeller", "__pycache__", "analiz_sayfalari", "iyilestirilmis", "kaynak", "media", "out"}
    for taban in (ROOT / "projeler", ROOT / "kimlik", ORTAM / "kurgu-ayar", ORTAM / "baglayici", ORTAM / "arsiv", ROOT / "sistem" / "ayar"):
        if not taban.exists():
            continue
        for dp, dn, fn in os.walk(taban):
            dn[:] = [d for d in dn if d not in atla]
            for f in fn:
                if f.lower().endswith((".json", ".md", ".cmd", ".txt", ".cfg", ".ini", ".yml", ".yaml")):
                    p = Path(dp) / f
                    try:
                        if p.stat().st_size < 2_000_000:
                            yield p
                    except OSError:
                        pass


def _kalip(eski: str) -> list[str]:
    e = str(eski).rstrip("\\/")
    return list(dict.fromkeys([e, e.replace("\\", "/"), e.replace("\\", "\\\\")]))


def denetle(eski_kok: str | None = None, duzelt: bool = False) -> dict:
    """Dosyalarda ESKİ stüdyo kökü (taşıma öncesi yer) ya da bu kökün dışında kalmış 'C:\\Users\\…' benzeri mutlak yol var mı?
    --duzelt: eski kök metni yeni kökle değiştirilir (JSON'da çift ters eğik çizgi biçimi dahil)."""
    bulgu, duz = [], 0
    kaliplar = _kalip(eski_kok) if eski_kok else []
    yeni = str(ROOT)
    for p in metin_dosyalar():
        try:
            s = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hit = None
        for k in kaliplar:
            if k and k in s:
                hit = k
                break
        if hit is None:
            temiz = s
            for k in _kalip(str(ROOT)):  # bu klasörün kendi yolu sorun değil: çıkarıp geri kalanına bak
                temiz = temiz.replace(k, "<KOK>")
            m = YOL_RE_WIN.search(temiz)
            if m:
                bulgu.append({"dosya": str(p.relative_to(ROOT)), "ornek": m.group(0)[:80], "tur": "baska-yol"})
            continue
        if duzelt:
            for k in kaliplar:
                yeni_k = yeni.replace("\\", "/") if "/" in k and "\\" not in k else (yeni.replace("\\", "\\\\") if "\\\\" in k else yeni)
                s = s.replace(k, yeni_k)
            p.write_text(s, encoding="utf-8")
            duz += 1
        else:
            bulgu.append({"dosya": str(p.relative_to(ROOT)), "ornek": hit[:80], "tur": "eski-kok"})
    return {"bulgu": bulgu, "duzeltilen": duz}


def damga_oku() -> dict:
    try:
        return json.loads(DAMGA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def damga_yaz(ek: dict | None = None) -> None:
    YEREL.mkdir(parents=True, exist_ok=True)
    d = {**damga_oku(), "kok": str(ROOT), "makine": makine(), "zaman": time.strftime("%Y-%m-%d %H:%M:%S"), **(ek or {})}
    DAMGA.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ komut satırı
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(ROOT / "sistem" / "arsiv"))
    import arsiv as A
    k = sys.argv[1] if len(sys.argv) > 1 else "durum"
    if k == "durum":
        c = A.baglan()
        print(f"bilgisayar: {makine()}   stüdyo klasörü: {ROOT}")
        for r in kok_listesi(c):
            print(f"  [{r['id']}] {r['ad']:10} {r['tur']:7} {'BAĞLI ' if r['bagli'] else 'YOK   '} {r['yol'] or '-'}   ({r['yontem'] or r['not']})")
    elif k == "denetle":
        eski = (damga_oku().get("kok") if "--eski" not in sys.argv else sys.argv[sys.argv.index("--eski") + 1])
        r = denetle(eski if eski and os.path.normcase(eski) != os.path.normcase(str(ROOT)) else None, "--duzelt" in sys.argv)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
