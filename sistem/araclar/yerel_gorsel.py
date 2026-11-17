#!/usr/bin/env python3
"""Yerel görsel üretim (İSTEĞE BAĞLI, varsayılan KURULU DEĞİL): Z-Image-Turbo + stable-diffusion.cpp. Veri bilgisayardan çıkmaz, hesap/anahtar gerekmez.

Neden isteğe bağlı: modeller ~7 GB, her bilgisayar kaldırmaz. Ekran kartı belleğine (VRAM) göre en küçük uygun kalite seçilir; 4 GB'lık kartlarda da çalışır
(resmî rehber: github.com/leejet/stable-diffusion.cpp/wiki → "How to Use Z-Image on a GPU with Only 4GB VRAM"; --offload-to-cpu ile ağırlıklar yalnızca
hesaplama sırasında VRAM'e alınır, düşük bellek için yavaşlar). Vulkan yapısı kullanılır (NVIDIA/AMD/Intel, CUDA çalışma zamanı gerekmez).
Esin ve atıf: 4 GB'lık kartlarda çalıştırma yöntemi ve model dosyalarını sabit adres + sha256 ile indirme (kilit dosyası) deseni github.com/alexturkey/z-image-turbo-pascal-4gb
(Apache-2.0) projesinden alınmıştır; kod kopyalanmadı. Model: Tongyi-MAI Z-Image-Turbo (Apache-2.0), GGUF: leejet, çalıştırıcı: stable-diffusion.cpp (MIT).
Dosyalar: sistem/ortam/yerel-gorsel/ (git'e girmez). İndirilen her model Hugging Face'in yayımladığı SHA256 ile doğrulanır.

  python sistem/araclar/yerel_gorsel.py durum | kur [--kalite Q4_0] | uret "<istem>" -o cikti.png [--genislik 1024 --yukseklik 576 --tohum N --adim 8]
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
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("YST_GORSEL_KOK") or Path(__file__).resolve().parents[2])
DIZIN = ROOT / "sistem" / "ortam" / "yerel-gorsel"
NW = 0x08000000 if os.name == "nt" else 0
HF = os.environ.get("YST_HF_ADRES") or "https://huggingface.co"
GH = os.environ.get("YST_GH_ADRES") or "https://api.github.com"
PARCALAR = {  # (depo, dosya deseni)
    "model": ("leejet/Z-Image-Turbo-GGUF", "z_image_turbo-{kalite}.gguf"),
    "llm": ("unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
    "vae": ("Comfy-Org/Z-Image-Turbo", "split_files/vae/ae.safetensors"),
}
KALITELER = [("Q3_K", 4500), ("Q4_0", 7500), ("Q5_0", 11000), ("Q6_K", 10**9)]  # (kalite, bu VRAM (MB) sınırına kadar uygun)
KALITE_RE = re.compile(r"^Q[2-8]_[0-9A-Z_]{1,4}$")
KILIT = threading.Lock()
IS = {"var": False, "adim": "", "yuzde": 0, "log": [], "bitti": False, "hata": ""}


def vram_mb() -> int:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return 0
    try:
        r = subprocess.run([exe, "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15, creationflags=NW)
        return max(int(x.strip()) for x in r.stdout.splitlines() if x.strip().isdigit())
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def oneri() -> dict:
    v = vram_mb()
    kalite = next(k for k, sinir in KALITELER if v <= sinir) if v else "Q4_0"
    return {"vram_mb": v, "kalite": kalite, "not": ("ekran kartı bulunamadı: işlemci ile çalışır, görsel başına dakikalar sürer" if not v else
                                                   f"{v} MB VRAM algılandı: {kalite} kalitesi uygun; bellek yetmezse --offload-to-cpu ile yavaşlar ama çalışır")}


def _exe() -> Path | None:
    ov = os.environ.get("YST_SD_CLI")  # ileri düzey / test: kendi sd-cli yolun
    if ov and Path(ov).is_file():
        return Path(ov)
    for ad in ("sd-cli.exe", "sd-cli", "sd.exe", "sd"):
        for p in (DIZIN / "bin" / ad, *(DIZIN / "bin").rglob(ad)):
            if p.is_file():
                return p
    return None


def _dosya(parca: str, kalite: str = "Q4_0") -> Path:
    return DIZIN / "modeller" / Path(PARCALAR[parca][1].format(kalite=kalite)).name


def kurulu_kalite() -> str | None:
    m = DIZIN / "modeller"
    try:
        manifest = json.loads((DIZIN / 'kurulum.json').read_text(encoding='utf-8'))
        selected = manifest.get('_kalite')
        if selected and KALITE_RE.fullmatch(selected):
            return selected
    except (OSError, ValueError):
        pass
    for p in (m.glob("z_image_turbo-*.gguf") if m.is_dir() else []):
        if p.stat().st_size > 1_000_000:
            return p.stem.split("-", 1)[1]
    return None


def durum() -> dict:
    kk = kurulu_kalite()
    files = [_dosya(k, kk or "Q4_0") for k in ("model", "llm", "vae")]
    try:
        manifest = json.loads((DIZIN / "kurulum.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    kurulu = bool(_exe() and kk and all(p.is_file() and p.stat().st_size > 0 and
                  (p.stat().st_size == manifest.get(p.name, {}).get("boyut") if p.name in manifest else p.stat().st_size > 1_000_000) for p in files))
    boyut = sum(f.stat().st_size for f in DIZIN.rglob("*") if f.is_file()) if DIZIN.is_dir() else 0
    return {"kurulu": kurulu, "kalite": kk, "disk_mb": round(boyut / 1e6), "oneri": oneri(), "is": dict(IS),
            "tahmini_indirme_gb": 7.2, "bos_disk_gb": round(shutil.disk_usage(ROOT).free / 1e9, 1)}


# ------------------------------------------------------------------ indirme
def _log(m: str, yuzde: int | None = None) -> None:
    IS["log"].append(f"{time.strftime('%H:%M:%S')} {m}")
    IS["adim"] = m
    if yuzde is not None:
        IS["yuzde"] = yuzde


def _json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "YSTCoreStudio", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def _hf_dosya(depo: str, ad: str) -> dict:
    """Hugging Face ağaç listesinden dosyanın boyutu ve SHA256'sı (LFS oid)."""
    try:
        folder = ad.rsplit("/", 1)[0] if "/" in ad else ""
        agac = _json(f"{HF}/api/models/{depo}/tree/main" + ("/" + folder if folder else ""))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{depo} listelenemedi (HTTP {e.code})" + (": bu depo giriş istiyor olabilir" if e.code in (401, 403) else "")) from None
    d = next((x for x in agac if x.get("path") == ad), None)
    if not d:
        raise RuntimeError(f"{depo} içinde {ad} bulunamadı")
    return {"boyut": d.get("size") or (d.get("lfs") or {}).get("size") or 0, "sha256": ((d.get("lfs") or {}).get("oid") or "").lower()}


def _indir(url: str, hedef: Path, beklenen_sha: str, boyut: int, etiket: str, taban: int, pay: int) -> None:
    from indirme import download
    _log(f"{etiket}: bağlantı kuruluyor…", taban)
    def ilerle(n, total):
        IS["adim"] = f"{etiket}: {n // 1_000_000} / {total // 1_000_000} MB"
        IS["yuzde"] = min(taban + pay, taban + int(pay * n / total)) if total else taban
    download(url, hedef, boyut, beklenen_sha, ilerle)
    _log(f"{etiket}: doğrulandı", taban + pay)


def _vulkan_var() -> bool:
    """Linux'ta Vulkan yapısı libvulkan ve bir sürücü ister; yoksa düz (CPU) yapı seçilir. Windows'ta Vulkan her ekran kartı sürücüsüyle gelir."""
    if sys.platform == "win32":
        return True
    import ctypes.util
    return bool(ctypes.util.find_library("vulkan"))


def _paket_sec(assets: list, platform_adi: str, makine: str, vulkan: bool):
    """Yayın paketleri bu adlarla gelir: `sd-master-<hash>-bin-win-vulkan-x64.zip`, `...-bin-Darwin-macOS-26.7.2-arm64.zip`, `...-bin-Linux-Ubuntu-26.04-x86_64-vulkan.zip`
    (ayrıca rocm/cuda yapıları ve `cudart-…` çalışma zamanı). İşletim sistemi sözcüğü, mimari takma adları (x64/x86_64/amd64, arm64/aarch64) ve özel çalışma zamanı isteyen yapıların (rocm/cuda) ayıklanması gerekir."""
    arm = makine.lower() in ("arm64", "aarch64")
    mimari = ("arm64", "aarch64") if arm else ("x64", "x86_64", "amd64")
    uygun = []
    for a in assets:
        ad = a["name"].lower()
        if not ad.endswith(".zip") or ad.startswith("cudart"):
            continue
        if platform_adi == "win32":
            ok_ = "-win-" in ad
        elif platform_adi == "darwin":
            ok_ = "darwin" in ad or "macos" in ad
        else:
            ok_ = "linux" in ad
        if ok_ and any(m in ad for m in mimari):
            uygun.append(a)
    sade = [a for a in uygun if not any(x in a["name"].lower() for x in ("rocm", "cuda", "-hip"))]  # AMD/NVIDIA'ya özel çalışma zamanı isteyenler
    vk = [a for a in sade if "vulkan" in a["name"].lower()]
    cpu = [a for a in sade if "vulkan" not in a["name"].lower()]
    cpu_tercih = [a for a in cpu if "avx2" in a["name"].lower() or "cpu" in a["name"].lower()] or cpu
    sira = (vk + cpu_tercih) if vulkan else (cpu_tercih + vk)
    return sira[0] if sira else None


def _sd_ikili() -> None:
    if _exe():
        _log("stable-diffusion.cpp: zaten var", 8)
        return
    rel = _json(f"{GH}/repos/leejet/stable-diffusion.cpp/releases/latest")
    a = _paket_sec(rel.get("assets", []), sys.platform, platform.machine(), _vulkan_var())
    if not a:
        raise RuntimeError("bu sistem için hazır stable-diffusion.cpp paketi bulunamadı")
    z = DIZIN / "bin" / a["name"]
    _indir(a["browser_download_url"], z, "", a.get("size") or 0, "stable-diffusion.cpp (" + a["name"] + ")", 0, 8)
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            hedef = (DIZIN / "bin" / n).resolve()
            if (DIZIN / "bin").resolve() in hedef.parents and not n.endswith("/"):
                hedef.parent.mkdir(parents=True, exist_ok=True)
                hedef.write_bytes(zf.read(n))
    z.unlink(missing_ok=True)
    e = _exe()
    if not e:
        raise RuntimeError("pakette sd-cli bulunamadı")
    if os.name != "nt":
        e.chmod(0o755)


def _kur_is(kalite: str) -> None:
    IS.update({"var": True, "adim": "başlıyor", "yuzde": 0, "log": [], "bitti": False, "hata": ""})
    try:
        _sd_ikili()
        pay = {"model": 45, "llm": 30, "vae": 5}
        taban = 8
        manifest = {}
        for parca in ("model", "llm", "vae"):
            depo, desen = PARCALAR[parca]
            ad = desen.format(kalite=kalite)
            bilgi = _hf_dosya(depo, ad)
            _indir(f"{HF}/{depo}/resolve/main/{ad}", _dosya(parca, kalite), bilgi["sha256"], bilgi["boyut"], ad, taban, pay[parca])
            manifest[_dosya(parca, kalite).name] = bilgi
            taban += pay[parca]
        manifest['_kalite'] = kalite
        (DIZIN / "kurulum.json").write_text(json.dumps(manifest), encoding="utf-8")
        if not durum()["kurulu"]:
            raise RuntimeError("İndirme bitti ancak gerekli dosyalar doğrulanamadı")
        IS["yuzde"] = 100
        _log("kurulum tamam")
    except Exception as e:  # noqa: BLE001
        IS["hata"] = str(e)
        _log("HATA: " + str(e))
    IS.update({"var": False, "bitti": True})


def kur(kalite: str | None = None) -> dict:
    kalite = kalite or oneri()["kalite"]
    if not KALITE_RE.match(kalite):
        raise ValueError("geçersiz kalite")
    with KILIT:
        if IS["var"]:
            return {"ok": False, "mesaj": "kurulum zaten sürüyor"}
        IS.update(var=True, bitti=False, hata="", adim="Bağlantı kuruluyor…", yuzde=0)
        threading.Thread(target=_kur_is, args=(kalite,), daemon=True, name="yerel-gorsel-kur").start()
    return {"ok": True, "kalite": kalite}


def sil() -> int:
    if IS["var"]:
        raise ValueError("İndirme sürerken model silinemez")
    n = sum(f.stat().st_size for f in DIZIN.rglob("*") if f.is_file()) if DIZIN.is_dir() else 0
    shutil.rmtree(DIZIN, ignore_errors=True)
    return n


# ------------------------------------------------------------------ üretim
def uret(istem: str, cikti: str, genislik: int = 1024, yukseklik: int = 576, tohum: int | None = None, adim: int = 8, zaman: int = 1800) -> dict:
    d = durum()
    if not d["kurulu"]:
        raise RuntimeError("yerel görsel üretim kurulu değil (panel → Ayarlar → Servisler ve modeller → Yerel görsel üretim)")
    if not isinstance(istem, str) or not (1 <= len(istem) <= 2000):
        raise ValueError("istem 1-2000 karakter olmalı")
    genislik, yukseklik = max(256, min(int(genislik), 1536)) // 64 * 64, max(256, min(int(yukseklik), 1536)) // 64 * 64
    out = Path(cikti)
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    kalite = d["kalite"]
    komut = [str(_exe()), "--diffusion-model", str(_dosya("model", kalite)), "--vae", str(_dosya("vae")), "--llm", str(_dosya("llm")), "-p", istem, "--cfg-scale", "1.0",
             "--steps", str(max(1, min(int(adim), 30))), "--offload-to-cpu", "--diffusion-fa", "-H", str(yukseklik), "-W", str(genislik), "-o", str(out)]
    if tohum is not None:
        komut += ["-s", str(int(tohum))]
    t0 = time.time()
    r = subprocess.run(komut, cwd=str(DIZIN), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, creationflags=NW, stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not out.is_file():
        raise RuntimeError("üretim başarısız: " + (r.stderr or r.stdout or "")[-400:])
    return {"dosya": str(out), "bayt": out.stat().st_size, "model": "z-image-turbo-" + kalite, "sn": round(time.time() - t0, 1), "yerel": True}


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 0
    try:
        if a[0] == "durum":
            print(json.dumps(durum(), ensure_ascii=False, indent=1))
        elif a[0] == "kur":
            kal = a[a.index("--kalite") + 1] if "--kalite" in a else None
            kur(kal)
            while True:
                time.sleep(2)
                print(f"\r%{IS['yuzde']} {IS['adim']}", end="", flush=True)
                if IS["bitti"]:
                    break
            print()
            return 1 if IS["hata"] else 0
        elif a[0] == "uret" and len(a) > 1 and "-o" in a:
            kw = {"genislik": 1024, "yukseklik": 576, "tohum": None, "adim": 8}
            for k, ad in (("--genislik", "genislik"), ("--yukseklik", "yukseklik"), ("--tohum", "tohum"), ("--adim", "adim")):
                if k in a:
                    kw[ad] = int(a[a.index(k) + 1])
            print(json.dumps(uret(a[1], a[a.index("-o") + 1], **kw), ensure_ascii=False))
        else:
            print(__doc__)
            return 2
    except (ValueError, RuntimeError) as e:
        print("HATA:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
