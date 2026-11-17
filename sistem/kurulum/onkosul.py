#!/usr/bin/env python3
"""Sistem analizi: Başlat.cmd ve panelin 'Sistem' kartı bunu kullanır. Yalnızca standart kütüphane; hiçbir şey KURMAZ, yalnızca denetler
ve eksikler için kopyalanabilir komut + indirme adresi verir (yetki gerektiren kurulumlar kullanıcıya bırakılır).

  python sistem/kurulum/onkosul.py            insan okunur özet
  python sistem/kurulum/onkosul.py --json     makine okunur (sihirbaz ve panel)

Her öğe: id, ad, seviye (zorunlu | onerilen | bilgi), durum (tamam | eksik | eski | uyari), surum, neden, kurulum{komut, winget, powershell, indir, not}.
Test/demo için: YST_ONKOSUL_EKSIK=git,node ortam değişkeni bu öğeleri "yokmuş gibi" gösterir.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORTAM = ROOT / "sistem" / "ortam"
YEREL = ORTAM / "yerel"
KURULUM_OK = YEREL / "kurulum.ok"
NW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

# Kurulumun ilk seferde dokunduğu adresler (yalnızca dosya/paket indirir; hesap, anahtar, telemetri yok)
AGLAR = {
    "GitHub (Kurgu ve skill'ler)": "https://github.com",
    "npm (Remotion, HyperFrames)": "https://registry.npmjs.org",
    "PyPI (Python paketleri)": "https://pypi.org",
    "PyPI dosyaları": "https://files.pythonhosted.org",
    "PyTorch": "https://download.pytorch.org",
    "Hugging Face (model ağırlığı)": "https://huggingface.co",
}
MIN_DISK_GB_ILK = 12.0
MIN_DISK_GB = 2.0


# ------------------------------------------------------------------ yardımcılar
def yol_yenile() -> None:
    """winget/yükleyici az önce PATH'e bir şey eklediyse bu süreç bunu görmez: kayıt defterinden PATH'i yeniden oku (Windows)."""
    if os.name != "nt":
        return
    try:
        import winreg
        parcalar = []
        for kok, anahtar in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"), (winreg.HKEY_CURRENT_USER, "Environment")):
            try:
                with winreg.OpenKey(kok, anahtar) as k:
                    v, _ = winreg.QueryValueEx(k, "Path")
                    parcalar.append(os.path.expandvars(v))
            except OSError:
                pass
        mevcut = os.environ.get("PATH", "").split(os.pathsep)
        for p in os.pathsep.join(parcalar).split(os.pathsep):
            if p and p not in mevcut:
                mevcut.append(p)
        os.environ["PATH"] = os.pathsep.join(mevcut)
    except Exception:  # noqa: BLE001
        pass


def _ek_klasorler(ad: str) -> list[Path]:
    """Standart kurulum yerleri (PATH'te olmasa da bulmak için)."""
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    yerel = os.environ.get("LOCALAPPDATA", "")
    ev = str(Path.home())
    ad = ad.lower()
    if ad == "git":
        return [Path(p) / "Git" / "cmd" for p in pf] + [Path(yerel) / "Programs" / "Git" / "cmd"]
    if ad in ("node", "npm"):
        return [Path(p) / "nodejs" for p in pf] + [Path(yerel) / "Programs" / "nodejs"]
    if ad == "claude":
        return [Path(ev) / ".local" / "bin", Path(yerel) / "Programs" / "claude", Path(os.environ.get("APPDATA", "")) / "npm"]
    return []


def _simule_eksik() -> set[str]:
    """Test/demo: YST_ONKOSUL_EKSIK=git,node ya da YST_ONKOSUL_EKSIK_DOSYA=<dosya> (her taramada yeniden okunur; satır/virgül ayrımlı)."""
    kume = {x.strip() for x in (os.environ.get("YST_ONKOSUL_EKSIK") or "").split(",") if x.strip()}
    f = os.environ.get("YST_ONKOSUL_EKSIK_DOSYA")
    if f:
        try:
            kume |= {x.strip() for x in Path(f).read_text(encoding="utf-8").splitlines() for x in x.split(",") if x.strip()}
        except OSError:
            pass
    return kume


def bul(ad: str) -> str | None:
    if ad in _simule_eksik():
        return None
    w = shutil.which(ad)
    if w:
        return w
    for d in _ek_klasorler(ad):
        for uz in ("", ".exe", ".cmd"):
            p = d / (ad + uz)
            if p.is_file():
                return str(p)
    return None


def surum(komut: list[str], zaman: int = 20) -> str:
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=zaman, creationflags=NW)
        return (r.stdout or r.stderr or "").strip().splitlines()[0] if (r.stdout or r.stderr) else ""
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return ""


def _sayi(s: str) -> tuple[int, ...]:
    import re
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def _os_kurulum(id_: str, kur: dict) -> dict:
    """Windows dışında winget/PowerShell yerine bu sistemin paket yöneticisi komutu."""
    if os.name == "nt" or not kur:
        return kur
    mac = sys.platform == "darwin"
    if mac:
        k = {"python": "brew install python@3.12", "git": "brew install git", "node": "brew install node", "claude": "curl -fsSL https://claude.ai/install.sh | bash"}.get(id_)
    elif shutil.which("apt-get") or shutil.which("apt"):
        k = {"python": "sudo apt install python3 python3-venv python3-pip", "git": "sudo apt install git", "node": "sudo apt install nodejs npm", "claude": "curl -fsSL https://claude.ai/install.sh | bash"}.get(id_)
    elif shutil.which("dnf"):
        k = {"python": "sudo dnf install python3 python3-pip", "git": "sudo dnf install git", "node": "sudo dnf install nodejs npm", "claude": "curl -fsSL https://claude.ai/install.sh | bash"}.get(id_)
    elif shutil.which("pacman"):
        k = {"python": "sudo pacman -S python python-pip", "git": "sudo pacman -S git", "node": "sudo pacman -S nodejs npm", "claude": "curl -fsSL https://claude.ai/install.sh | bash"}.get(id_)
    else:
        k = None
    y = {a: b for a, b in kur.items() if a not in ("winget", "powershell")}
    if k:
        y["komut"] = k
    if id_ == "python":
        y["not"] = "Python 3.10–3.13 (venv modülüyle: Debian/Ubuntu'da python3-venv paketi gerekir)."
    elif id_ == "node":
        y["not"] = "Node.js 20 ya da üstü (npm ile). Dağıtımın paketi eskiyse https://nodejs.org adresinden LTS kur."
    return y


def oge(id_: str, ad: str, seviye: str, durum: str, surum_: str = "", neden: str = "", kurulum: dict | None = None, atlanabilir: bool = False) -> dict:
    kurulum = _os_kurulum(id_, kurulum or {})
    return {"id": id_, "ad": ad, "seviye": seviye, "durum": durum, "surum": surum_, "neden": neden, "kurulum": kurulum or {}, "atlanabilir": atlanabilir}


# ------------------------------------------------------------------ denetimler
def k_python() -> dict:
    v = sys.version_info
    s = f"{v.major}.{v.minor}.{v.micro}"
    kur = {"winget": "winget install --id Python.Python.3.12 -e --source winget", "indir": "https://www.python.org/downloads/windows/",
           "not": "Kurarken 'Add python.exe to PATH' kutusunu işaretle. 3.10–3.13 arası uygundur."}
    if v < (3, 10):
        return oge("python", "Python 3.10+", "zorunlu", "eski", s, "Stüdyo Python 3.10 ve üstünü ister.", kur)
    if v >= (3, 14):
        return oge("python", "Python 3.10–3.13", "zorunlu", "uyari", s, "3.14 ve üstü için PyTorch paketleri henüz olmayabilir; 3.12 önerilir.", kur)
    return oge("python", "Python 3.10+", "zorunlu", "tamam", s)


def k_git() -> dict:
    p = bul("git")
    kur = {"winget": "winget install --id Git.Git -e --source winget", "indir": "https://git-scm.com/download/win",
           "not": "Kurulumdan sonra yeni bir pencerede 'Devam et' de. Git Bash da bu pakettedir (Claude Code kabuk komutları için kullanır)."}
    if not p:
        return oge("git", "Git", "zorunlu", "eksik", "", "Kurgu, skill'ler ve dış bileşenler kendi depolarından git ile çekilir.", kur)
    return oge("git", "Git", "zorunlu", "tamam", surum([p, "--version"]).replace("git version ", ""))


def k_node() -> dict:
    p = bul("node")
    kur = {"winget": "winget install --id OpenJS.NodeJS.LTS -e --source winget", "indir": "https://nodejs.org/en/download",
           "not": "LTS sürümünü seç (20 ya da üstü). Kurulum npm'i de getirir."}
    if not p:
        return oge("node", "Node.js 20+ (npm ile)", "zorunlu", "eksik", "", "Remotion ve HyperFrames sahne/animasyon çizimi için.", kur)
    s = surum([p, "--version"])
    if _sayi(s)[:1] < (20,):
        return oge("node", "Node.js 20+ (npm ile)", "zorunlu", "eski", s, "Sürüm 20 ya da üstü gerekir.", kur)
    if not bul("npm"):
        return oge("node", "Node.js 20+ (npm ile)", "zorunlu", "eksik", s, "npm bulunamadı (Node.js'i npm bileşeniyle yeniden kur).", kur)
    return oge("node", "Node.js 20+ (npm ile)", "zorunlu", "tamam", s)


def k_claude() -> dict:
    p = bul("claude")
    kur = {"powershell": "irm https://claude.ai/install.ps1 | iex", "winget": "winget install Anthropic.ClaudeCode", "indir": "https://code.claude.com/docs/en/setup",
           "not": "Yönetici izni gerekmez. Kurduktan sonra bir pencerede 'claude' yazıp hesabınla giriş yap (Claude aboneliği ya da API gerekir)."}
    if not p:
        return oge("claude", "Claude Code", "zorunlu", "eksik", "", "Video üretimini yürüten ajanlar Claude Code ile çalışır. Panel onsuz da açılır; arşiv ve iyileştirme çalışır, video üretimi çalışmaz.",
                   kur, atlanabilir=True)
    return oge("claude", "Claude Code", "zorunlu", "tamam", surum([p, "--version"]))


def k_disk() -> dict:
    ilk = not KURULUM_OK.exists()
    gerek = MIN_DISK_GB_ILK if ilk else MIN_DISK_GB
    try:
        bos = shutil.disk_usage(ROOT).free / 1e9
    except OSError:
        return oge("disk", "Boş disk alanı", "bilgi", "uyari", "", "Ölçülemedi.")
    if bos < gerek:
        return oge("disk", "Boş disk alanı", "zorunlu", "eksik", f"{bos:.1f} GB", f"Bu klasörün diskinde en az {gerek:.0f} GB boş yer gerekir"
                   f"{' (PyTorch, modeller, npm paketleri)' if ilk else ''}. Yer aç ya da klasörü daha boş bir diske taşı.")
    return oge("disk", "Boş disk alanı", "zorunlu", "tamam", f"{bos:.0f} GB boş")


def k_ag() -> list[dict]:
    """Yalnızca ilk kurulumda gerekli: indirme adreslerine ulaşılabiliyor mu (paralel, kısa zaman aşımı)."""
    if KURULUM_OK.exists():
        return []
    sonuc: dict[str, str | None] = {}

    def dene(ad, url):
        for deneme in range(2):  # geçici yavaşlık yanlış alarm vermesin: bir kez daha dene
            try:
                urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "YSTCoreStudio-onkosul"}), timeout=10).close()
                sonuc[ad] = None
                return
            except urllib.error.HTTPError:
                sonuc[ad] = None  # sunucu yanıt verdi (403/405 olabilir): ulaşılabilir
                return
            except Exception as e:  # noqa: BLE001
                sonuc[ad] = str(getattr(e, "reason", e))[:80]

    th = [threading.Thread(target=dene, args=(a, u), daemon=True) for a, u in AGLAR.items()]
    for t in th:
        t.start()
    for t in th:
        t.join(25)
    yok = [a for a in AGLAR if sonuc.get(a, "zaman aşımı") is not None]
    if not yok:
        return [oge("ag", "İnternet (ilk kurulum indirmeleri)", "zorunlu", "tamam", f"{len(AGLAR)} adres erişilebilir")]
    return [oge("ag", "İnternet (ilk kurulum indirmeleri)", "zorunlu", "eksik", "", "Ulaşılamayan: " + ", ".join(yok) + ". İnternet/proxy/güvenlik duvarını kontrol et.",
                {"not": "Kurumsal ağdaysan bu adreslere izin gerekir. Bağlantı gelince 'Devam et'."})]


def k_gpu() -> dict:
    p = bul("nvidia-smi")
    if p:
        ad = surum([p, "--query-gpu=name", "--format=csv,noheader"])
        return oge("gpu", "Ekran kartı (foto iyileştirme hızı)", "bilgi", "tamam", ad or "NVIDIA", "CUDA'lı PyTorch kurulur; Real-ESRGAN hızlı çalışır.")
    return oge("gpu", "Ekran kartı (foto iyileştirme hızı)", "bilgi", "uyari", "NVIDIA yok", "CPU'lu PyTorch kurulur; foto iyileştirme çalışır ama yavaştır (fotoğraf başına dakikalar).")


def k_uzun_yol() -> list[dict]:
    if os.name != "nt" or len(str(ROOT)) <= 70:
        return []
    return [oge("uzunyol", "Klasör yolu uzun", "onerilen", "uyari", f"{len(str(ROOT))} karakter",
                "node_modules içindeki derin yollar Windows'un 260 karakter sınırına takılabilir. Klasörü daha kısa bir yola (örn. C:\\YST) taşı "
                "ya da yönetici olarak 'Uzun yol desteği'ni aç.",
                {"powershell": "New-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem' -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force",
                 "not": "Yönetici PowerShell gerekir; bir kez yapılır, yeniden başlatma gerekebilir."})]


def k_ffmpeg() -> dict:
    var = bool(bul("ffmpeg")) and bool(bul("ffprobe"))
    if var or (YEREL / "veri" / "Kurgu" / "ffmpeg").exists():
        return oge("ffmpeg", "ffmpeg", "bilgi", "tamam", "var")
    return oge("ffmpeg", "ffmpeg", "bilgi", "uyari", "yok", "Kurulum Kurgu'nun kendi indiricisiyle (yönetici izni gerekmez) otomatik indirir.")


# ------------------------------------------------------------------ ana giriş
def tara(ag: bool = True) -> dict:
    yol_yenile()
    ogeler = [k_python(), k_git(), k_node(), k_claude(), k_disk()]
    if ag:
        ogeler += k_ag()
    ogeler += k_uzun_yol() + [k_ffmpeg(), k_gpu()]
    atlanan = set((_atlananlar()))
    for o in ogeler:
        if o["id"] in atlanan and o["durum"] != "tamam" and o["atlanabilir"]:
            o["atlandi"] = True
    engel = [o for o in ogeler if o["seviye"] == "zorunlu" and o["durum"] in ("eksik", "eski") and not o.get("atlandi")]
    return {"ogeler": ogeler, "tamam": not engel, "engel": [o["id"] for o in engel], "ilk_kurulum": not KURULUM_OK.exists(),
            "zaman": time.strftime("%H:%M:%S"), "makine_os": f"{sys.platform}", "kok": str(ROOT)}


ATLA_DOSYA = YEREL / "onkosul_atla.json"


def _atlananlar() -> list[str]:
    try:
        return json.loads(ATLA_DOSYA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def atla(id_: str) -> None:
    """Atlanabilir öğeyi (Claude Code gibi) 'sonra kurarım' diye işaretle."""
    YEREL.mkdir(parents=True, exist_ok=True)
    l = set(_atlananlar())
    l.add(id_)
    ATLA_DOSYA.write_text(json.dumps(sorted(l)), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = tara()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["tamam"] else 1
    simge = {"tamam": "tamam ", "eksik": "EKSİK ", "eski": "ESKİ  ", "uyari": "uyarı "}
    for o in r["ogeler"]:
        print(f"  {simge.get(o['durum'], o['durum'])} {o['ad']:38} {o['surum']}")
        if o["durum"] != "tamam" and o["neden"]:
            print(f"         {o['neden']}")
        for k in ("komut", "winget", "powershell"):
            if o["durum"] in ("eksik", "eski") and o["kurulum"].get(k):
                print(f"         {k}: {o['kurulum'][k]}")
        if o["durum"] in ("eksik", "eski") and o["kurulum"].get("indir"):
            print(f"         indir: {o['kurulum']['indir']}")
    print("\n" + ("Her şey hazır." if r["tamam"] else "Eksikler var: " + ", ".join(r["engel"])))
    return 0 if r["tamam"] else 1


if __name__ == "__main__":
    sys.exit(main())
