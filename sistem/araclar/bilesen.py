#!/usr/bin/env python3
"""Bileşen yöneticisi: isteğe bağlı ve kurulumla gelen bileşenleri panelden TEK TIKLA kur / kaldır (Ayarlar → Sistem → Donanım ve bileşenler).

  python sistem/araclar/bilesen.py durum
  python sistem/araclar/bilesen.py kur <bilesen> [seçenek]
  python sistem/araclar/bilesen.py kaldir <bilesen> [seçenek]

Bileşenler (donanim.KATALOG ile aynı kimlikler):
  realesrgan  fotoğraf iyileştirme modeli (TEMEL: kaldırılamaz, kur = onar)
  whisper     konuşma tanıma modelleri (tiny…large-v3); small TEMEL
  ema         yerel Türkçe seslendirme (TEMEL)
  klon        Ses klonlama: Pocket TTS Turkish (pip paketi + model; CC-BY-4.0, atıf gerekir)
  zimage      yerel görsel üretim (yerel_gorsel.py'ye devreder)
  derinlik    Depth Anything V2 Small
  rclone      bulut disk programı
  render      video işleme (TEMEL)
  gpu         NVIDIA hızlandırma: PyTorch'un CUDA sürümü (isteğe bağlı; yoksa işlemci PyTorch'u kullanılır, her şey yine çalışır)
Kurulumlar arka plan iş parçacığında çalışır; ilerleme durum()["is"] içinde. Model dosyaları Hugging Face'ten resmî kitaplıkla iner (sağlama toplamını
kitaplık doğrular); pip paketleri bu stüdyonun sanal ortamına (sistem/ortam/venv) kurulur. Kaldırma yalnızca o bileşenin dosyalarını siler.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("YST_BILESEN_KOK") or Path(__file__).resolve().parents[2])
ORTAM = ROOT / "sistem" / "ortam"
VENV_PY = ORTAM / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NW = 0x08000000 if os.name == "nt" else 0
KILIT = threading.Lock()
IS = {"var": False, "bilesen": "", "secenek": "", "adim": "", "yuzde": 0, "log": [], "bitti": False, "hata": ""}

# whisper: seçenek -> (HF deposu, beklenen GB, temel mi)
WHISPER = {
    "tiny": ("Systran/faster-whisper-tiny", 0.08, False), "base": ("Systran/faster-whisper-base", 0.15, False),
    "small": ("Systran/faster-whisper-small", 0.49, True), "medium": ("Systran/faster-whisper-medium", 1.53, False),
    "large-v3-turbo": ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", 1.62, False), "large-v3": ("Systran/faster-whisper-large-v3", 3.09, False),
}
POCKET_REPO = "wite-tech/pocket-tts-turkish"
EMA_REPO = "canberkkkkkk/ema-lightning"
DEPTH_REPO = "depth-anything/Depth-Anything-V2-Small-hf"
TEMEL = {"realesrgan", "ema", "render"}
SECENEKSIZ = {"realesrgan": "x4plus", "ema": "ema", "klon": "pocket-tr", "derinlik": "small", "rclone": "rclone", "render": "render", "gpu": "cuda"}


def _log(m: str, yuzde: int | None = None) -> None:
    IS["log"].append(f"{time.strftime('%H:%M:%S')} {m}")
    IS["log"][:] = IS["log"][-60:]
    IS["adim"] = m
    if yuzde is not None:
        IS["yuzde"] = yuzde


# ------------------------------------------------------------------ Hugging Face önbelleği
def _hub(ozel_ev: Path | None = None) -> Path:
    if ozel_ev:
        return ozel_ev / "hub"
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    return Path(os.environ.get("HF_HOME") or ORTAM / "modeller/hf") / "hub"


DEPTH_EV = ORTAM / "modeller" / "hf"


def _repo_dizin(repo: str, ev: Path | None = None) -> Path:
    return _hub(ev) / ("models--" + repo.replace("/", "--"))


def _gercek_dosyalar(d: Path) -> dict:
    """{çözülmüş yol: boyut}. Windows'ta HF dosyaları doğrudan snapshots/ altına koyar; Linux/macOS'ta snapshots/ altındaki girdiler sembolik bağdır ve
    yeni huggingface_hub blob'ları repo klasörünün DIŞINDA, hub/blobs altında ortak tutar. Bağlar hedefe çözülür, aynı blob bir kez sayılır."""
    gor: dict = {}
    if not d.is_dir():
        return gor
    for f in d.rglob("*"):
        try:
            if f.is_file():
                gor[f.resolve()] = f.stat().st_size
        except OSError:
            pass
    return gor


def _repo_kurulu(repo: str, ev: Path | None = None) -> bool:
    """Linux/macOS'ta blobs/ dosyaları özet adıyla durur (uzantısız); model dosyasının adı snapshots/ altındaki sembolik bağdadır. Bu yüzden iki yere de bakılır:
    yarım indirme (.incomplete) blobs/'ta, model dosyası (uzantısıyla) snapshots/'ta aranır; stat() sembolik bağı izler."""
    d = _repo_dizin(repo, ev)
    if not d.is_dir():
        return False
    snap = d / "snapshots"
    if "faster-whisper" in repo:
        return snap.is_dir() and any(all((rev / name).is_file() and (rev / name).stat().st_size > (1_000_000 if name == "model.bin" else 0)
                                       for name in ("model.bin", "config.json", "tokenizer.json")) for rev in snap.iterdir() if rev.is_dir())
    return snap.is_dir() and any(f.suffix in (".bin", ".safetensors", ".pt") and f.is_file() and f.stat().st_size > 1_000_000 for f in snap.rglob("*"))


def _repo_boyut(repo: str, ev: Path | None = None) -> int:
    boyut = sum(_gercek_dosyalar(_repo_dizin(repo, ev)).values())
    # indirme sürerken yarım dosyalar (.incomplete) ortak blobs/ altındadır: ilerleme çubuğu için say
    blobs = _hub(ev) / "blobs"
    if blobs.is_dir():
        boyut += sum(f.stat().st_size for f in blobs.glob("*.incomplete") if f.is_file())
    return boyut


# ------------------------------------------------------------------ paket varlığı (venv'de)
_PKG = {"t": 0.0, "v": {}}


def _paketler(adlar=("ema_lightning", "pocket_tts_turkish", "transformers", "faster_whisper")) -> dict:
    if time.time() - _PKG["t"] < 5 and _PKG["v"] and set(adlar).issubset(_PKG["v"]):
        return _PKG["v"]
    kod = "import importlib.util as u,json;print(json.dumps({n: u.find_spec(n) is not None for n in %r}))" % (list(adlar),)
    try:
        r = subprocess.run([str(VENV_PY if VENV_PY.exists() else sys.executable), "-c", kod], capture_output=True, text=True, timeout=30, creationflags=NW)
        v = json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        v = {n: importlib.util.find_spec(n) is not None for n in adlar}
    _PKG.update({"t": time.time(), "v": v})
    return v


CUDA_INDEKS = "https://download.pytorch.org/whl/cu130"
CPU_INDEKS = "https://download.pytorch.org/whl/cpu"


def torch_surum() -> str:
    """Kurulu PyTorch sürümü (ör. '2.14.1+cu130' / '2.14.1+cpu' / '' = yok); paketi İÇE AKTARMADAN dist-info klasör adından okunur (anında)."""
    for kok in sorted((ORTAM / "venv").glob("Lib/site-packages")) + sorted((ORTAM / "venv").glob("lib/python*/site-packages")):
        for d in kok.glob("torch-*.dist-info"):
            return d.name[len("torch-"):-len(".dist-info")]
    return ""


def cuda_torch_var() -> bool:
    return "+cu" in torch_surum()


def _arac():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import bulut_disk
    return bulut_disk


def _gorsel():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import yerel_gorsel
    return yerel_gorsel


# ------------------------------------------------------------------ durum
def durum() -> dict:
    p = _paketler()
    b: dict = {}
    model = ORTAM / "modeller" / "RealESRGAN_x4plus.safetensors"
    b["realesrgan"] = {"temel": True, "secenekler": {"x4plus": {"kurulu": model.is_file(), "temel": True, "boyut_mb": round(model.stat().st_size / 1e6) if model.is_file() else 0}}}
    b["whisper"] = {"temel": False, "secenekler": {k: {"kurulu": _repo_kurulu(r) and p.get("faster_whisper", False), "temel": t, "boyut_mb": round(_repo_boyut(r) / 1e6)} for k, (r, _g, t) in WHISPER.items()}}
    ema_k = p.get("ema_lightning", False) and _repo_kurulu(EMA_REPO)
    b["ema"] = {"temel": True, "secenekler": {"ema": {"kurulu": bool(ema_k), "temel": True, "boyut_mb": round(_repo_boyut(EMA_REPO) / 1e6)}}}
    kl = p.get("pocket_tts_turkish", False) and _repo_kurulu(POCKET_REPO)
    b["klon"] = {"temel": False, "secenekler": {"pocket-tr": {"kurulu": bool(kl), "temel": False, "boyut_mb": round(_repo_boyut(POCKET_REPO) / 1e6)}}}
    try:
        g = _gorsel().durum()
        kq = g.get("kalite")
        b["zimage"] = {"temel": False, "secenekler": {q: {"kurulu": bool(g["kurulu"] and kq == q), "temel": False, "boyut_mb": g["disk_mb"] if kq == q else 0} for q in ("Q3_K", "Q4_0", "Q5_0", "Q6_K")}}
        gis = g.get("is", {})
    except Exception:  # noqa: BLE001
        b["zimage"] = {"temel": False, "secenekler": {}}
        gis = {}
    dk = p.get("transformers", False) and _repo_kurulu(DEPTH_REPO, DEPTH_EV)
    b["derinlik"] = {"temel": False, "secenekler": {"small": {"kurulu": bool(dk), "temel": False, "boyut_mb": round(_repo_boyut(DEPTH_REPO, DEPTH_EV) / 1e6)}}}
    try:
        rc = _arac().rclone()
    except Exception:  # noqa: BLE001
        rc = None
    b["rclone"] = {"temel": False, "secenekler": {"rclone": {"kurulu": bool(rc), "temel": False, "boyut_mb": round(Path(rc).stat().st_size / 1e6) if rc else 0}}}
    ts = torch_surum()
    b["gpu"] = {"temel": False, "secenekler": {"cuda": {"kurulu": "+cu" in ts, "temel": False, "boyut_mb": 2900 if "+cu" in ts else 0}}}
    b["render"] = {"temel": True, "secenekler": {"render": {"kurulu": (ROOT / "node_modules").is_dir(), "temel": True, "boyut_mb": 0}}}
    is_ = dict(IS)
    if not is_["var"] and gis.get("var"):
        is_ = {"var": True, "bilesen": "zimage", "secenek": "", "adim": gis.get("adim", ""), "yuzde": gis.get("yuzde", 0), "log": gis.get("log", [])[-20:], "bitti": False, "hata": ""}
    elif not is_["var"] and not is_["bitti"] and gis.get("hata"):
        is_["hata"] = gis["hata"]
    return {"bilesenler": b, "is": is_}


# ------------------------------------------------------------------ kur
def _pip(*paketler: str, kaldir: bool = False) -> None:
    kom = [str(VENV_PY), "-m", "pip"] + (["uninstall", "-y"] if kaldir else ["install", "-q"]) + list(paketler)
    r = subprocess.run(kom, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, creationflags=NW)
    _PKG["t"] = 0.0
    if r.returncode != 0:
        raise RuntimeError("pip hatası: " + (r.stderr or r.stdout).strip()[-300:])


def _hf_indir(repo: str, beklenen_gb: float, ev: Path | None, baz: int, pay: int) -> None:
    """Hugging Face deposunu resmî kitaplıkla indirir; ilerleme önbellek boyutundan hesaplanır."""
    import tempfile
    import yol
    env = {**os.environ, **yol.kapsama()}
    cache = _hub(ev)
    kod = "import sys;from huggingface_hub import snapshot_download;snapshot_download(sys.argv[1], cache_dir=sys.argv[2])"
    # Drain stderr into a file: pip/HF progress can fill a PIPE and deadlock the downloader.
    with tempfile.TemporaryFile(mode="w+b") as log:
        p = subprocess.Popen([str(VENV_PY), "-c", kod, repo, str(cache)], env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=NW)
        started = time.monotonic()
        while p.poll() is None:
            if time.monotonic() - started > 14400:
                p.kill(); p.wait(); raise RuntimeError("Model indirmesi zaman aşımına uğradı; yeniden deneyin")
            time.sleep(1)
            n = _repo_boyut(repo, ev)
            _log(f"{repo.split('/')[-1]} iniyor: {round(n / 1e6)} MB", baz + int(pay * min(.99, n / max(1, beklenen_gb * 1e9))))
        if p.returncode:
            log.seek(max(0, log.tell() - 3000))
            raise RuntimeError(f"{repo} indirilemedi: " + log.read().decode("utf-8", "replace")[-600:])
    if not _repo_kurulu(repo, ev):
        raise RuntimeError("Model indirildi fakat kullanılabilir ağırlık bulunamadı: " + repo)


def _kur_is(bilesen: str, secenek: str) -> None:
    IS.update({"var": True, "bilesen": bilesen, "secenek": secenek, "yuzde": 0, "log": [], "bitti": False, "hata": ""})
    try:
        if bilesen == "realesrgan":
            _log("Real-ESRGAN modeli indiriliyor", 10)
            r = subprocess.run([str(VENV_PY), str(ROOT / "sistem" / "varlik" / "varlik.py"), "indir", "--tur", "model"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), creationflags=NW, env=dict(os.environ, PYTHONUTF8="1"))
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
        elif bilesen == "whisper":
            repo, gb, _t = WHISPER[secenek]
            if not _paketler().get("faster_whisper"):
                _log("faster-whisper paketi kuruluyor", 5)
                _pip("faster-whisper==1.2.1", "av>=12,<17")
            _hf_indir(repo, gb, None, 10, 88)
        elif bilesen == "ema":
            _log("ema-lightning paketi kuruluyor", 10)
            _pip("ema-lightning==1.1.2")
            _hf_indir(EMA_REPO, 0.04, None, 40, 55)
        elif bilesen == "klon":
            _log("pocket-tts-turkish paketi kuruluyor (birkaç dakika)", 5)
            _pip("pocket-tts-turkish")
            _hf_indir(POCKET_REPO, 0.45, None, 25, 72)
        elif bilesen == "derinlik":
            if not _paketler().get("transformers"):
                _log("transformers paketi kuruluyor", 5)
                _pip("transformers>=4.45")
            _hf_indir(DEPTH_REPO, 0.1, DEPTH_EV, 25, 72)
        elif bilesen == "gpu":
            if not (shutil.which("nvidia-smi")):
                raise RuntimeError("NVIDIA ekran kartı/sürücüsü bulunamadı (nvidia-smi yok): GPU hızlandırma kurulamaz")
            _log("PyTorch CUDA sürümü indiriliyor (~2,7 GB; internet hızına bağlı, birkaç dakika)", 10)
            _pip("--upgrade", "torch", "torchvision", "--index-url", CUDA_INDEKS)
        elif bilesen == "rclone":
            _log("rclone resmî siteden indiriliyor", 20)
            _arac().kur()
        else:
            raise RuntimeError("bu bileşen buradan kurulmaz")
        _PKG["t"] = 0
        check = durum()["bilesenler"].get(bilesen, {}).get("secenekler", {}).get(secenek, {})
        if not check.get("kurulu"):
            raise RuntimeError("Kurulum sonrasında bileşen doğrulanamadı; günlükteki hatayı kontrol edin")
        _log("tamam", 100)
    except Exception as e:  # noqa: BLE001
        IS["hata"] = f"{type(e).__name__}: {e}"
        _log("HATA: " + IS["hata"])
    IS.update({"var": False, "bitti": True})


def kur(bilesen: str, secenek: str = "") -> dict:
    if bilesen == "zimage":
        return _gorsel().kur(secenek or None)
    gecerli = {"realesrgan", "whisper", "ema", "klon", "derinlik", "rclone", "gpu"}
    if bilesen not in gecerli:
        raise ValueError("bilinmeyen ya da kurulamayan bileşen")
    if bilesen == "whisper" and secenek not in WHISPER:
        raise ValueError("bilinmeyen whisper modeli")
    if bilesen != "whisper":
        secenek = SECENEKSIZ.get(bilesen, "")
    with KILIT:
        if IS["var"] or _gorsel().IS["var"]:
            return {"ok": False, "mesaj": "başka bir kurulum sürüyor"}
        IS.update({"var": True})  # yarışı kapat; iş parçacığı sıfırlar
        threading.Thread(target=_kur_is, args=(bilesen, secenek), daemon=True, name="bilesen-kur").start()
    return {"ok": True, "bilesen": bilesen, "secenek": secenek}


# ------------------------------------------------------------------ kaldır
def _boyut_sil(yol: Path) -> int:
    """Klasörü siler; Linux/macOS'ta snapshots/ bağlarının işaret ettiği ortak blob'lar (hub/blobs) başka bir repo kullanmıyorsa onlar da silinir, yoksa disk boşalmaz."""
    gor = _gercek_dosyalar(yol)
    n = sum(gor.values())
    kok = yol.resolve()
    dis = [p for p in gor if kok not in p.parents]  # repo klasörünün dışındaki (ortak blobs/) hedefler
    shutil.rmtree(yol, ignore_errors=True)
    if dis:
        kullanilan: set = set()
        for f in yol.parent.glob("models--*/snapshots/**/*"):
            try:
                if f.is_symlink():
                    kullanilan.add(f.resolve())
            except OSError:
                pass
        for p in dis:
            if p not in kullanilan:
                p.unlink(missing_ok=True)
    return n


def kaldir(bilesen: str, secenek: str = "") -> dict:
    if bilesen in TEMEL:
        raise ValueError("temel bileşen kaldırılamaz (stüdyo bunsuz çalışmaz); bozulduysa Kur ile onarılır")
    with KILIT:
        if IS["var"] or _gorsel().IS["var"]:
            raise ValueError("bir kurulum sürerken kaldırılamaz")
    n = 0
    if bilesen == "whisper":
        if secenek not in WHISPER:
            raise ValueError("bilinmeyen whisper modeli")
        if WHISPER[secenek][2]:
            raise ValueError("small modeli temeldir (dikte ve altyazı bunu kullanır)")
        n = _boyut_sil(_repo_dizin(WHISPER[secenek][0]))
    elif bilesen == "klon":
        _pip("pocket-tts-turkish", "pocket-tts", kaldir=True)
        n = _boyut_sil(_repo_dizin(POCKET_REPO))
    elif bilesen == "derinlik":
        n = _boyut_sil(_repo_dizin(DEPTH_REPO, DEPTH_EV))
    elif bilesen == "gpu":   # işlemci sürümüne dön (CUDA'lı PyTorch'u siler)
        _pip("--force-reinstall", "--no-deps", "torch", "torchvision", "--index-url", CPU_INDEKS)
        n = 2_700_000_000
    elif bilesen == "zimage":
        n = _gorsel().sil()
    elif bilesen == "rclone":
        yol = _arac().ARAC
        n = _boyut_sil(yol)
    else:
        raise ValueError("bilinmeyen bileşen")
    return {"ok": True, "bilesen": bilesen, "secenek": secenek, "bosalan_mb": round(n / 1e6)}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a or a[0] == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
    elif a[0] == "kur" and len(a) >= 2:
        print(kur(a[1], a[2] if len(a) > 2 else ""))
        while True:
            time.sleep(1)
            d = durum()["is"]
            print(f"{d['yuzde']:3}% {d['adim']}", flush=True)
            if not d["var"]:
                print("hata:", d["hata"] or "yok")
                break
    elif a[0] == "kaldir" and len(a) >= 2:
        print(kaldir(a[1], a[2] if len(a) > 2 else ""))
    else:
        print(__doc__)
