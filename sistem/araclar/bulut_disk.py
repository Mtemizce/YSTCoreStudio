#!/usr/bin/env python3
"""Bulut disk (Google Drive, OneDrive, Dropbox ...) arşiv kaynağı: rclone üzerinden, SALT OKUNUR.

Neden rclone: Google/Microsoft OAuth'u için her kullanıcının kendi bulut projesi açması gerekmez; rclone'un yetkilendirmesi tarayıcıda tek tıkla yapılır,
jeton bu klasörde (sistem/ortam/yerel/rclone.conf, git'e girmez) durur. Arşiv için Drive'a yalnızca OKUMA izni istenir (scope=drive.readonly).
Dosyalar bilgisayara kendiliğinden inmez: tarama yalnızca liste (ad/boyut/tarih) alır; analiz, önizleme ve projeye kopyalama dosyayı gerektiğinde bir ÖNBELLEĞE indirir
(sistem/ortam/arsiv/onbellek/<arşiv>/, üst sınır ayarlı, en eski silinir).

  python bulut_disk.py durum | kur | uzaklar | klasorler <uzak:yol> | baglan <ad> <drive|onedrive|dropbox>
Yalnızca standart kütüphane.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORTAM = ROOT / "sistem" / "ortam"
ARAC = ORTAM / "arac"
CONF = ORTAM / "yerel" / "rclone.conf"
ONBELLEK = ORTAM / "arsiv" / "onbellek"
NW = 0x08000000 if os.name == "nt" else 0
UZAK_ADI = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\-]{0,40}$")
UZAK_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\- ]{0,60}:[^\x00-\x1f]{0,400}$")
TURLER = {"drive": "Google Drive", "onedrive": "Microsoft OneDrive", "dropbox": "Dropbox"}
INDIRME = "https://downloads.rclone.org"
# downloads.rclone.org Python'un varsayılan "Python-urllib" kimliğini 403 ile reddeder (rclone hiçbir platformda kurulamıyordu): genel bir istemci adı gönderilir
UA = "local-studio-setup/1.0 (rclone installer)"
VIDEO_EN_COK_MB = 300.0  # bulut arşivde analiz için bundan büyük video indirilmez


def _ac(url: str, zaman: int):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=zaman)


# ------------------------------------------------------------------ rclone'u bul / kur
def _exe_adi() -> str:
    return "rclone.exe" if os.name == "nt" else "rclone"


def rclone() -> str | None:
    ov = os.environ.get("YST_RCLONE")  # testler/özel kurulum: bu yoldaki rclone kullanılır
    if ov and Path(ov).is_file():
        return ov
    yerel = ARAC / _exe_adi()
    if yerel.is_file():
        return str(yerel)
    return shutil.which("rclone")


def _os_ad() -> tuple[str, str]:
    s = {"win32": "windows", "darwin": "osx"}.get(sys.platform, "linux")
    m = platform.machine().lower()
    a = "arm64" if m in ("arm64", "aarch64") else ("amd64" if m in ("amd64", "x86_64", "x64") else "386")
    return s, a


def kur() -> dict:
    """Resmî rclone paketini (downloads.rclone.org) indirir, SHA256'sını resmî listeyle doğrular, sistem/ortam/arac/ altına açar (~25 MB)."""
    if rclone():
        return {"ok": True, "yol": rclone(), "not": "zaten kurulu"}
    s, a = _os_ad()
    with _ac(f"{INDIRME}/version.txt", 30) as r:
        surum = r.read().decode().strip().split()[-1]  # "rclone v1.xx.y"
    if not re.fullmatch(r"v\d+\.\d+\.\d+", surum):
        raise RuntimeError("rclone sürüm bilgisi okunamadı")
    ad = f"rclone-{surum}-{s}-{a}.zip"
    with _ac(f"{INDIRME}/{surum}/SHA256SUMS", 30) as r:
        sums = r.read().decode("utf-8", "replace")
    beklenen = next((ln.split()[0] for ln in sums.splitlines() if ln.strip().endswith(" " + ad)), None)
    if not beklenen:
        raise RuntimeError(f"{ad} için resmî sağlama toplamı bulunamadı")
    ARAC.mkdir(parents=True, exist_ok=True)
    zip_yol = ARAC / ad
    h = hashlib.sha256()
    with _ac(f"{INDIRME}/{surum}/{ad}", 120) as r, open(zip_yol, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            h.update(b)
            f.write(b)
    if h.hexdigest().lower() != beklenen.lower():
        zip_yol.unlink(missing_ok=True)
        raise RuntimeError("rclone indirmesi resmî sağlama toplamıyla uyuşmadı: iptal edildi")
    with zipfile.ZipFile(zip_yol) as z:
        uye = next(n for n in z.namelist() if n.endswith("/" + _exe_adi()) and n.count("/") == 1)
        with z.open(uye) as src, open(ARAC / _exe_adi(), "wb") as dst:
            shutil.copyfileobj(src, dst)
    zip_yol.unlink(missing_ok=True)
    if os.name != "nt":
        (ARAC / _exe_adi()).chmod(0o755)
    return {"ok": True, "yol": str(ARAC / _exe_adi()), "surum": surum, "sha256": beklenen}


def _env() -> dict:
    e = dict(os.environ)
    CONF.parent.mkdir(parents=True, exist_ok=True)
    e["RCLONE_CONFIG"] = str(CONF)
    return e


def calistir(args: list[str], zaman: int = 600) -> subprocess.CompletedProcess:
    exe = rclone()
    if not exe:
        raise RuntimeError("rclone kurulu değil (panel → Ayarlar → Konumlar → Bulut disk → 'rclone'u kur')")
    return subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, env=_env(), creationflags=NW)


def uzak_kontrol(u: str) -> str:
    if not isinstance(u, str) or u.startswith("-") or not UZAK_RE.match(u) or ".." in u.replace("\\", "/").split(":", 1)[1].split("/"):
        raise ValueError("uzak yol 'ad:klasör/yol' biçiminde olmalı (örn. gdrive:Arsiv)")
    return u


# ------------------------------------------------------------------ hesap bağlama (tarayıcıda izin)
_BAGLAN = {"durum": "bos", "mesaj": "", "url": None, "ad": None}


def baglan_durumu() -> dict:
    return dict(_BAGLAN)


def baglan_baslat(ad: str, tur: str) -> dict:
    """Arka planda `rclone config create` çalıştırır: tarayıcı açılır, kullanıcı izin verir, jeton rclone.conf'a yazılır."""
    if tur not in TURLER:
        raise ValueError("tür drive, onedrive ya da dropbox olmalı")
    if not UZAK_ADI.match(ad or ""):
        raise ValueError("hesap adı harf/rakam/-/_ olmalı (örn. gdrive)")
    exe = rclone()
    if not exe:
        raise RuntimeError("önce rclone'u kur")
    if _BAGLAN["durum"] == "bekliyor":
        return {"ok": False, "mesaj": "bir bağlanma zaten sürüyor (tarayıcıdaki izin ekranını tamamla)"}
    ek = ["scope=drive.readonly"] if tur == "drive" else []  # Drive: yalnızca okuma izni
    _BAGLAN.update({"durum": "bekliyor", "mesaj": "Tarayıcıda izin ekranı açılıyor…", "url": None, "ad": ad})

    def is_():
        try:
            p = subprocess.Popen([exe, "config", "create", ad, tur, *ek], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace", env=_env(), creationflags=NW)
            son = time.time() + 300
            for satir in p.stdout:  # type: ignore[union-attr]
                m = re.search(r"https?://127\.0\.0\.1:\d+/auth\S*", satir)
                if m:
                    _BAGLAN["url"] = m.group(0)
                    _BAGLAN["mesaj"] = "Tarayıcı kendiliğinden açılmadıysa bağlantıyı aç ve izin ver."
                if time.time() > son:
                    p.kill()
                    break
            p.wait(timeout=10)
            ok = p.returncode == 0 and any(u.startswith(ad + ":") for u in uzaklar_liste())
            _BAGLAN.update({"durum": "tamam" if ok else "hata", "mesaj": "Bağlandı." if ok else "İzin verilmedi ya da süre doldu (5 dk). Tekrar dene."})
        except Exception as e:  # noqa: BLE001
            _BAGLAN.update({"durum": "hata", "mesaj": f"{type(e).__name__}: {e}"})

    threading.Thread(target=is_, daemon=True).start()
    return {"ok": True}


def uzaklar_liste() -> list[str]:
    if not rclone():
        return []
    r = calistir(["listremotes"], 30)
    return [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]


def uzaklar() -> list[dict]:
    if not rclone():
        return []
    r = calistir(["listremotes", "--long"], 30)
    out = []
    for ln in (r.stdout or "").splitlines():
        a, _, t = ln.partition(":")
        if a.strip():
            out.append({"ad": a.strip(), "tur": t.strip(), "tur_adi": TURLER.get(t.strip(), t.strip())})
    return out


def durum() -> dict:
    exe = rclone()
    return {"kurulu": bool(exe), "yol": exe, "uzaklar": uzaklar() if exe else [], "baglan": baglan_durumu(), "turler": TURLER, "yapilandirma": str(CONF)}


def sil(ad: str) -> None:
    if not UZAK_ADI.match(ad or ""):
        raise ValueError("geçersiz ad")
    calistir(["config", "delete", ad], 30)


# ------------------------------------------------------------------ gezinme / liste / indirme
def klasorler(uzak: str) -> list[str]:
    r = calistir(["lsjson", uzak_kontrol(uzak), "--dirs-only", "--max-depth", "1", "--no-mimetype", "--no-modtime"], 180)
    if r.returncode != 0:
        raise RuntimeError("rclone: " + (r.stderr or "")[-300:])
    return sorted(x["Path"] for x in json.loads(r.stdout or "[]"))


def dosyalar(uzak: str):
    """Arşiv taraması için: uzak klasördeki tüm dosyalar (özyinelemeli) → [{Path, Size, ModTime}]."""
    r = calistir(["lsjson", uzak_kontrol(uzak), "-R", "--files-only", "--no-mimetype", "--fast-list", "--drive-skip-gdocs"], 3600)
    if r.returncode != 0:
        raise RuntimeError("rclone: " + (r.stderr or "")[-300:])
    return json.loads(r.stdout or "[]")


def onbellek_yolu(arsiv_adi: str) -> Path:
    p = ONBELLEK / re.sub(r"[^a-z0-9_-]+", "-", arsiv_adi.lower()).strip("-")
    p.mkdir(parents=True, exist_ok=True)
    return p


_indirilen = {"n": 0}


def getir(uzak: str, rel: str, arsiv_adi: str, sinir_gb: float = 5.0) -> Path:
    """Uzak dosyayı önbelleğe indirir (varsa indirmez) ve yerel yolunu döndürür."""
    uzak_kontrol(uzak)
    parcalar = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parcalar or any(p in ("..", ".") for p in parcalar):
        raise ValueError("geçersiz dosya yolu")
    hedef = onbellek_yolu(arsiv_adi).joinpath(*parcalar)
    if hedef.is_file() and hedef.stat().st_size > 0:
        return hedef
    hedef.parent.mkdir(parents=True, exist_ok=True)
    kaynak = uzak.rstrip("/") + ("" if uzak.endswith(":") else "/") + "/".join(parcalar)
    r = calistir(["copyto", kaynak, str(hedef), "--drive-skip-gdocs", "--retries", "2"], 1800)
    if r.returncode != 0 or not hedef.is_file():
        hedef.unlink(missing_ok=True)
        raise RuntimeError("indirilemedi: " + (r.stderr or "")[-200:])
    _indirilen["n"] += 1
    if _indirilen["n"] % 20 == 0:
        onbellek_temizle(sinir_gb)
    return hedef


def onbellek_boyut() -> int:
    return sum(f.stat().st_size for f in ONBELLEK.rglob("*") if f.is_file()) if ONBELLEK.exists() else 0


def onbellek_temizle(sinir_gb: float = 5.0, koru: set[str] | None = None) -> dict:
    """Önbellek sınırı aşıldıysa en eski indirilenleri siler (arşivin kendisine ve projelere dokunmaz)."""
    if not ONBELLEK.exists():
        return {"silinen": 0, "bos": 0}
    dosyalar_ = sorted((f for f in ONBELLEK.rglob("*") if f.is_file()), key=lambda f: f.stat().st_mtime)
    toplam = sum(f.stat().st_size for f in dosyalar_)
    sinir = int(sinir_gb * 1e9)
    silinen = 0
    for f in dosyalar_:
        if toplam <= sinir * 0.8:
            break
        if koru and str(f) in koru:
            continue
        toplam -= f.stat().st_size
        f.unlink(missing_ok=True)
        silinen += 1
    return {"silinen": silinen, "kalan_mb": round(toplam / 1e6, 1)}


def onbellegi_bosalt() -> int:
    n = onbellek_boyut()
    shutil.rmtree(ONBELLEK, ignore_errors=True)
    return n


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    if a[0] == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
    elif a[0] == "kur":
        print(json.dumps(kur(), ensure_ascii=False))
    elif a[0] == "uzaklar":
        print(json.dumps(uzaklar(), ensure_ascii=False))
    elif a[0] == "klasorler" and len(a) > 1:
        print("\n".join(klasorler(a[1])))
    elif a[0] == "baglan" and len(a) > 2:
        baglan_baslat(a[1], a[2])
        while baglan_durumu()["durum"] == "bekliyor":
            time.sleep(1)
        print(json.dumps(baglan_durumu(), ensure_ascii=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
