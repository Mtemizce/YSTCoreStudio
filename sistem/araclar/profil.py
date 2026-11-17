#!/usr/bin/env python3
"""Profil dışa/içe aktarma: bu bilgisayarda yaptığın her şeyi (ayarlar, API anahtarları, kimlik katmanları, arşiv kökleri ve analizi,
marka kitleri, MCP kayıtları) TEK bir JSON dosyasına koyar; başka bir bilgisayardaki yeni kuruluma içe aktarırsın, kaldığın yerden devam edersin.

  python sistem/araclar/profil.py disa-aktar [--hedef dosya.json] [--sifre-sor | --sifresiz] [--anahtarsiz] [--arsivsiz] [--ornek-yok] [--iyilestirilmis] [--projeler]
  python sistem/araclar/profil.py goster <dosya.json>                  içeriğin özeti (şifreliyse şifre sorar)
  python sistem/araclar/profil.py ice-aktar <dosya.json> [--kuru] [--atla]   --kuru: yazmadan neyin değişeceğini göster

Bu SENİN verindir; dışa aktarmaya API anahtarları ve kişisel kimlik bilgileri de girer. Bu yüzden dosya varsayılan olarak **parolayla şifrelenir**
(scrypt + Fernet). Parolasız dosya düz metindir: güvenli sakla. Parolayı unutursan dosya açılmaz (kurtarma yok).

Biçim: {"format":"yst-profil","surum":N,"sifreli":bool,...}. Uyumluluk: yalnızca ekleme; yeni sürümün bilinmeyen bölümleri içe aktarmada silinmez
(sistem/ortam/yerel/profil_ek.json'da saklanır, sonraki dışa aktarmaya geri konur). Eski sürüm dosyaları göç fonksiyonlarıyla yükseltilir.
Arşivin kendisi (fotoğraf/video) yedeğe girmez, yalnızca kök tanımları ve dizin/analiz kayıtları girer; yolu yeni bilgisayarda gösterirsin.
Büyük ekler (iyileştirilmiş fotoğraflar, projeler) JSON'un yanında `<ad>.ekler.zip` olarak yazılır.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
YEDEK = ORTAM / "yedek"
EK_DOSYA = ORTAM / "yerel" / "profil_ek.json"
FORMAT = "yst-profil"
SURUM = 1
BILINEN = {"uygulama", "ayar", "baglayici", "kimlik", "arsiv", "olusturma", "makine"}
KIMLIK_UZANTI = {".md", ".json", ".txt", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".wav", ".mp3", ".m4a", ".ogg", ".flac", ".csv", ".srt"}
KIMLIK_EN_COK = 120_000_000  # bayt (örnek ses/video dosyaları için üst sınır)
sys.path.insert(0, str(SISTEM / "arsiv"))
sys.path.insert(0, str(SISTEM / "araclar"))


# ------------------------------------------------------------------ şifreleme (scrypt + Fernet)
def _fernet(sifre: str, tuz: bytes, n: int = 2 ** 15):
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:  # noqa: F841
        raise RuntimeError("şifreleme için 'cryptography' paketi gerekir (Başlat.cmd kurulumu yükler; elle: pip install cryptography)") from None
    anahtar = hashlib.scrypt(sifre.encode("utf-8"), salt=tuz, n=n, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024)
    return Fernet(base64.urlsafe_b64encode(anahtar))


def sifrele(icerik: dict, sifre: str) -> dict:
    tuz = os.urandom(16)
    f = _fernet(sifre, tuz)
    veri = f.encrypt(json.dumps(icerik, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return {"format": FORMAT, "surum": SURUM, "sifreli": True, "kdf": {"ad": "scrypt", "n": 2 ** 15, "r": 8, "p": 1, "tuz": base64.b64encode(tuz).decode()},
            "olusturma": time.strftime("%Y-%m-%d %H:%M:%S"), "veri": veri.decode("ascii")}


def coz(zarf: dict, sifre: str | None) -> dict:
    """Zarfı açıp iç içeriği döndürür. Şifre yanlışsa/yoksa ValueError."""
    if zarf.get("format") != FORMAT:
        raise ValueError("bu bir YSTCoreStudio profil dosyası değil")
    if not zarf.get("sifreli"):
        return zarf["icerik"]
    if not sifre:
        raise ValueError("SIFRE_GEREKLI: dosya şifreli, parola gerekli")
    k = zarf["kdf"]
    try:
        from cryptography.fernet import InvalidToken
        f = _fernet(sifre, base64.b64decode(k["tuz"]), int(k.get("n", 2 ** 15)))
        return json.loads(f.decrypt(zarf["veri"].encode("ascii")).decode("utf-8"))
    except InvalidToken:
        raise ValueError("parola yanlış (ya da dosya bozulmuş)") from None


# ------------------------------------------------------------------ yardımcılar
def _json(p: Path, varsayilan=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return varsayilan if varsayilan is not None else {}


def surum_bilgisi() -> dict:
    return _json(SISTEM / "surum.json", {"uygulama": "?", "sema": {}})


def _dosya_ekle(kimlik: dict, rel: str, p: Path) -> None:
    if p.suffix.lower() in {".md", ".json", ".txt", ".csv", ".srt", ".svg"}:
        try:
            kimlik[rel] = {"metin": p.read_text(encoding="utf-8")}
            return
        except UnicodeDecodeError:
            pass
    kimlik[rel] = {"b64": base64.b64encode(p.read_bytes()).decode("ascii")}


def _arsiv_bolumu(c: sqlite3.Connection) -> dict:
    """Yalnızca arşiv kökleri ve onlara ait kayıtlar. Stüdyo kökü yedeğe girmez (her bilgisayarda kendiliğinden algılanır)."""
    kokler = []
    ad_of = {}
    for r in c.execute("SELECT * FROM kok WHERE tur='arsiv' ORDER BY id"):
        ad_of[r["id"]] = r["ad"]
        yollar = [dict(y) for y in c.execute("SELECT makine,yol,seri,etiket,alt,surucu_turu FROM kok_yol WHERE kok_id=?", (r["id"],))]
        kokler.append({"ad": r["ad"], "gorunen_ad": r["gorunen_ad"], "adaptor": r["adaptor"], "uzak": r["uzak"] if "uzak" in r.keys() else None,
                       "son_tarama": r["son_tarama"], "yollar": yollar})
    dosya = []
    for r in c.execute("SELECT * FROM dosya ORDER BY kok_id, id"):
        if r["kok_id"] in ad_of:
            d = dict(r)
            d.pop("id", None)
            d["kok"] = ad_of[d.pop("kok_id")]
            d.pop("goruldu", None)
            dosya.append(d)
    analiz = []
    for r in c.execute("SELECT * FROM analiz"):
        if r["kok_id"] in ad_of:
            d = dict(r)
            d["kok"] = ad_of[d.pop("kok_id")]
            analiz.append(d)
    notlar = []
    for r in c.execute("SELECT * FROM proje_notu"):
        if r["kok_id"] in ad_of:
            d = dict(r)
            d["kok"] = ad_of[d.pop("kok_id")]
            notlar.append(d)
    iyi = []
    for r in c.execute("""SELECT i.*, d.kok_id, d.yol dyol FROM iyilestirme i JOIN dosya d ON d.id=i.dosya_id"""):
        if r["kok_id"] in ad_of:
            d = dict(r)
            d["kok"] = ad_of[d.pop("kok_id")]
            d["dosya_yol"] = d.pop("dyol")
            d.pop("id", None)
            d.pop("dosya_id", None)
            iyi.append(d)
    return {"surum": 1, "kokler": kokler, "dosya": dosya, "analiz": analiz, "proje_notu": notlar, "iyilestirme": iyi}


# ------------------------------------------------------------------ dışa aktarma
def disa_aktar(hedef: str | None = None, sifre: str | None = None, anahtarlar: bool = True, arsiv_dizini: bool = True, ornekler: bool = True,
               iyilestirilmis: bool = False, projeler: bool = False) -> dict:
    import konum as K
    import arsiv as A
    YEDEK.mkdir(parents=True, exist_ok=True)
    ic: dict = {"uygulama": surum_bilgisi(), "olusturma": time.strftime("%Y-%m-%d %H:%M:%S"), "makine": K.makine(), "bolumler_not": "yst-profil"}
    icerik = []
    ic["ayar"] = {"surum": 1, "kullanici": _json(SISTEM / "ayar" / "kullanici.json", {"ajanlar": {}})}
    icerik.append("ayarlar (ajan model/effort, işler ve modeller, bağlayıcı durumları)")
    bag = {"surum": 1, "mcp": _json(ORTAM / "baglayici" / "mcp.json", {})}
    if anahtarlar:
        bag["anahtarlar"] = _json(ORTAM / "baglayici" / "anahtar.json", {})
        icerik.append(f"API anahtarları ({len(bag['anahtarlar'])} adet)")
    else:
        bag["anahtar_adlari"] = sorted(_json(ORTAM / "baglayici" / "anahtar.json", {}))
    cf = ORTAM / "yerel" / "rclone.conf"
    if anahtarlar and cf.is_file():  # Google Drive/OneDrive/Dropbox hesap jetonları (rclone yapılandırması)
        bag["bulut_disk_conf"] = cf.read_text(encoding="utf-8", errors="replace")
        icerik.append("bulut disk hesapları (rclone jetonları)")
    ic["baglayici"] = bag
    kimlik: dict = {}
    toplam = 0
    kdir = ROOT / "kimlik"
    if kdir.is_dir():
        for p in sorted(kdir.rglob("*")):
            if not p.is_file() or p.name == ".gitkeep" or p.suffix.lower() not in KIMLIK_UZANTI:
                continue
            rel = p.relative_to(kdir).as_posix()
            if rel.startswith("ornekler/") and not ornekler:
                continue
            toplam += p.stat().st_size
            if toplam > KIMLIK_EN_COK:
                raise ValueError(f"kimlik dosyaları {KIMLIK_EN_COK // 1_000_000} MB'ı aşıyor; kimlik/ornekler içindeki büyük dosyaları azalt ya da --ornek-yok")
            _dosya_ekle(kimlik, rel, p)
    ic["kimlik"] = {"surum": 1, "dosyalar": kimlik}
    icerik.append(f"kimlik katmanları ve marka kitleri ({len(kimlik)} dosya)")
    if arsiv_dizini:
        c = A.baglan()
        ic["arsiv"] = _arsiv_bolumu(c)
        c.close()
        a = ic["arsiv"]
        icerik.append(f"arşiv: {len(a['kokler'])} kök, {len(a['dosya'])} dosya kaydı, {len(a['analiz'])} analiz")
    ek = _json(EK_DOSYA, {})
    if ek:
        ic["ek"] = ek  # önceki içe aktarmada tanınmayan (daha yeni sürüm) bölümler geri konur
    ekler = []
    ad = f"yst-profil-{time.strftime('%Y%m%d-%H%M%S')}"
    z_yol = None
    if iyilestirilmis or projeler:
        if hedef:
            Path(hedef).parent.mkdir(parents=True, exist_ok=True)
        z_yol =(Path(hedef).parent / (Path(hedef).stem + ".ekler.zip")) if hedef else YEDEK / f"{ad}.ekler.zip"
        with zipfile.ZipFile(z_yol, "w", zipfile.ZIP_DEFLATED) as zf:
            if iyilestirilmis and (ORTAM / "arsiv" / "iyilestirilmis").is_dir():
                n = 0
                for p in (ORTAM / "arsiv" / "iyilestirilmis").rglob("*"):
                    if p.is_file():
                        zf.write(p, "iyilestirilmis/" + p.relative_to(ORTAM / "arsiv" / "iyilestirilmis").as_posix())
                        n += 1
                ekler.append(f"iyileştirilmiş fotoğraflar ({n})")
            if projeler and (ROOT / "projeler").is_dir():
                n = 0
                for dp, dn, fn in os.walk(ROOT / "projeler"):
                    dn[:] = [d for d in dn if d not in ("node_modules", "__pycache__", "out", ".git")]
                    for f in fn:
                        p = Path(dp) / f
                        zf.write(p, "projeler/" + p.relative_to(ROOT / "projeler").as_posix())
                        n += 1
                ekler.append(f"projeler ({n} dosya)")
        ic["ekler"] = {"zip": z_yol.name, "icerik": ekler}
        icerik += ekler
    if sifre:
        zarf = sifrele(ic, sifre)
        icerik.append("parolayla şifrelendi")
    else:
        zarf = {"format": FORMAT, "surum": SURUM, "sifreli": False, "olusturma": ic["olusturma"], "icerik": ic}
    yol = Path(hedef) if hedef else YEDEK / f"{ad}.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    tmp = yol.with_suffix(yol.suffix + ".part")
    tmp.write_text(json.dumps(zarf, ensure_ascii=False, indent=None if sifre else 1), encoding="utf-8")
    tmp.replace(yol)
    if z_yol and z_yol.parent != yol.parent:
        pass
    return {"dosya": str(yol), "ad": yol.name, "boyut_mb": round(yol.stat().st_size / 1e6, 2), "sifreli": bool(sifre), "icerik": icerik,
            "ek_zip": str(z_yol) if z_yol else None, "uyari": None if sifre else "Dosya ŞİFRESİZ: içinde API anahtarların ve kişisel verin düz metin olarak duruyor. Güvenli sakla."}


# ------------------------------------------------------------------ göç (eski sürüm → şimdiki)
def _yukselt(ic: dict, surum: int) -> dict:
    """Her N→N+1 adımı burada tanımlanır (şimdilik tek sürüm var). Örn: GOC[1] = lambda ic: …  → 2. sürüme."""
    GOC: dict[int, object] = {}
    s = surum
    while s < SURUM:
        f = GOC.get(s)
        if f:
            ic = f(ic)  # type: ignore[operator]
        s += 1
    return ic


def oku(dosya: str, sifre: str | None) -> tuple[dict, dict]:
    zarf = json.loads(Path(dosya).read_text(encoding="utf-8"))
    ic = coz(zarf, sifre)
    return zarf, _yukselt(ic, int(zarf.get("surum", 1)))


def ozet(dosya: str, sifre: str | None = None) -> dict:
    zarf = json.loads(Path(dosya).read_text(encoding="utf-8"))
    if zarf.get("format") != FORMAT:
        raise ValueError("bu bir YSTCoreStudio profil dosyası değil")
    if zarf.get("sifreli") and not sifre:
        return {"sifreli": True, "surum": zarf.get("surum"), "olusturma": zarf.get("olusturma")}
    _, ic = oku(dosya, sifre)
    a = ic.get("arsiv") or {}
    return {"sifreli": bool(zarf.get("sifreli")), "surum": zarf.get("surum"), "uygulama": ic.get("uygulama", {}).get("uygulama"), "olusturma": ic.get("olusturma"), "makine": ic.get("makine"),
            "anahtar_sayisi": len((ic.get("baglayici") or {}).get("anahtarlar") or {}), "anahtar_adlari": sorted((ic.get("baglayici") or {}).get("anahtarlar") or (ic.get("baglayici") or {}).get("anahtar_adlari") or []),
            "kimlik_dosyasi": len((ic.get("kimlik") or {}).get("dosyalar") or {}), "arsiv_kokleri": [k["ad"] for k in a.get("kokler", [])],
            "arsiv_dosya": len(a.get("dosya", [])), "arsiv_analiz": len(a.get("analiz", [])), "ekler": (ic.get("ekler") or {}).get("icerik", []),
            "bilinmeyen_bolumler": sorted(set(ic) - BILINEN - {"ekler", "ek", "bolumler_not"})}


# ------------------------------------------------------------------ içe aktarma
def _guvenli_rel(rel: str) -> Path:
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts or re.search(r"^[A-Za-z]:", rel) or Path(rel).suffix.lower() not in KIMLIK_UZANTI:
        raise ValueError(f"güvensiz ya da desteklenmeyen kimlik dosyası: {rel!r}")
    p = (ROOT / "kimlik" / rel).resolve()
    if (ROOT / "kimlik").resolve() not in p.parents:
        raise ValueError(f"kimlik klasörü dışına yazılamaz: {rel!r}")
    return p


def _birlestir(a: dict, b: dict) -> dict:
    out = json.loads(json.dumps(a))
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _birlestir(out[k], v)
        else:
            out[k] = v
    return out


def ice_aktar(dosya: str, sifre: str | None = None, kuru: bool = False, cakisma: str = "uzerine") -> dict:
    """cakisma: 'uzerine' (dosyadaki değer kazanır; değişen yerel dosyanın .yedek kopyası alınır) | 'atla' (var olana dokunma)."""
    import konum as K
    import arsiv as A
    zarf, ic = oku(dosya, sifre)
    atla = cakisma == "atla"
    rapor: dict = {"kuru": kuru, "yazilan": [], "atlanan": [], "uyari": []}
    if int(zarf.get("surum", 1)) > SURUM:
        rapor["uyari"].append(f"dosya daha yeni bir sürümden (şema {zarf.get('surum')} > {SURUM}): tanınan bölümler alındı, tanınmayanlar saklandı")

    # --- ayar
    mevcut = _json(SISTEM / "ayar" / "kullanici.json", {"ajanlar": {}})
    gelen = (ic.get("ayar") or {}).get("kullanici") or {}
    yeni = _birlestir(gelen, mevcut) if atla else _birlestir(mevcut, gelen)
    if yeni != mevcut:
        rapor["yazilan"].append("ayarlar (ajan model/effort, işler ve modeller, bağlayıcı durumları)")
        if not kuru:
            (SISTEM / "ayar" / "kullanici.json").write_text(json.dumps(yeni, ensure_ascii=False, indent=2), encoding="utf-8")
    # --- bağlayıcı: MCP + anahtarlar
    bag = ic.get("baglayici") or {}
    if bag.get("bulut_disk_conf"):
        cf = ORTAM / "yerel" / "rclone.conf"
        if not cf.exists() or not atla:
            rapor["yazilan"].append("bulut disk hesapları (rclone jetonları)")
            if not kuru:
                cf.parent.mkdir(parents=True, exist_ok=True)
                cf.write_text(bag["bulut_disk_conf"], encoding="utf-8")
                try:
                    os.chmod(cf, 0o600)
                except OSError:
                    pass
    for ad, hedef in (("mcp", ORTAM / "baglayici" / "mcp.json"), ("anahtarlar", ORTAM / "baglayici" / "anahtar.json")):
        gel = bag.get(ad)
        if not gel:
            continue
        mev = _json(hedef, {})
        yn = _birlestir(gel, mev) if atla else _birlestir(mev, gel)
        if yn != mev:
            rapor["yazilan"].append("MCP kayıtları" if ad == "mcp" else f"API anahtarları ({len(gel)} adet: {', '.join(sorted(gel))})")
            if not kuru:
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_text(json.dumps(yn, ensure_ascii=False, indent=1), encoding="utf-8")
                if ad == "anahtarlar":
                    try:
                        os.chmod(hedef, 0o600)
                    except OSError:
                        pass
    if bag.get("anahtar_adlari"):
        rapor["uyari"].append("dosya anahtarsız dışa aktarılmış; şu anahtarları Ayarlar → Bağlayıcılar'dan yeniden gir: " + ", ".join(bag["anahtar_adlari"]))
    # --- kimlik
    n = 0
    for rel, v in ((ic.get("kimlik") or {}).get("dosyalar") or {}).items():
        p = _guvenli_rel(rel)
        veri = v["metin"].encode("utf-8") if "metin" in v else base64.b64decode(v["b64"])
        if p.exists():
            if p.read_bytes() == veri:
                continue
            if atla:
                rapor["atlanan"].append(f"kimlik/{rel}")
                continue
            if not kuru:
                p.replace(p.with_name(p.name + ".yedek-" + time.strftime("%Y%m%d-%H%M%S")))
        n += 1
        if not kuru:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(veri)
    if n:
        rapor["yazilan"].append(f"kimlik dosyaları ({n})")
    # --- arşiv
    a = ic.get("arsiv")
    if a:
        k = {"kok": 0, "dosya": 0, "analiz": 0, "iyilestirme": 0}
        if not kuru:
            c = A.baglan()
            idler: dict[str, int] = {}
            for kk in a.get("kokler", []):
                r = c.execute("SELECT id FROM kok WHERE ad=?", (kk["ad"],)).fetchone()
                if r:
                    kid = r[0]
                else:
                    kid = c.execute("INSERT INTO kok(ad,tur,gorunen_ad,adaptor,uzak,son_tarama,olusturma) VALUES (?,?,?,?,?,?,?)",
                                    (kk["ad"], "arsiv", kk.get("gorunen_ad"), kk.get("adaptor") or "klasor", kk.get("uzak"), kk.get("son_tarama"), time.strftime("%Y-%m-%d %H:%M"))).lastrowid
                    k["kok"] += 1
                idler[kk["ad"]] = kid
                for y in kk.get("yollar", []):
                    c.execute("INSERT OR REPLACE INTO kok_yol(kok_id,makine,yol,seri,etiket,alt,surucu_turu) VALUES (?,?,?,?,?,?,?)",
                              (kid, y["makine"], y["yol"], y.get("seri"), y.get("etiket"), y.get("alt"), y.get("surucu_turu")))
            kolonlar = [r[1] for r in c.execute("PRAGMA table_info(dosya)") if r[1] not in ("id", "kok_id", "goruldu")]
            for d in a.get("dosya", []):
                kid = idler.get(d.get("kok"))
                if not kid:
                    continue
                vals = [d.get(col) for col in kolonlar]
                cur = c.execute(f"INSERT OR IGNORE INTO dosya(kok_id,goruldu,{','.join(kolonlar)}) VALUES (?,?,{','.join('?' * len(kolonlar))})", [kid, time.time()] + vals)
                if cur.rowcount:
                    k["dosya"] += 1
                    if A.fts_var(c):
                        c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)", (cur.lastrowid, (d.get("etiket") or "")))
            akol = [r[1] for r in c.execute("PRAGMA table_info(analiz)") if r[1] != "kok_id"]
            for d in a.get("analiz", []):
                kid = idler.get(d.get("kok"))
                if not kid or not c.execute("SELECT 1 FROM dosya WHERE kok_id=? AND yol=?", (kid, d.get("yol"))).fetchone():
                    continue
                cur = c.execute(f"INSERT OR REPLACE INTO analiz(kok_id,{','.join(akol)}) VALUES (?,{','.join('?' * len(akol))})", [kid] + [d.get(col) for col in akol])
                k["analiz"] += 1
                if A.fts_var(c) and d.get("c_tarih"):  # Claude açıklaması/etiketleri aramada bulunsun
                    r = c.execute("SELECT id, etiket FROM dosya WHERE kok_id=? AND yol=?", (kid, d["yol"])).fetchone()
                    c.execute("DELETE FROM dosya_fts WHERE rowid=?", (r["id"],))
                    c.execute("INSERT INTO dosya_fts(rowid, etiket) VALUES (?,?)",
                              (r["id"], " ".join([r["etiket"] or "", A.norm(" ".join(str(d.get(x) or "") for x in ("konu", "asama", "aciklama", "etiketler")))])))
            for d in a.get("proje_notu", []):
                kid = idler.get(d.get("kok"))
                if kid:
                    c.execute("INSERT OR REPLACE INTO proje_notu(kok_id,klasor,ozet,tur,tarih) VALUES (?,?,?,?,?)", (kid, d["klasor"], d.get("ozet"), d.get("tur"), d.get("tarih")))
            ikol = [r[1] for r in c.execute("PRAGMA table_info(iyilestirme)") if r[1] not in ("id", "dosya_id")]
            for d in a.get("iyilestirme", []):
                kid = idler.get(d.get("kok"))
                r = c.execute("SELECT id FROM dosya WHERE kok_id=? AND yol=?", (kid, d.get("dosya_yol"))).fetchone() if kid else None
                if r and not c.execute("SELECT 1 FROM iyilestirme WHERE dosya_id=? AND model=? AND cikti_yol IS ?", (r[0], d.get("model"), d.get("cikti_yol"))).fetchone():
                    c.execute(f"INSERT INTO iyilestirme(dosya_id,{','.join(ikol)}) VALUES (?,{','.join('?' * len(ikol))})", [r[0]] + [d.get(col) for col in ikol])
                    k["iyilestirme"] += 1
            c.commit()
            c.close()
        else:
            k = {"kok": len(a.get("kokler", [])), "dosya": len(a.get("dosya", [])), "analiz": len(a.get("analiz", [])), "iyilestirme": len(a.get("iyilestirme", []))}
        rapor["yazilan"].append(f"arşiv dizini: {k['kok']} kök, {k['dosya']} dosya kaydı, {k['analiz']} analiz")
        rapor["uyari"].append("Arşivin kendisi taşınmadı: yeni bilgisayarda yolunu Ayarlar → Konumlar → Gözat ile göster (ya da YST_<AD> ortam değişkeni).")
    # --- ekler (zip)
    e = ic.get("ekler")
    if e:
        zip_yol = Path(dosya).with_name(e["zip"])
        if zip_yol.is_file():
            if not kuru:
                with zipfile.ZipFile(zip_yol) as zf:
                    for ad in zf.namelist():
                        if ad.endswith("/"):
                            continue
                        if ad.startswith("iyilestirilmis/"):
                            hedef = ORTAM / "arsiv" / ad
                        elif ad.startswith("projeler/"):
                            hedef = ROOT / ad
                        else:
                            continue
                        h = hedef.resolve()
                        if not (ROOT.resolve() in h.parents):
                            raise ValueError(f"güvensiz yol: {ad}")
                        if h.exists() and atla:
                            continue
                        h.parent.mkdir(parents=True, exist_ok=True)
                        h.write_bytes(zf.read(ad))
            rapor["yazilan"].append("ekler: " + ", ".join(e.get("icerik", [])))
        else:
            rapor["uyari"].append(f"ek dosya bulunamadı ({e['zip']}): JSON ile aynı klasöre koy ve yeniden içe aktar")
    # --- tanınmayan bölümler saklanır (ileri uyum)
    bilinmeyen = {k2: v for k2, v in ic.items() if k2 not in BILINEN and k2 not in ("ekler", "bolumler_not")}
    if bilinmeyen:
        rapor["uyari"].append("bu sürümün tanımadığı bölümler saklandı: " + ", ".join(sorted(bilinmeyen)))
        if not kuru:
            EK_DOSYA.parent.mkdir(parents=True, exist_ok=True)
            EK_DOSYA.write_text(json.dumps(_birlestir(_json(EK_DOSYA, {}), bilinmeyen), ensure_ascii=False), encoding="utf-8")
    if not kuru:
        try:  # model/effort değiştiyse ajan dosyalarının frontmatter'ı eşitlenir
            import importlib.util
            sp = importlib.util.spec_from_file_location("yst_ayar_p", SISTEM / "ayar" / "ayar.py")
            m = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
            rapor["esitlenen_ajan"] = m.esitle()
        except Exception as ex:  # noqa: BLE001
            rapor["uyari"].append(f"ajan dosyaları eşitlenemedi: {ex}")
    return rapor


# ------------------------------------------------------------------ komut satırı
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if not a or a[0] not in ("disa-aktar", "ice-aktar", "goster"):
        print(__doc__)
        return 2
    try:
        if a[0] == "disa-aktar":
            sifre = None
            if "--sifresiz" not in a:
                sifre = getpass.getpass("Parola (boş bırakma: şifreli dosya için gerekli): ")
                if sifre != getpass.getpass("Parolayı tekrar yaz: "):
                    raise ValueError("parolalar uyuşmuyor")
                if not sifre:
                    raise ValueError("parola boş; şifresiz istiyorsan --sifresiz ver")
            r = disa_aktar(a[a.index("--hedef") + 1] if "--hedef" in a else None, sifre, "--anahtarsiz" not in a, "--arsivsiz" not in a, "--ornek-yok" not in a,
                           "--iyilestirilmis" in a, "--projeler" in a)
        else:
            dosya = a[1]
            sifre = None
            z = json.loads(Path(dosya).read_text(encoding="utf-8"))
            if z.get("sifreli"):
                sifre = getpass.getpass("Parola: ")
            r = ozet(dosya, sifre) if a[0] == "goster" else ice_aktar(dosya, sifre, "--kuru" in a, "atla" if "--atla" in a else "uzerine")
    except (ValueError, RuntimeError, OSError) as e:
        print("HATA:", e)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
