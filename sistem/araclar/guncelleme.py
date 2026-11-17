#!/usr/bin/env python3
"""GitHub'dan güncelleme: ayar (depo + jeton), saatlik kontrol, tek tıkla güncelleme.

  python sistem/araclar/guncelleme.py durum | kontrol | guncelle | ayar <sahip/depo> [jeton]

Akış: kontrol (GitHub API, salt okunur) → kullanıcı "Güncelle" der → 1) veritabanı + ayar + kimlik YEDEĞİ (sistem/ortam/yedek/guncelleme-<zaman>/)
2) güncellemeyi çek: zip kurulumunda son SÜRÜM paketi (sağlama toplamı doğrulanır), geliştirici klonunda `git pull --ff-only` (yerel değişiklik varsa durur)
3) kullanıcı verisine (kimlik/, projeler/, sistem/ortam/, ayar) DOKUNMADAN dosyaları yerleştir 4) onarım + bağımlılıklar (pip, npm) + ajan dosyalarının eşitlenmesi
+ veritabanı şeması 5) rapor + yeniden başlatma. Jeton yalnızca sistem/ortam/baglayici/guncelleme.json'da durur (git'e girmez), arayüze geri gösterilmez.
Yalnızca standart kütüphane.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("YST_GUNCELLEME_KOK") or Path(__file__).resolve().parents[2])  # (ortam değişkeni yalnızca testler içindir)
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
CONF = ORTAM / "baglayici" / "guncelleme.json"
DURUM = ORTAM / "yerel" / "guncelleme_durum.json"
RAPOR = ORTAM / "yerel" / "guncelleme_rapor.json"
YEDEK = ORTAM / "yedek"
NW = 0x08000000 if os.name == "nt" else 0
DEPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,60}/[A-Za-z0-9._-]{1,100}$")
API = os.environ.get("YST_GUNCELLEME_API") or "https://api.github.com"
KORUNAN = ("kimlik/", "projeler/", "sistem/ortam/", ".git/", "node_modules/", "kurgu/")
KORUNAN_DOSYA = {"sistem/ayar/kullanici.json"}
KILIT = threading.Lock()
CALISIYOR = {"var": False, "adim": "", "log": [], "bitti": False, "hata": ""}


# ------------------------------------------------------------------ ayar
def surum() -> str:
    try:
        return json.loads((SISTEM / "surum.json").read_text(encoding="utf-8"))["uygulama"]
    except (OSError, ValueError, KeyError):
        return "0.0.0"


def _oku(p: Path, varsayilan):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return varsayilan


def ayar_oku() -> dict:
    d = _oku(CONF, {})
    return {"repo": d.get("repo", ""), "jeton_var": bool(d.get("jeton")), "etkin": bool(d.get("repo") and d.get("jeton")), "dal": d.get("dal", "")}


def ayar_yaz(repo: str, jeton: str | None = None, dal: str | None = None) -> dict:
    repo = (repo or "").strip()
    if repo and not DEPO_RE.match(repo):
        raise ValueError("depo 'sahip/ad' biçiminde olmalı (örn. Mtemizce/YSTCoreStudio)")
    d = _oku(CONF, {})
    d["repo"] = repo
    if jeton:  # boş bırakılırsa eski jeton korunur
        if not re.fullmatch(r"[A-Za-z0-9_\-]{20,255}", jeton.strip()):
            raise ValueError("jeton biçimi geçersiz (github_pat_… ya da ghp_…)")
        d["jeton"] = jeton.strip()
    if dal is not None:
        if dal and not re.fullmatch(r"[A-Za-z0-9._/-]{1,60}", dal):
            raise ValueError("dal adı geçersiz")
        d["dal"] = dal
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps(d, indent=1), encoding="utf-8")
    try:
        os.chmod(CONF, 0o600)
    except OSError:
        pass
    DURUM.unlink(missing_ok=True)
    return ayar_oku()


def jeton_sil() -> None:
    d = _oku(CONF, {})
    d.pop("jeton", None)
    CONF.write_text(json.dumps(d, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ GitHub
class _Yonlendir(urllib.request.HTTPRedirectHandler):
    """Başka bir sunucuya (indirme deposu) yönlenirken Authorization başlığı gönderilmez."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        yeni = super().redirect_request(req, fp, code, msg, headers, newurl)
        if yeni is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            yeni.headers.pop("Authorization", None)
            yeni.unredirected_hdrs.pop("Authorization", None)
        return yeni


import urllib.parse  # noqa: E402


def _istek(yol_ya_da_url: str, jeton: str, kabul: str = "application/vnd.github+json", zaman: int = 30):
    url = yol_ya_da_url if yol_ya_da_url.startswith(("https://", "http://127.0.0.1")) else API + yol_ya_da_url
    if not url.startswith(("https://", "http://127.0.0.1")):
        raise ValueError("yalnızca https")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jeton}", "Accept": kabul, "User-Agent": "YSTCoreStudio-guncelleme",
                                               "X-GitHub-Api-Version": "2022-11-28"})
    return urllib.request.build_opener(_Yonlendir).open(req, timeout=zaman)


def _api_json(yol: str, jeton: str):
    try:
        with _istek(yol, jeton) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        nedenler = {401: "jeton geçersiz ya da süresi dolmuş", 403: "jeton bu depoya erişemiyor ya da istek sınırı doldu", 404: "depo bulunamadı (adı ve jetonun bu depoya izni var mı?)"}
        raise RuntimeError(nedenler.get(e.code, f"GitHub HTTP {e.code}")) from None
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"GitHub'a ulaşılamadı: {getattr(e, 'reason', e)}") from None


def _sayilar(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:4]) or (0,)


def klon_mu() -> bool:
    return (ROOT / ".git").exists()


def _git(*a: str, jeton: str | None = None, zaman: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if jeton:  # komut satırında görünmesin diye ortam üzerinden
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                    "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic " + base64.b64encode(f"x-access-token:{jeton}".encode()).decode()})
    return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, env=env, creationflags=NW)


# ------------------------------------------------------------------ kontrol
def kontrol() -> dict:
    """Güncelleme var mı? Sonuç sistem/ortam/yerel/guncelleme_durum.json'a yazılır."""
    c = _oku(CONF, {})
    sonuc = {"son_kontrol": time.strftime("%Y-%m-%d %H:%M:%S"), "var": False, "mevcut": surum(), "yeni": None, "notlar": "", "hata": "", "tur": "klon" if klon_mu() else "surum"}
    if not (c.get("repo") and c.get("jeton")):
        sonuc["hata"] = "depo ve jeton girilmemiş"
        DURUM.parent.mkdir(parents=True, exist_ok=True)
        DURUM.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
        return sonuc
    try:
        if klon_mu():
            dal = c.get("dal") or (_git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main")
            uz = _api_json(f"/repos/{c['repo']}/commits/{dal}", c["jeton"])
            uzak_sha = uz["sha"]
            yerel = _git("rev-parse", "HEAD").stdout.strip()
            if uzak_sha != yerel:
                # yerel, uzağın ilerisinde ya da ayrışmış olabilir: uzak sha yerelde biliniyorsa ve atasıysa güncelleme yok
                bil = _git("merge-base", "--is-ancestor", uzak_sha, "HEAD")
                if bil.returncode != 0:
                    sonuc.update(var=True, yeni=uzak_sha[:8], notlar=(uz.get("commit", {}).get("message") or "")[:300])
        else:
            r = _api_json(f"/repos/{c['repo']}/releases/latest", c["jeton"])
            tag = r.get("tag_name", "")
            if _sayilar(tag) > _sayilar(surum()):
                sonuc.update(var=True, yeni=tag.lstrip("v"), notlar=(r.get("body") or "")[:1500])
    except (RuntimeError, ValueError, KeyError) as e:
        sonuc["hata"] = str(e)
    DURUM.parent.mkdir(parents=True, exist_ok=True)
    DURUM.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
    return sonuc


def durum() -> dict:
    d = _oku(DURUM, {})
    return {**ayar_oku(), "surum": surum(), "tur": "klon" if klon_mu() else "surum", "kontrol": d, "calisiyor": dict(CALISIYOR), "rapor": _oku(RAPOR, None)}


def saatlik_baslat(aralik: int = 3600) -> None:
    """Panel açıkken saatte bir kontrol (ayar girilmişse). İlk kontrol 45 sn sonra."""
    def d():
        time.sleep(45)
        while True:
            try:
                if ayar_oku()["etkin"] and not CALISIYOR["var"]:
                    kontrol()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(aralik)
    threading.Thread(target=d, daemon=True, name="guncelleme-kontrol").start()


# ------------------------------------------------------------------ güncelleme
def _log(m: str) -> None:
    CALISIYOR["log"].append(f"{time.strftime('%H:%M:%S')} {m}")
    CALISIYOR["adim"] = m


def yedekle() -> Path:
    hedef = YEDEK / f"guncelleme-{time.strftime('%Y%m%d-%H%M%S')}"
    hedef.mkdir(parents=True, exist_ok=True)
    db = ORTAM / "arsiv" / "arsiv.db"
    if db.is_file():  # tutarlı kopya: SQLite yedekleme arayüzü
        kaynak = sqlite3.connect(str(db))
        kopya = sqlite3.connect(str(hedef / "arsiv.db"))
        with kopya:
            kaynak.backup(kopya)
        kopya.close()
        kaynak.close()
    for rel in ("sistem/ayar/kullanici.json", "sistem/ortam/baglayici/mcp.json"):
        p = ROOT / rel
        if p.is_file():
            (hedef / Path(rel).parent.name).mkdir(exist_ok=True)
            shutil.copy2(p, hedef / Path(rel).parent.name / p.name)
    kim = ROOT / "kimlik"
    if kim.is_dir():
        shutil.copytree(kim, hedef / "kimlik", ignore=shutil.ignore_patterns("ornekler", "karakterler"), dirs_exist_ok=True)
    return hedef


def _surum_paketi(c: dict, tag_adi: str | None = None) -> Path:
    r = _api_json(f"/repos/{c['repo']}/releases/latest", c["jeton"])
    varlik = next((a for a in r.get("assets", []) if re.fullmatch(r"YSTCoreStudio-[\d.]+\.zip", a["name"])), None)
    if not varlik:
        raise RuntimeError("son sürümde YSTCoreStudio-<sürüm>.zip paketi yok")
    sha = next((a for a in r.get("assets", []) if a["name"] == varlik["name"] + ".sha256" or a["name"].endswith(".sha256")), None)
    beklenen = None
    if sha:
        with _istek(sha["url"], c["jeton"], "application/octet-stream") as rr:
            beklenen = rr.read().decode().split()[0].lower()
    hedef = ORTAM / "yerel" / "guncelleme" / varlik["name"]
    hedef.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with _istek(varlik["url"], c["jeton"], "application/octet-stream", 300) as rr, open(hedef, "wb") as f:
        while True:
            b = rr.read(1 << 20)
            if not b:
                break
            h.update(b)
            f.write(b)
    if beklenen and h.hexdigest() != beklenen:
        hedef.unlink(missing_ok=True)
        raise RuntimeError("indirilen paketin sağlama toplamı uyuşmadı: güncelleme iptal edildi")
    _log(f"paket indirildi ({hedef.stat().st_size // 1_000_000} MB, sağlama toplamı {'doğrulandı' if beklenen else 'yayımlanmamış'})")
    return hedef


def _yerlestir(zip_yol: Path) -> dict:
    degisen, atlanan = 0, 0
    with zipfile.ZipFile(zip_yol) as z:
        adlar = [n for n in z.namelist() if not n.endswith("/")]
        kok = adlar[0].split("/", 1)[0] + "/" if adlar else ""
        for n in adlar:
            rel = n[len(kok):] if n.startswith(kok) else n
            if not rel or ".." in rel.split("/") or rel.startswith("/") or ":" in rel.split("/")[0]:
                continue
            hedef = ROOT / rel
            if rel in KORUNAN_DOSYA or rel.startswith(KORUNAN):
                if rel.startswith("kimlik/") and not hedef.exists():  # kimlik: yalnızca eksik olan şablonlar eklenir
                    hedef.parent.mkdir(parents=True, exist_ok=True)
                    hedef.write_bytes(z.read(n))
                    degisen += 1
                else:
                    atlanan += 1
                continue
            veri = z.read(n)
            if hedef.is_file() and hedef.read_bytes() == veri:
                continue
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_bytes(veri)
            degisen += 1
    return {"degisen": degisen, "korunan": atlanan}


def _sonrasi(onceki_kilit: str) -> list[str]:
    py = ORTAM / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    notlar = []
    gereksinim = SISTEM / "kurulum" / "gereksinim.txt"
    if py.exists() and gereksinim.exists():
        _log("Python bağımlılıkları denetleniyor")
        r = subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(gereksinim)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=NW)
        notlar.append("pip: tamam" if r.returncode == 0 else "pip UYARI: " + (r.stderr or "")[-200:])
        ml = SISTEM / "kurulum" / "gereksinim-ml.txt"   # yapay zekâ paketleri: yalnızca PyTorch zaten kuruluysa güncellenir (yoksa arka plan kurulumu yapar)
        if ml.exists() and (any((ORTAM / "venv").glob("Lib/site-packages/torch-*.dist-info")) or any((ORTAM / "venv").glob("lib/python*/site-packages/torch-*.dist-info"))):
            r = subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(ml)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=NW)
            notlar.append("pip (yapay zekâ paketleri): tamam" if r.returncode == 0 else "pip (yapay zekâ paketleri) UYARI: " + (r.stderr or "")[-200:])
    kilit = ROOT / "package-lock.json"
    yeni_kilit = hashlib.sha256(kilit.read_bytes()).hexdigest() if kilit.is_file() else ""
    if yeni_kilit != onceki_kilit and shutil.which("npm"):
        _log("Remotion/HyperFrames paketleri güncelleniyor (npm)")
        r = subprocess.run([shutil.which("npm"), "ci", "--no-audit", "--no-fund"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=NW)
        notlar.append("npm: tamam" if r.returncode == 0 else "npm UYARI: " + (r.stderr or "")[-200:])
    try:
        sys.path.insert(0, str(SISTEM / "kurulum"))
        sys.path.insert(0, str(SISTEM / "araclar"))
        import onar
        onar.onar()
        notlar.append("onarım: tamam")
        try:
            sys.path.insert(0, str(ROOT / "sistem" / "araclar"))
            import kimlik_sablon
            kimlik_sablon.kur()
        except Exception as e:  # noqa: BLE001
            notlar.append(f"kimlik şablonu UYARI: {type(e).__name__}")
    except Exception as e:  # noqa: BLE001
        notlar.append(f"onarım UYARI: {type(e).__name__}")
    try:
        import importlib.util as u
        sp = u.spec_from_file_location("yst_ayar_g", SISTEM / "ayar" / "ayar.py")
        m = u.module_from_spec(sp)
        sp.loader.exec_module(m)
        e = m.esitle()
        notlar.append(f"ajan dosyaları eşitlendi ({len(e)})")
    except Exception as e:  # noqa: BLE001
        notlar.append(f"ajan eşitleme UYARI: {type(e).__name__}")
    try:
        sys.path.insert(0, str(SISTEM / "arsiv"))
        import arsiv
        arsiv.baglan().close()  # şema yükseltmesi bağlanırken yapılır
        notlar.append("veritabanı şeması: güncel")
    except Exception as e:  # noqa: BLE001
        notlar.append(f"veritabanı UYARI: {type(e).__name__}")
    return notlar


def _is() -> None:
    CALISIYOR.update({"var": True, "adim": "başlıyor", "log": [], "bitti": False, "hata": ""})
    rapor = {"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "onceki": surum(), "yeni": None, "yedek": None, "adimlar": [], "ok": False}
    try:
        c = _oku(CONF, {})
        if not (c.get("repo") and c.get("jeton")):
            raise RuntimeError("depo ve jeton girilmemiş")
        _log("güncelleme var mı bakılıyor")
        k = kontrol()
        if k["hata"]:
            raise RuntimeError(k["hata"])
        if not k["var"]:
            raise RuntimeError("zaten güncel")
        rapor["yeni"] = k["yeni"]
        y = yedekle()
        rapor["yedek"] = str(y.relative_to(ROOT))
        _log(f"yedek alındı: {rapor['yedek']}")
        kilit = ROOT / "package-lock.json"
        onceki_kilit = hashlib.sha256(kilit.read_bytes()).hexdigest() if kilit.is_file() else ""
        if klon_mu():
            if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
                raise RuntimeError("klonda kaydedilmemiş değişiklik var: önce commit/stash et (güncelleme bu yüzden durduruldu; yedek alındı)")
            _log("git pull (yalnızca ileri sarma)")
            r = _git("pull", "--ff-only", "origin", jeton=c["jeton"], zaman=600)
            if r.returncode != 0:
                raise RuntimeError("git pull başarısız: " + (r.stderr or r.stdout)[-300:])
            rapor["adimlar"].append("git pull: " + (r.stdout.strip().splitlines() or [""])[-1])
        else:
            paket = _surum_paketi(c)
            _log("dosyalar yerleştiriliyor (kimlik, projeler ve ayarlar korunur)")
            rapor["adimlar"].append("dosyalar: " + json.dumps(_yerlestir(paket), ensure_ascii=False))
            paket.unlink(missing_ok=True)
        rapor["adimlar"] += _sonrasi(onceki_kilit)
        rapor["yeni_surum"] = surum()
        rapor["ok"] = True
        _log(f"tamam: {rapor['onceki']} → {rapor['yeni_surum']}")
        kontrol()
    except Exception as e:  # noqa: BLE001
        CALISIYOR["hata"] = str(e)
        rapor["hata"] = str(e)
        _log("HATA: " + str(e))
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    CALISIYOR.update({"var": False, "bitti": True})


def guncelle_baslat() -> dict:
    with KILIT:
        if CALISIYOR["var"]:
            return {"ok": False, "mesaj": "güncelleme zaten sürüyor"}
        threading.Thread(target=_is, daemon=True, name="guncelleme").start()
    return {"ok": True}


def yeniden_baslat() -> None:
    """Güncellemeden sonra paneli temiz biçimde yeniden başlatır (yardımcı süreç 3 sn sonra başlatıcıyı çalıştırır, bu süreç çıkar)."""
    py = ORTAM / "venv" / ("Scripts/pythonw.exe" if os.name == "nt" else "bin/python")
    if not py.exists():
        py = Path(sys.executable)
    kod = ("import subprocess,sys,time;time.sleep(3);"
           f"subprocess.Popen([{str(py)!r},{str(SISTEM / 'kurulum' / 'baslat.py')!r},'sessiz'],cwd={str(ROOT)!r},stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL"
           + (",creationflags=0x00000008|0x00000200|0x08000000)" if os.name == "nt" else ",start_new_session=True)"))
    subprocess.Popen([str(py), "-c", kod], cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     **({"creationflags": 0x00000008 | 0x00000200 | 0x08000000} if os.name == "nt" else {"start_new_session": True}))
    (ORTAM / "yerel" / "panel.json").unlink(missing_ok=True)
    threading.Timer(1.0, lambda: os._exit(0)).start()


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    try:
        if a[0] == "durum":
            print(json.dumps(durum(), ensure_ascii=False, indent=1))
        elif a[0] == "kontrol":
            print(json.dumps(kontrol(), ensure_ascii=False, indent=1))
        elif a[0] == "ayar" and len(a) > 1:
            print(json.dumps(ayar_yaz(a[1], a[2] if len(a) > 2 else None), ensure_ascii=False))
        elif a[0] == "guncelle":
            _is()
            print(json.dumps(_oku(RAPOR, {}), ensure_ascii=False, indent=1))
        else:
            print(__doc__)
            return 2
    except (ValueError, RuntimeError) as e:
        print("HATA:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
