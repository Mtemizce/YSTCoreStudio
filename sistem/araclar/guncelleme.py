"""Public GitHub güncellemeleri: salt okunur kontrol, kullanıcı isteğiyle doğrulanmış kurulum."""
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
import stat
import uuid
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
VARSAYILAN_DEPO = "Mtemizce/YSTCoreStudio"
REVIZYON = ORTAM / "yerel" / "guncelleme_revizyon.json"
KILIT = threading.RLock()
MESGUL = lambda: []
# Set by the panel; serialized with request admission and automatic job starts.
BASLANGIC = time.time()

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


def config():
    return {"repo": VARSAYILAN_DEPO, "jeton": "", "dal": "", **_oku(CONF, {})}


def ayar_oku() -> dict:
    d = config()
    return {"repo": d["repo"], "jeton_var": bool(d.get("jeton")), "etkin": bool(d["repo"]), "dal": d.get("dal", "")}


def engel():
    if CALISIYOR["var"]:
        return "Güncelleme kuruluyor; tamamlanana kadar yeni işlem başlatılamaz."
    if CALISIYOR.get("yeniden_baslat"):
        return "Yeni sürüm hazır. Devam etmek için panelde Yeniden başlat düğmesine bas."
    return ""



def ayar_yaz(repo: str, jeton: str | None = None, dal: str | None = None) -> dict:
    repo = (repo or "").strip()
    if repo and not DEPO_RE.match(repo):
        raise ValueError("depo 'sahip/ad' biçiminde olmalı (örn. Mtemizce/YSTCoreStudio)")
    d = _oku(CONF, {})
    if repo != d.get("repo", VARSAYILAN_DEPO):
        d.pop("jeton", None)
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
    CONF.parent.mkdir(parents=True, exist_ok=True)
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
    headers = {"Accept": kabul, "User-Agent": "YSTCoreStudio-guncelleme", "X-GitHub-Api-Version": "2022-11-28"}
    if jeton and urllib.parse.urlparse(url).netloc == urllib.parse.urlparse(API).netloc:
        headers["Authorization"] = f"Bearer {jeton}"
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.build_opener(_Yonlendir).open(req, timeout=zaman)


def _api_json(yol: str, jeton: str = "", yoksa=False):
    try:
        with _istek(yol, jeton) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404 and yoksa:
            return None
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
    """Only reads GitHub/local revision; never fetches or installs code."""
    c = config()
    sonuc = {"son_kontrol": time.strftime("%Y-%m-%d %H:%M:%S"), "var": False, "mevcut": surum(),
             "yeni": None, "notlar": "", "hata": "", "tur": "klon" if klon_mu() else "surum", "repo": c["repo"]}
    try:
        if not c["repo"]:
            raise ValueError("Otomatik güncelleme kontrolü kapalı; depo seçilmedi.")
        if not DEPO_RE.fullmatch(c["repo"]):
            raise ValueError("Geçersiz depo adı")
        release = None if klon_mu() or c.get("dal") else _api_json(f"/repos/{c['repo']}/releases/latest", c["jeton"], yoksa=True)
        if release:
            tag = release.get("tag_name", "")
            sonuc.update(var=_sayilar(tag) > _sayilar(surum()), yeni=tag.lstrip("v"),
                         notlar=(release.get("body") or "")[:1500], release_id=release["id"])
        else:
            dal = c.get("dal") or _api_json(f"/repos/{c['repo']}", c["jeton"])["default_branch"]
            uz = _api_json(f"/repos/{c['repo']}/commits/{urllib.parse.quote(dal, safe='')}", c["jeton"])
            sha = uz["sha"]
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("GitHub revizyonu geçersiz")
            installed = _oku(REVIZYON, {})
            yerel = _git("rev-parse", "HEAD").stdout.strip() if klon_mu() else installed.get("sha") if installed.get("repo") == c["repo"] else None
            var = yerel != sha
            if klon_mu() and var and _git("merge-base", "--is-ancestor", sha, "HEAD").returncode == 0:
                var = False
            sonuc.update(var=var, yeni=sha[:8], sha=sha, dal=dal,
                         notlar=(uz.get("commit", {}).get("message") or "")[:1500])
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.SubprocessError) as e:
        sonuc["hata"] = str(e)
    DURUM.parent.mkdir(parents=True, exist_ok=True)
    temp = DURUM.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
    temp.replace(DURUM)
    return sonuc


def durum() -> dict:
    d = _oku(DURUM, {})
    return {**ayar_oku(), "surum": surum(), "tur": "klon" if klon_mu() else "surum", "kontrol": d, "calisiyor": dict(CALISIYOR), "rapor": _oku(RAPOR, None), "engeller": MESGUL()}


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
    hedef = YEDEK / f"guncelleme-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
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


def _indir(url, token, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix('.part')
    h = hashlib.sha256()
    try:
        with _istek(url, token, "application/octet-stream", 300) as rr, part.open('wb') as f:
            while chunk := rr.read(1 << 20):
                h.update(chunk)
                f.write(chunk)
                if f.tell() > 512 * 1024 * 1024:
                    raise ValueError("Güncelleme paketi 512 MB sınırını aşıyor")
        if expected and h.hexdigest() != expected:
            raise ValueError("Paket SHA256 doğrulaması başarısız; hiçbir dosya değiştirilmedi")
        part.replace(target)
        return target
    finally:
        part.unlink(missing_ok=True)


def _surum_paketi(c, k):
    # Pin release ID from the check, never race against releases/latest.
    r = _api_json(f"/repos/{c['repo']}/releases/{int(k['release_id'])}", c["jeton"])
    asset = next((a for a in r.get('assets', []) if re.fullmatch(r"YSTCoreStudio-[0-9.]+\.zip", a['name'])), None)
    if not asset:
        raise ValueError("Sürümde YSTCoreStudio-<sürüm>.zip paketi bulunamadı")
    digest = asset.get('digest') or ''
    expected = digest[7:] if re.fullmatch(r'sha256:[0-9a-f]{64}', digest) else None
    if not expected:
        checksum = next((a for a in r.get('assets', []) if a['name'] == asset['name'] + '.sha256'), None)
        if checksum:
            with _istek(checksum['url'], c['jeton'], 'application/octet-stream') as rr:
                fields = rr.read(2048).decode().split()
                if fields and re.fullmatch(r'[0-9a-fA-F]{64}', fields[0]):
                    expected = fields[0].lower()
    if not expected:
        raise ValueError("Bu sürümde SHA256 yayımlanmamış; doğrulanamayan paket kurulmadı")
    return _indir(asset['url'], c['jeton'], ORTAM / 'yerel/guncelleme' / asset['name'], expected)


def _dosyalar(z):
    """Validate the ENTIRE archive before writing. Single wrapper, Windows-safe names."""
    files = [i for i in z.infolist() if not i.is_dir()]
    if not files or len(files) > 30000 or sum(i.file_size for i in files) > 1024 * 1024 * 1024:
        raise ValueError('Geçersiz/büyük güncelleme arşivi')
    roots = {i.filename.split('/')[0] for i in files}
    if len(roots) != 1 or any('/' not in i.filename for i in files):
        raise ValueError('Güncelleme arşivinin tek kök klasörü olmalı')
    result, seen = [], set()
    for i in files:
        if chr(92) in i.orig_filename:
            raise ValueError('Arşiv yolunda ters eğik çizgi var')
        parts = i.filename.split('/')
        if any(not x or x in ('.', '..') or x.rstrip(' .') != x or
               re.search(r'[\\:<>"|?*\x00-\x1f]', x) or
               re.fullmatch(r'(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?', x, re.I) for x in parts):
            raise ValueError('Güvensiz arşiv yolu: ' + i.filename)
        if stat.S_ISLNK(i.external_attr >> 16):
            raise ValueError('Güncelleme arşivinde sembolik bağlantı var')
        rel = '/'.join(parts[1:])
        key = rel.casefold()
        if key in seen:
            raise ValueError('Arşivde çakışan dosya: ' + rel)
        seen.add(key)
        if not (ROOT / rel).resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Hedef klasör dışına çıkıyor')
        result.append((rel, i))
    if not {'sistem/surum.json', 'sistem/panel/panel.py'}.issubset(seen):
        raise ValueError('Eksik uygulama paketi')
    return result


def _kaynak_paketi(c, k):
    sha = k['sha']
    tree = _api_json(f"/repos/{c['repo']}/git/trees/{sha}?recursive=1", c['jeton'])
    if tree.get('truncated'):
        raise ValueError('Depo dosya listesi eksik; sürüm paketi yayımlanmalı')
    blobs = {i['path']: i['sha'] for i in tree['tree'] if i['type'] == 'blob'}
    if any(i.get('mode') in ('120000', '160000') for i in tree['tree']):
        raise ValueError('Kaynak paketinde bağlantı/alt depo desteklenmiyor')
    target = _indir(f"/repos/{c['repo']}/zipball/{sha}", c['jeton'], ORTAM / 'yerel/guncelleme' / (sha + '.zip'))
    with zipfile.ZipFile(target) as z:
        files = _dosyalar(z)
        if {r for r, _ in files} != set(blobs):
            raise ValueError('Kaynak paketi dosya listesi revizyonla uyuşmuyor')
        for rel, info in files:
            data = z.read(info)
            actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if actual != blobs[rel]:
                raise ValueError('Kaynak dosya doğrulaması başarısız: ' + rel)
    return target


def korunan(rel):
    name = rel.casefold()
    return name in KORUNAN_DOSYA or name.startswith(KORUNAN)


def _geri_al(yedek):
    entries = _oku(yedek / 'dosyalar.json', [])
    for rel, existed in reversed(entries):
        target = ROOT / rel
        if existed:
            shutil.copy2(yedek / 'kod' / rel, target)
        else:
            target.unlink(missing_ok=True)


def _yerlestir(zip_yol, yedek=None):
    yedek = yedek or yedekle()
    entries, skipped = [], 0
    with zipfile.ZipFile(zip_yol) as z:
        files = _dosyalar(z)
        stage = yedek / 'yeni'
        for rel, info in files:
            if korunan(rel):
                skipped += 1
                continue
            data = z.read(info)
            target = ROOT / rel
            if target.is_file() and target.read_bytes() == data:
                continue
            if target.exists() and not target.is_file():
                raise ValueError('Dosya hedefi klasör: ' + rel)
            (stage / rel).parent.mkdir(parents=True, exist_ok=True)
            (stage / rel).write_bytes(data)
            if target.exists():
                old = yedek / 'kod' / rel
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, old)
            entries.append((rel, target.exists()))
        # Durable rollback receipt before the first mutation.
        (yedek / 'dosyalar.json').write_text(json.dumps(entries), encoding='utf-8')
        try:
            for rel, _ in entries:
                target = ROOT / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                (stage / rel).replace(target)
                if rel.endswith(('.sh', '.command')):
                    target.chmod(target.stat().st_mode | 0o111)
        except Exception:
            _geri_al(yedek)
            raise
    return {'degisen': len(entries), 'korunan': skipped}


def _sonrasi(onceki_kilit: str) -> list[str]:
    py = ORTAM / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    notlar = []
    gereksinim = SISTEM / "kurulum" / "gereksinim.txt"
    if not py.exists() or not gereksinim.exists():
        raise RuntimeError("Python ortamı eksik; Başlat üzerinden kurulumu tamamla")
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
    if yeni_kilit != onceki_kilit and not shutil.which("npm"):
        raise RuntimeError("Node.js/npm eksik; bağımlılıklar güncellenemedi")
    if yeni_kilit != onceki_kilit and shutil.which("npm"):
        _log("Remotion/HyperFrames paketleri güncelleniyor (npm)")
        r = subprocess.run([shutil.which("npm"), "ci", "--no-audit", "--no-fund"], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=NW)
        notlar.append("npm: tamam" if r.returncode == 0 else "npm UYARI: " + (r.stderr or "")[-200:])
    try:
        sys.path.insert(0, str(SISTEM / "kurulum"))
        sys.path.insert(0, str(SISTEM / "araclar"))
        import onar
        repair = onar.onar()
        if repair.get("uyarilar") or repair.get("venv_yeniden_kur"):
            raise RuntimeError("; ".join(repair.get("uyarilar", [])) or "Python ortamı onarılmalı")
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
    sorun = [n for n in notlar if 'UYARI:' in n]
    if sorun:
        raise RuntimeError('Bağımlılık/onarım tamamlanamadı: ' + '; '.join(sorun))
    return notlar


def _git_kur(c, k):
    status = _git('status', '--porcelain', '--untracked-files=all')
    if status.returncode or status.stdout.strip():
        raise ValueError('Yerel kod değişiklikleri var; güncelleme dosyaların üzerine yazmadı. Önce değişiklikleri commit/stash ile koru.')
    sha = k['sha']
    old = _git('rev-parse', 'HEAD').stdout.strip()
    r = _git('fetch', '--no-tags', 'https://github.com/' + c['repo'] + '.git', sha, jeton=c['jeton'], zaman=600)
    if r.returncode or _git('rev-parse', 'FETCH_HEAD').stdout.strip() != sha:
        raise ValueError('Kontrol edilen Git revizyonu alınamadı')
    if _git('merge-base', '--is-ancestor', 'HEAD', sha).returncode:
        raise ValueError('Yerel dal uzak depoyla ayrışmış; otomatik birleştirme yapılmadı')
    changed = _git('diff', '--name-only', '-z', 'HEAD', sha)
    if changed.returncode or any(korunan(p) for p in changed.stdout.split('\0') if p):
        raise ValueError('Güncelleme korunan kullanıcı dosyalarını değiştiriyor; otomatik kurulum durduruldu')
    # Git itself refuses overwriting local files that appear after the preflight.
    r = _git('merge', '--ff-only', '--no-edit', sha)
    if r.returncode:
        raise ValueError('Git ileri sarma başarısız; yerel değişiklikler korunuyor')
    return old


def _is() -> None:
    CALISIYOR.update(var=True, adim='başlıyor', log=[], bitti=False, hata='')
    rapor = {'zaman': time.strftime('%Y-%m-%d %H:%M:%S'), 'onceki': surum(), 'yeni': None, 'yedek': None, 'adimlar': [], 'ok': False}
    y = None
    applied = False
    try:
        busy = MESGUL()
        if busy:
            raise ValueError('Önce devam eden işleri bitir: ' + ', '.join(busy))
        c = config()
        k = kontrol()
        if k['hata'] or not k['var']:
            raise ValueError(k['hata'] or 'Zaten güncel')
        rapor['yeni'] = k['yeni']
        # Download and verify before taking backups or modifying any code.
        paket = None if klon_mu() else _surum_paketi(c, k) if k.get('release_id') else _kaynak_paketi(c, k)
        y = yedekle()
        rapor['yedek'] = str(y.relative_to(ROOT))
        _log('Yedek alındı: ' + rapor['yedek'])
        lockfile = ROOT / 'package-lock.json'
        previous = hashlib.sha256(lockfile.read_bytes()).hexdigest() if lockfile.is_file() else ''
        if klon_mu():
            rapor['onceki_sha'] = _git_kur(c, k)
        else:
            rapor['adimlar'].append('Dosyalar: ' + json.dumps(_yerlestir(paket, y)))
        applied = True
        rapor['adimlar'] += _sonrasi(previous)
        if k.get('sha'):
            REVIZYON.parent.mkdir(parents=True, exist_ok=True)
            REVIZYON.write_text(json.dumps({'repo': c['repo'], 'sha': k['sha']}), encoding='utf-8')
        rapor.update(ok=True, yeni_surum=surum())
        CALISIYOR['yeniden_baslat'] = True
        _log('Güncelleme hazır. Kullanıcı istediğinde panel yeniden başlatılacak.')
        kontrol()
    except Exception as e:
        if applied:
            if not klon_mu() and y:
                try:
                    _geri_al(y)
                    rapor['adimlar'].append('Uygulama dosyaları önceki sürüme geri alındı.')
                except Exception as rollback:
                    rapor['adimlar'].append('Geri alma başarısız: ' + str(rollback))
            # Never reset a developer working tree or claim pip/npm/DB migrations were undone.
            rapor['onarim_gerekli'] = True
            CALISIYOR['yeniden_baslat'] = True
            rapor['adimlar'].append('Bağımlılıklar/veritabanı için Başlat üzerinden onarım gerekebilir; yedek korundu.')
        CALISIYOR['hata'] = str(e)
        rapor['hata'] = str(e)
        _log('HATA: ' + str(e))
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding='utf-8')
    CALISIYOR.update(var=False, bitti=True)


def guncelle_baslat() -> dict:
    with KILIT:
        if engel():
            return {'ok': False, 'mesaj': engel()}
        busy = MESGUL()
        if busy:
            return {'ok': False, 'mesaj': 'İşlerin kesilmemesi için önce tamamla/kapat: ' + ', '.join(busy)}
        CALISIYOR.update(var=True, bitti=False, hata='', log=[], adim='başlıyor')
        try:
            threading.Thread(target=_is, daemon=True, name='guncelleme').start()
        except Exception:
            CALISIYOR['var'] = False
            raise
    return {'ok': True}


def yeniden_baslat() -> None:
    """Güncellemeden sonra paneli temiz biçimde yeniden başlatır (yardımcı süreç 3 sn sonra başlatıcıyı çalıştırır, bu süreç çıkar)."""
    if CALISIYOR['var'] or MESGUL():
        raise ValueError('İşlem sürerken yeniden başlatılamaz; önce işleri kaydet ve bitir.')
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
