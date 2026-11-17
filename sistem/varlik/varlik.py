"""Varlık kayıt defteri (SQLite): ses efektleri, müzik, modeller, yerel araçlar nereden geldi, nereye iner.

Depoda yalnızca `varliklar.db` (kayıtlar) bulunur; büyük/yeniden indirilebilir dosyalar (mp3, model ağırlığı, LibreDWG)
depoya KONMAZ. Kurulum `indir` ile eksikleri kaynağından getirir, sha256 doğrular.

Komutlar (depo kökünden; yalnızca Python standart kütüphanesi):
  python sistem/varlik/varlik.py liste [--tur sfx|muzik|model|arac|referans]
  python sistem/varlik/varlik.py indir [--tur ...]             eksik/bozuk olanları kaynağından getir (kurulum bunu çağırır)
  python sistem/varlik/varlik.py ekle --tur muzik --ad "Ad" --url https://... --hedef sistem/kit/muzik/ad.mp3 --lisans "..." [--lisans-url ...] [--not ...]
  python sistem/varlik/varlik.py durum                         hangileri yerelde var/yok/bozuk (sha256)
Kaynak türleri: npm (node_modules/<paket>/<yol> içinden kopya), url (HTTPS indirme; sha256 doğrulanır), zip-url (indir + aç),
git (sabit commit'ten klasör; commit sha'sı içeriği doğrular; sha256 sütununda commit tutulur), yerel (bu bilgisayara özel kendi dosyan;
başka bilgisayarda otomatik gelmez, durum 'yok' görünür ve bir UYARI verilir).
Müzik/SFX'i Pixabay vb. bir siteden kendin indirdiysen `ekle` ile URL'sini ve lisansını kaydet: sonraki kurulumlar otomatik indirir.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # depo kökü; DB'deki hedefler köke göredir
DB = Path(__file__).resolve().parent / "varliklar.db"
# Wikimedia gibi sunucular iletişim adresi (URL) içermeyen genel kimliğe 429 verir: projenin açık adresi kimliğe yazılır (kişisel veri değildir).
UA = "YSTCoreStudio/1.0 (https://github.com/Mtemizce/YSTCoreStudio; local setup tool) python-urllib"

SEMA = """
CREATE TABLE IF NOT EXISTS varlik (
  id TEXT PRIMARY KEY,          -- kisa, kararlı ad
  tur TEXT NOT NULL,            -- sfx | muzik | model | arac | referans
  ad TEXT NOT NULL,
  hedef TEXT NOT NULL,          -- depo köküne göre yerel yol (dosya ya da, zip-url için, klasör)
  kaynak_tur TEXT NOT NULL,     -- npm | url | zip-url
  kaynak TEXT NOT NULL,         -- npm: 'paket::yol'   url: https adresi
  sha256 TEXT,                  -- dosya (zip-url için: indirilen zip) karması
  boyut INTEGER,
  lisans TEXT,
  lisans_url TEXT,
  notlar TEXT,
  eklendi TEXT
);
"""


def baglan() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SEMA)
    return c


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


_SON_ISTEK: dict = {}
_ENGEL: dict = {}   # sunucu -> neden: hız sınırına/ulaşılamazlığa takılan sunucuya bu çalıştırmada bir daha istek atılmaz
BEKLE_EN_COK = 25   # sn: sunucu bundan kısa bir bekleme istiyorsa BİR kez beklenir; uzunsa vazgeçilir (kurulumu bekletme, sonra denenir)


class SunucuEngeli(Exception):
    """Sunucu hız sınırı/ulaşılamazlık: bu varlık ATLANIR (hata sayılmaz), sonra yeniden denenir."""


def _indir(url: str, hedef: Path) -> None:
    """Kibar ve SABIRSIZ indirme: aynı sunucuya art arda istekler arasında bekler; 429/503'te en çok BEKLE_EN_COK sn bir kez bekler, daha uzunsa
    SunucuEngeli ile vazgeçer ve o sunucuya bu çalıştırmada bir daha gitmez (dakikalarca/saatlerce bekleyip kurulumu kilitlemek yerine atla, sonra dene)."""
    host = urllib.parse.urlparse(url).netloc
    if host in _ENGEL:
        raise SunucuEngeli(_ENGEL[host])
    bekleme = 3.0 if "wikimedia" in host else 0.5
    gecen = time.time() - _SON_ISTEK.get(host, 0)
    if gecen < bekleme:
        time.sleep(bekleme - gecen)
    for deneme in range(2):
        try:
            istek = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(istek, timeout=60) as yanit, open(hedef, "wb") as f:
                shutil.copyfileobj(yanit, f)
            _SON_ISTEK[host] = time.time()
            return
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503):
                raise
            try:
                bekle = float(e.headers.get("Retry-After", ""))
            except ValueError:
                bekle = 10.0
            if deneme == 0 and bekle <= BEKLE_EN_COK:
                print(f"   {host}: HTTP {e.code}, {bekle:.0f} sn bekleniyor", flush=True)
                time.sleep(bekle)
                continue
            _ENGEL[host] = f"{host} hız sınırı uyguluyor (HTTP {e.code}, {bekle:.0f} sn istedi)"
            raise SunucuEngeli(_ENGEL[host]) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _ENGEL[host] = f"{host} yanıt vermiyor ({type(e).__name__})"
            raise SunucuEngeli(_ENGEL[host]) from e


def var_mi(r: sqlite3.Row) -> str:
    """'ok' | 'yok' | 'bozuk' (dosya için sha256; zip-url için hedef klasör boş mu)."""
    hedef = ROOT / r["hedef"]
    if r["kaynak_tur"] in ("zip-url", "git"):
        if not (hedef.is_dir() and any(hedef.iterdir())):
            return "yok"
        isaret = hedef / ".varlik-sha256"  # hangi zip'ten açıldığını işaretler: sürüm değişince yeniden indirir
        return "ok" if isaret.is_file() and isaret.read_text(encoding="utf-8").strip() == (r["sha256"] or "") else "bozuk"
    if not hedef.is_file():
        return "yok"
    if r["sha256"] and sha256(hedef) != r["sha256"]:
        return "bozuk"
    return "ok"


def getir(r: sqlite3.Row) -> str:
    hedef = ROOT / r["hedef"]
    tur = r["kaynak_tur"]
    if tur == "npm":
        paket, yol = r["kaynak"].split("::", 1)
        src = ROOT / "node_modules" / paket / yol
        if not src.is_file():
            return f"HATA kaynak yok: {src} (önce npm kurulumu)"
        hedef.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, hedef)
    elif tur == "git":
        adres, _, kalan = r["kaynak"].partition("@")
        ref, _, altyol = kalan.partition("::")
        if not adres.startswith("https://") or len(ref) != 40:
            return "HATA: git kaynağı https adresi + 40 haneli commit olmalı"
        tmp = ROOT / "sistem" / "ortam" / "yerel" / "indirme" / (r["id"] + "-git")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for komut in (["init", "-q"], ["remote", "add", "origin", adres], ["fetch", "-q", "--depth", "1", "origin", ref],
                      ["-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD"]):
            try:
                sp = subprocess.run(["git", "-c", "core.longpaths=true", *komut], cwd=str(tmp), capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired:
                shutil.rmtree(tmp, ignore_errors=True)
                raise SunucuEngeli("git sunucusu 5 dk içinde yanıt vermedi")
            if sp.returncode != 0:
                return "HATA: git " + komut[0] + ": " + sp.stderr.strip()[-160:]
        gercek = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tmp), capture_output=True, text=True).stdout.strip()
        if gercek != ref:
            return "HATA: çekilen commit beklenenle aynı değil"
        src = (tmp / altyol) if altyol else tmp
        if not src.is_dir():
            return f"HATA: depoda '{altyol}' klasörü yok"
        shutil.rmtree(hedef, ignore_errors=True)
        shutil.copytree(src, hedef, ignore=shutil.ignore_patterns(".git"))
        (hedef / ".varlik-sha256").write_text(r["sha256"] or "", encoding="utf-8")
        shutil.rmtree(tmp, ignore_errors=True)
    elif tur == "yerel":
        return "UYARI: yerel dosya bu bilgisayara özel; başka kaynaktan getirilemez (kendi parçanı yeniden koy)"
    else:
        if not r["kaynak"].startswith("https://"):
            return "HATA: yalnızca https adresi indirilir"
        indirme = (ROOT / "sistem" / "ortam" / "yerel" / "indirme" / (r["id"] + ".part"))
        indirme.parent.mkdir(parents=True, exist_ok=True)
        # Bazı siteler (ör. GitHub, Hugging Face) kimliksiz istemciyi reddeder: genel bir istemci adı kullan.
        try:
            _indir(r["kaynak"], indirme)
        except BaseException:
            indirme.unlink(missing_ok=True)   # yarım kalan dosya bir sonraki denemeyi bozmasın
            raise
        if r["sha256"] and sha256(indirme) != r["sha256"]:
            indirme.unlink(missing_ok=True)
            return "HATA: sha256 uyuşmadı, indirilen dosya atıldı"
        if tur == "zip-url":
            shutil.rmtree(hedef, ignore_errors=True)  # eski/bozuk sürümü temizle
            hedef.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(indirme) as z:
                for ad in z.namelist():  # zip-slip koruması
                    if not (hedef / ad).resolve().is_relative_to(hedef.resolve()):
                        return f"HATA: güvensiz zip yolu {ad}"
                z.extractall(hedef)
            (hedef / ".varlik-sha256").write_text(r["sha256"] or "", encoding="utf-8")
            indirme.unlink(missing_ok=True)
        else:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(indirme), hedef)
    return "indirildi" if var_mi(r) == "ok" else "HATA: sonrasında doğrulanamadı"


def cmd_liste(c, a):
    for r in c.execute("SELECT * FROM varlik" + (" WHERE tur=?" if a.tur else "") + " ORDER BY tur,id", (a.tur,) if a.tur else ()):
        print(f"{r['tur']:9} {r['kaynak_tur']:7} {r['id']:34} {r['hedef']}   [{r['lisans']}]")


def cmd_durum(c, a):
    sayac = {"ok": 0, "yok": 0, "bozuk": 0}
    for r in c.execute("SELECT * FROM varlik" + (" WHERE tur=?" if a.tur else ""), (a.tur,) if a.tur else ()):
        d = var_mi(r)
        sayac[d] += 1
        if d != "ok":
            print(f"{d.upper():6} {r['id']} → {r['hedef']}")
    print(f"toplam: {sayac['ok']} tamam, {sayac['yok']} eksik, {sayac['bozuk']} bozuk")
    return 1 if sayac["bozuk"] else 0


def indir_calistir(c, tur: str | None = None, bildir=None, turler: tuple | None = None) -> dict:
    """Eksik/bozuk varlıkları getirir → {id: sonuç}. Sonuç 'indirildi' | 'ATLANDI: …' (sunucu hız sınırı/ulaşılamaz: sonra denenir) | 'HATA: …'.
    Bir varlığın sorunu diğerlerini durdurmaz; hız sınırına takılan sunucu bu çalıştırmada bir daha denenmez (bekletme yok)."""
    if turler:   # birden çok tür (ör. temel varlıklar): yalnızca bunlar
        satirlar = list(c.execute("SELECT * FROM varlik WHERE tur IN (%s) ORDER BY tur,id" % ",".join("?" * len(turler)), tuple(turler)))
    else:
        satirlar = list(c.execute("SELECT * FROM varlik" + (" WHERE tur=?" if tur else "") + " ORDER BY tur,id", (tur,) if tur else ()))
    eksik = [r for r in satirlar if var_mi(r) != "ok"]
    sonuc: dict = {}
    for sira, r in enumerate(eksik):
        if bildir:
            bildir({"sira": sira, "toplam": len(eksik), "simdiki": r["id"], "tur": r["tur"], "sonuc": dict(sonuc)})
        try:
            s = getir(r)
        except SunucuEngeli as e:
            s = f"ATLANDI: {e}"
        except Exception as e:  # noqa: BLE001  (ağ kesintisi…): bir varlık diğerlerini durdurmasın
            s = f"HATA: {type(e).__name__}: {str(e)[:120]}"
        sonuc[r["id"]] = s
        print(f"{r['id']}: {s}", flush=True)
    if bildir:
        bildir({"sira": len(eksik), "toplam": len(eksik), "simdiki": "", "sonuc": dict(sonuc)})
    return sonuc


def cmd_indir(c, a):
    """Çıkış kodu: 0 hepsi tamam · 3 bazıları ATLANDI (sunucu hız sınırı/ulaşılamaz; kurulum bunu hata saymaz, panel arka planda yeniden dener) · 1 gerçek hata."""
    sonuc = indir_calistir(c, a.tur)
    hata = [k for k, v in sonuc.items() if v.startswith("HATA")]
    atlanan = [k for k, v in sonuc.items() if v.startswith("ATLANDI")]
    if hata:
        print("indirme bitti (bazı varlıklar inemedi: ağı kontrol edip tekrar çalıştır; kalanlar kaldığı yerden devam eder)")
        return 1
    if atlanan:
        print(f"indirme bitti ({len(atlanan)} varlık atlandı: sunucu şu an hız sınırı uyguluyor; panel açıkken arka planda yeniden denenir ya da: Başlat.cmd varlik)")
        return 3
    print("indirme bitti")
    return 0


def cmd_ekle(c, a):
    hedef = ROOT / a.hedef
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if not a.url.startswith("https://"):
        sys.exit("yalnızca https adresi")
    _indir(a.url, hedef)
    kimlik = a.id or hedef.stem
    c.execute("INSERT OR REPLACE INTO varlik VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (kimlik, a.tur, a.ad, a.hedef.replace("\\", "/"), "url", a.url, sha256(hedef), hedef.stat().st_size,
               a.lisans, a.lisans_url, a.__dict__.get("not_"), time.strftime("%Y-%m-%d")))
    c.commit()
    print(f"kaydedildi: {kimlik} ({hedef.stat().st_size} bayt, sha256 {sha256(hedef)[:12]}…)")


def cmd_ekle_yerel(c, a):
    src = Path(a.dosya)
    if not src.is_file():
        sys.exit(f"dosya yok: {src}")
    hedef_rel = (a.hedef or f"sistem/kit/muzik/{src.name}").replace("\\", "/")
    hedef = ROOT / hedef_rel
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() != hedef.resolve():
        shutil.copy2(src, hedef)
    kimlik = a.id or hedef.stem
    c.execute("INSERT OR REPLACE INTO varlik VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (kimlik, a.tur, a.ad or hedef.stem, hedef_rel, "yerel", src.name, sha256(hedef), hedef.stat().st_size,
               a.lisans, a.lisans_url, a.__dict__.get("not_"), time.strftime("%Y-%m-%d")))
    c.commit()
    print(f"kaydedildi (yerel, bu bilgisayara özel): {kimlik} → {hedef_rel}")


def cmd_ekle_git(c, a):
    kimlik = a.id or a.ad.lower().replace(" ", "-")
    kaynak = f"{a.adres}@{a.ref}::{a.altyol or ''}"
    c.execute("INSERT OR REPLACE INTO varlik VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (kimlik, a.tur, a.ad, a.hedef.replace("\\", "/"), "git", kaynak, a.ref, None, a.lisans, a.lisans_url,
               a.__dict__.get("not_"), time.strftime("%Y-%m-%d")))
    c.commit()
    r = c.execute("SELECT * FROM varlik WHERE id=?", (kimlik,)).fetchone()
    print("kaydedildi; indiriliyor/doğrulanıyor:", getir(r))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="komut", required=True)
    for k in ("liste", "durum", "indir"):
        p = sp.add_parser(k)
        p.add_argument("--tur")
    e = sp.add_parser("ekle")
    e.add_argument("--tur", required=True, choices=["sfx", "muzik", "model", "arac", "referans"])
    e.add_argument("--ad", required=True)
    e.add_argument("--url", required=True)
    e.add_argument("--hedef", required=True)
    e.add_argument("--lisans", required=True)
    e.add_argument("--lisans-url")
    e.add_argument("--id")
    e.add_argument("--not", dest="not_")
    y = sp.add_parser("ekle-yerel", help="kendi dosyanı kaydet (bu bilgisayara özel)")
    y.add_argument("--tur", required=True, choices=["sfx", "muzik"])
    y.add_argument("--dosya", required=True)
    y.add_argument("--ad")
    y.add_argument("--hedef")
    y.add_argument("--lisans", required=True)
    y.add_argument("--lisans-url")
    y.add_argument("--id")
    y.add_argument("--not", dest="not_")
    g = sp.add_parser("ekle-git", help="sabit commit'ten bir klasörü kaydet ve indir")
    g.add_argument("--tur", required=True, choices=["sfx", "muzik", "referans"])
    g.add_argument("--ad", required=True)
    g.add_argument("--adres", required=True)
    g.add_argument("--ref", required=True, help="40 haneli commit")
    g.add_argument("--altyol", default="")
    g.add_argument("--hedef", required=True)
    g.add_argument("--lisans", required=True)
    g.add_argument("--lisans-url")
    g.add_argument("--id")
    g.add_argument("--not", dest="not_")
    a = ap.parse_args()
    c = baglan()
    return {"liste": cmd_liste, "durum": cmd_durum, "indir": cmd_indir, "ekle": cmd_ekle,
            "ekle-yerel": cmd_ekle_yerel, "ekle-git": cmd_ekle_git}[a.komut](c, a) or 0


if __name__ == "__main__":
    sys.exit(main())
