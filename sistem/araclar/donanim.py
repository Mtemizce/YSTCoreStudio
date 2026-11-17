#!/usr/bin/env python3
"""Bu bilgisayarın donanımı + stüdyo bileşenlerinin gereksinimleri + "yeterli mi?" değerlendirmesi.

  python sistem/araclar/donanim.py            # makine + her bileşen için karar (JSON)
  python sistem/araclar/donanim.py zimage     # tek bileşen

Her gereksinim değerinin bir KAYNAĞI vardır; panel bunu kullanıcıya gösterir:
  olculdu   = indirilip diskte ölçüldü
  yayimlanan = model deposunun yayımladığı dosya boyutu (Hugging Face API)
  tahmin    = yayımlanmış kesin sayı yok; benzer iş yüklerinden kaba tahmin, ölçülmedi
Karar: yeterli / sinirda / yetersiz. VRAM ve RAM için "asgari" altı = yetersiz (GPU isteğe bağlıysa yalnızca yavaşlar),
"önerilen" altı = sınırda. Yalnızca standart kütüphane.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NW = 0x08000000 if os.name == "nt" else 0


def _calistir(komut: list[str], sure: int = 15) -> str:
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=sure, creationflags=NW, encoding="utf-8", errors="replace")
        return r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _ram() -> tuple[float, float]:
    """(toplam GB, boş GB)"""
    try:
        if os.name == "nt":
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("y", ctypes.c_ulong), ("t", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                            ("tp", ctypes.c_ulonglong), ("bp", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("bv", ctypes.c_ulonglong), ("bx", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.t / 2**30, 1), round(m.b / 2**30, 1)
        if sys.platform == "darwin":
            t = int(_calistir(["sysctl", "-n", "hw.memsize"]).strip() or 0)
            return round(t / 2**30, 1), 0.0
        d = {}
        for s in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = s.partition(":")
            d[k] = int(v.split()[0]) if v.split() else 0
        return round(d.get("MemTotal", 0) / 2**20, 1), round(d.get("MemAvailable", 0) / 2**20, 1)
    except (OSError, ValueError):
        return 0.0, 0.0


_ONBELLEK: dict = {}


def _onbellekli(anahtar: str, fn, sure: float = 600.0):
    """İşlemci adı ve ekran kartı çalışma sırasında değişmez; her çağrıda PowerShell/nvidia-smi başlatmak panelde ~1,5 sn bekletiyordu."""
    t = time.time()
    e = _ONBELLEK.get(anahtar)
    if e and t - e[0] < sure:
        return e[1]
    v = fn()
    _ONBELLEK[anahtar] = (t, v)
    return v


def _cpu() -> tuple[str, int]:
    return _onbellekli("cpu", _cpu_oku)


def _cpu_oku() -> tuple[str, int]:
    ad = platform.processor() or ""
    try:
        if os.name == "nt":
            o = _calistir(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"])
            ad = o.strip() or ad
        elif sys.platform == "darwin":
            ad = _calistir(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or ad
        else:
            m = re.search(r"model name\s*:\s*(.+)", Path("/proc/cpuinfo").read_text())
            ad = m.group(1).strip() if m else ad
    except OSError:
        pass
    return re.sub(r"\s+", " ", ad).strip() or "bilinmiyor", os.cpu_count() or 1


def _gpuler() -> list[dict]:
    return _onbellekli("gpu", _gpuler_oku)


def _gpuler_oku() -> list[dict]:
    """[{ad, vram_gb (0 = bilinmiyor), cuda}]"""
    sonuc: list[dict] = []
    smi = shutil.which("nvidia-smi")
    if smi:
        for s in _calistir([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]).splitlines():
            ad, _, mb = s.rpartition(",")
            if ad.strip() and mb.strip().isdigit():
                sonuc.append({"ad": ad.strip(), "vram_gb": round(int(mb) / 1024, 1), "cuda": True})
    if sonuc:
        return sonuc
    adlar: list[str] = []
    if os.name == "nt":
        adlar = [x.strip() for x in _calistir(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"]).splitlines() if x.strip()]
    elif sys.platform == "darwin":
        adlar = re.findall(r"Chipset Model:\s*(.+)", _calistir(["system_profiler", "SPDisplaysDataType"]))
    else:
        adlar = [re.sub(r"^.*?:\s*", "", x, count=1) for x in _calistir(["sh", "-c", "lspci 2>/dev/null | grep -i -E 'vga|3d|display'"]).splitlines()]
    apple = sys.platform == "darwin" and platform.machine() == "arm64"
    for a in adlar:
        # Apple Silicon: bellek CPU ile ortak; yaklaşık yarısı GPU'ya ayrılabilir. Diğerlerinde VRAM güvenilir okunamadı → 0 (bilinmiyor).
        sonuc.append({"ad": a, "vram_gb": round(_ram()[0] * 0.5, 1) if apple else 0, "cuda": False})
    return sonuc


def sistem() -> dict:
    t, b = _ram()
    cpu, thr = _cpu()
    g = _gpuler()
    en = max(g, key=lambda x: x["vram_gb"]) if g else None
    try:
        du = shutil.disk_usage(ROOT)
        bos = round(du.free / 1e9, 1)
        toplam = round(du.total / 1e9)
    except OSError:
        bos, toplam = 0.0, 0
    return {"os": f"{platform.system()} {platform.release()}", "cpu": cpu, "mantiksal_cekirdek": thr, "ram_gb": t, "ram_bos_gb": b,
            "gpuler": g, "en_iyi_gpu": en, "cuda": any(x["cuda"] for x in g), "vram_gb": en["vram_gb"] if en else 0.0,
            "disk_bos_gb": bos, "disk_toplam_gb": toplam}


# ---------------------------------------------------------------------------------------------- katalog
# disk_gb: bu bileşenin KENDİ indirmesi. paylasilan: başka bileşenlerle ortak olan (PyTorch gibi) → ek yer sayılmaz.
# gpu: "gerekmez" (yalnızca hızlandırır) | "onerilir" (işlemcide çok yavaş) | "gerekir"
# ram_gb / vram_gb: (asgari, önerilen)
def _o(ad, disk, ram, vram, kaynak, **k):
    return {"ad": ad, "disk_gb": disk, "ram_gb": ram, "vram_gb": vram, "kaynak": kaynak, **k}


KATALOG: dict[str, dict] = {
    "realesrgan": {
        "ad": "Real-ESRGAN x4 (fotoğraf iyileştirme)", "kurulum": "otomatik", "varsayilan": True, "gpu": "onerilir",
        "ne": "Bulanık ve düşük çözünürlüklü arşiv fotoğraflarını yapay zekâyla büyütür/toparlar.",
        "secenekler": {"x4plus": _o("RealESRGAN x4plus", 0.07, (4, 8), (2, 4), "olculdu",
                                    not_="Model dosyası 67 MB ölçüldü. VRAM değeri parçalı (tile) işleme için tahmin; ekran kartı yoksa işlemcide foto başına dakikalar sürer.")},
        "paylasilan": "PyTorch başka bileşenlerle ortak; kuruluysa ek yer gerekmez.",
    },
    "whisper": {
        "ad": "faster-whisper (konuşma → yazı, altyazı)", "kurulum": "ilk kullanımda otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Ses kaydını / videoyu Türkçe metne çevirir (dikte, altyazı, kelime zamanlaması).",
        "varsayilan_secenek": "small",
        "secenekler": {
            "tiny": _o("tiny", 0.08, (1, 2), (1, 1), "yayimlanan", not_="Çok hızlı, Türkçede hata çok."),
            "base": _o("base", 0.15, (2, 2), (1, 1), "yayimlanan", not_="Hızlı; Türkçe için sınırlı."),
            "small": _o("small (varsayılan)", 0.49, (2, 4), (1, 2), "yayimlanan", not_="Türkçe için iyi denge. Ölçülen önbellek: 464 MB."),
            "medium": _o("medium", 1.53, (4, 8), (3, 4), "yayimlanan", not_="Daha doğru, işlemcide yavaş."),
            "large-v3-turbo": _o("large-v3-turbo", 1.62, (6, 8), (3, 5), "yayimlanan", not_="En iyi hız/doğruluk dengesi; ekran kartı önerilir."),
            "large-v3": _o("large-v3", 3.09, (8, 12), (5, 8), "yayimlanan", not_="En doğru, en ağır."),
        },
        "paylasilan": "Dosya boyutları yayımlanan değerdir; RAM/VRAM faster-whisper'ın yayımladığı ölçümlerden ve benzer yüklerden TAHMİN edilmiştir.",
    },
    "ema": {
        "ad": "EMA Lightning (yerel Türkçe seslendirme)", "kurulum": "otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Metni Türkçe seslendirir; ücretsiz ve hesapsız, her şey bu bilgisayarda.",
        "secenekler": {"ema": _o("EMA Lightning", 0.45, (2, 4), (0, 0), "olculdu",
                                 not_="Disk: ema-lightning (33 MB) + Türkçe ses modeli (420 MB) ölçüldü. RAM değeri tahmindir.")},
        "paylasilan": "PyTorch ortak.",
    },
    "klon": {
        "ad": "Ses klonlama (Pocket TTS Turkish)", "kurulum": "otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Türkçe seslendirmeyi, 3-10 saniyelik temiz bir örnek sesin tınısıyla (ses klonlama) üretir; ayrıca 6 hazır ses ve duygu etiketi (mutlu, üzgün, kızgın, şaşkın, sakin) sunar. İşlemcide çalışır.",
        "secenekler": {"pocket-tr": _o("Pocket TTS Turkish", 0.5, (2, 4), (0, 0), "olculdu",
                                       not_="İşlemcide gerçek zamandan hızlı (üretim süresi ses süresinin ~%30-40'ı), model ~0,45 GB + paketler. Bellek tepesi ~1,7 GB ölçüldü (PyTorch dahil). "
                                           "Lisans CC-BY-4.0: atıf gerekir (README ve Sistem → Lisanslar'da; bu motorla üretilen her çıktının yanına ATIF.txt yazılır). "
                                           "Klonlama panelde 'Sesimi klonla' seçilince açılır; ses bu bilgisayarda işlenir, hiçbir yere gönderilmez.")},
        "paylasilan": "PyTorch ortak.",
    },
    "gpu": {
        "ad": "GPU hızlandırma (NVIDIA CUDA için PyTorch)", "kurulum": "isteğe bağlı", "varsayilan": False, "gpu": "gerekir",
        "ne": "Foto iyileştirme, derinlik ve ses modellerini NVIDIA ekran kartında çalıştırır (işlemciye göre kat kat hızlı). Kurulmazsa her şey işlemcide yine çalışır, yalnızca yavaş olur.",
        "secenekler": {"cuda": _o("PyTorch CUDA", 2.9, (4, 8), (2, 4), "olculdu",
                                  not_="İşlemci sürümünün yerini alır; net ek yer ~2,7 GB (kurulu CUDA'lı PyTorch ölçüldü: 2,9 GB). Kurulurken ses/foto işi çalıştırma. NVIDIA sürücüsü gerekir.")},
        "paylasilan": "İşlemci PyTorch'un yerine geçer.",
    },
    "zimage": {
        "ad": "Z-Image-Turbo (yerel görsel üretim)", "kurulum": "isteğe bağlı", "varsayilan": False, "gpu": "onerilir", "bellek_tasima": True,
        "ne": "Metinden görsel üretir (stable-diffusion.cpp, Vulkan). Veri dışarı çıkmaz.",
        "secenekler": {
            "Q3_K": _o("Q3_K (en küçük)", 6.0, (8, 16), (4, 6), "yayimlanan", not_="Model 3.1 GB + metin modeli ~2.5 GB + VAE ~0.3 GB. 4 GB VRAM'de bellek taşırma (offload) ile çalışır, yavaştır."),
            "Q4_0": _o("Q4_0", 6.5, (8, 16), (4, 8), "yayimlanan", not_="Model 3.7 GB + metin modeli ~2.5 GB + VAE ~0.3 GB."),
            "Q5_0": _o("Q5_0", 7.4, (12, 16), (6, 10), "yayimlanan", not_="Model 4.5 GB + metin modeli ~2.5 GB + VAE ~0.3 GB."),
            "Q6_K": _o("Q6_K (en kaliteli)", 8.1, (16, 24), (8, 12), "yayimlanan", not_="Model 5.3 GB + metin modeli ~2.5 GB + VAE ~0.3 GB."),
        },
        "paylasilan": "Dosya boyutları yayımlanan değerdir; RAM/VRAM eşikleri tahmindir.",
    },
    "derinlik": {
        "ad": "Depth Anything V2 Small (mekân gezisi derinlik haritası)", "kurulum": "otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Tek bir fotoğraftan derinlik haritası çıkarır; mekân gezisi (parallax) videosunda yakın/uzak ayrımı için kullanılır.",
        "secenekler": {"small": _o("Depth Anything V2 Small", 0.1, (2, 4), (0, 1), "yayimlanan",
                                   not_="Model dosyası 99 MB (yayımlanan). transformers paketi ek ~0.1 GB (ölçüldü). RAM/VRAM tahmin; küçük bir ağ olduğundan işlemcide de saniyeler sürer, ölçülmedi.")},
        "paylasilan": "PyTorch ortak.",
    },
    "rclone": {
        "ad": "rclone (Google Drive / OneDrive / Dropbox arşivi)", "kurulum": "otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Bulut diskteki arşivi listeler; yalnızca seçtiğin dosyaları indirir.",
        "secenekler": {"rclone": _o("rclone", 0.06, (0.5, 1), (0, 0), "tahmin", not_="Tek program (~60 MB). Önbellek ayrıca en çok 5 GB'a kadar büyür (en eski dosyalar silinir).")},
        "paylasilan": "",
    },
    "render": {
        "ad": "Video işleme (ffmpeg + Remotion + Chromium)", "kurulum": "otomatik", "varsayilan": True, "gpu": "gerekmez",
        "ne": "Kurgu önizleme ve son render; her şey işlemcide çalışır.",
        "secenekler": {"render": _o("Remotion + Chromium", 0.8, (4, 8), (0, 0), "tahmin", not_="Disk ve RAM tahmin. Uzun/4K videolarda RAM ve işlemci süresi artar.")},
        "paylasilan": "",
    },
}


# ---------------------------------------------------------------------------------------------- ilk kurulum bütçesi
# gb = diskte kaplayacağı yer (indirme genelde biraz daha küçüktür; PyTorch tekerlekleri sıkıştırılmıştır). "olculdu" = kurulu halinin ölçülen boyutu.
def kurulum_plani(cuda: bool) -> list[dict]:
    return [
        {"ad": "PyTorch (işlemci sürümü, yapay zekâ motoru)", "gb": 0.5, "kaynak": "tahmin", "zaman": "arka planda"},
        {"ad": "Python paketleri (çekirdek: faster-whisper, scipy, PDF…)", "gb": 0.45, "kaynak": "olculdu", "zaman": "kurulumda"},
        {"ad": "Yapay zekâ paketleri (EMA, Real-ESRGAN çalıştırıcı, ses klonlama, derinlik)", "gb": 0.3, "kaynak": "olculdu", "zaman": "arka planda"},
        {"ad": "Remotion + HyperFrames (npm)", "gb": 0.7, "kaynak": "olculdu", "zaman": "kurulumda"},
        {"ad": "Kurgu editörü", "gb": 0.1, "kaynak": "olculdu", "zaman": "kurulumda"},
        {"ad": "Real-ESRGAN modeli, DWG aracı, referans belgeleri", "gb": 0.1, "kaynak": "olculdu", "zaman": "arka planda"},
        {"ad": "Depth Anything V2 Small (derinlik modeli)", "gb": 0.1, "kaynak": "yayimlanan", "zaman": "arka planda"},
        {"ad": "Konuşma tanıma modeli (faster-whisper small)", "gb": 0.5, "kaynak": "yayimlanan", "zaman": "arka planda"},
        {"ad": "ffmpeg", "gb": 0.1, "kaynak": "tahmin", "zaman": "kurulumda"},
        {"ad": "rclone (bulut disk)", "gb": 0.06, "kaynak": "tahmin", "zaman": "arka planda"},
        {"ad": "Ses klonlama (Pocket TTS Turkish)", "gb": 0.5, "kaynak": "olculdu", "zaman": "arka planda"},
        {"ad": "Türkçe seslendirme modeli (EMA Lightning)", "gb": 0.45, "kaynak": "olculdu", "zaman": "arka planda"},
    ]


def ilk_kurulum(s: dict | None = None) -> dict:
    s = s or sistem()
    p = kurulum_plani(bool(s["cuda"]))
    kur = round(sum(x["gb"] for x in p if x["zaman"] == "kurulumda"), 1)
    arka = round(sum(x["gb"] for x in p if x["zaman"] == "arka planda"), 1)   # panel açıldıktan sonra, kullanıcıyı bekletmeden iner
    sonra = round(sum(x["gb"] for x in p if x["zaman"] not in ("kurulumda", "arka planda")), 1)   # ilk kullanımda
    gerek = round((kur + arka + sonra) * 1.3 + 2, 1)  # geçici dosyalar + proje çıktıları için pay
    return {"parcalar": p, "kurulumda_gb": kur, "arka_plan_gb": arka, "ilk_kullanimda_gb": sonra, "toplam_gb": round(kur + arka + sonra, 1), "onerilen_bos_disk_gb": gerek,
            "bos_disk_gb": s["disk_bos_gb"], "disk_yeterli": s["disk_bos_gb"] >= kur + arka + sonra,
            "not": "Boyutlar diskte kaplanan yerdir; indirme genelde biraz daha küçüktür. Z-Image gibi isteğe bağlı bileşenler bu toplamda YOKTUR."}


def _seviye(var: float, gerek: tuple[float, float]) -> str:
    """ok | sinir | yok"""
    if var >= gerek[1]:
        return "ok"
    return "sinir" if var >= gerek[0] else "yok"


def degerlendir_secenek(bilesen: dict, sec: dict, s: dict) -> dict:
    sat: list[dict] = []
    gpu_modu = bilesen.get("gpu", "gerekmez")
    # disk: 1.3 kat boşluk önerilir (geçici dosyalar)
    d = sec["disk_gb"]
    sev = "ok" if s["disk_bos_gb"] >= d * 1.3 + 1 else ("sinir" if s["disk_bos_gb"] >= d else "yok")
    sat.append({"etiket": "Disk", "gerek": f"{d:g} GB", "var": f"{s['disk_bos_gb']:g} GB boş", "durum": sev})
    a, o = sec["ram_gb"]
    o_ram = o
    sat.append({"etiket": "RAM", "gerek": f"asgari {a:g} · önerilen {o:g} GB", "var": f"{s['ram_gb']:g} GB", "durum": _seviye(s["ram_gb"], (a, o))})
    va, vo = sec["vram_gb"]
    if vo > 0 or va > 0:
        if s["vram_gb"] > 0:
            sev = _seviye(s["vram_gb"], (va, vo))
            if gpu_modu == "gerekmez" and sev == "yok":
                sev = "sinir"  # ekran kartı yoksa/ küçükse yalnızca işlemciye düşer
            var = f"{s['vram_gb']:g} GB ({(s['en_iyi_gpu'] or {}).get('ad', '')})"
            if bilesen.get("bellek_tasima") and sev != "ok" and s["ram_gb"] >= o_ram:
                # Ağırlıklar yalnızca hesap sırasında VRAM'e alınır, gerisi RAM'de durur (stable-diffusion.cpp --offload-to-cpu):
                # VRAM asgarinin üstündeyse ÇALIŞIR (biraz yavaş) → uygun; altındaysa yine çalışır ama çok yavaş → sınırda.
                if s["vram_gb"] >= va:
                    sev = "ok"
                    var += ": önerilenin altında, ağırlıklar RAM'e taşınır (biraz yavaşlar)"
                else:
                    sev = "sinir"
                    var += ": asgarinin altında, RAM'e taşınarak çalışır ama çok yavaş"
        else:
            sev = "sinir" if gpu_modu != "gerekir" else "yok"
            var = "ekran kartı belleği algılanamadı" if s["gpuler"] else "ekran kartı yok"
        sat.append({"etiket": "Ekran kartı belleği (VRAM)", "gerek": f"{'isteğe bağlı: ' if gpu_modu == 'gerekmez' else ''}asgari {va:g} · önerilen {vo:g} GB", "var": var, "durum": sev})
    else:
        sat.append({"etiket": "Ekran kartı", "gerek": "gerekmez", "var": "—", "durum": "ok"})
    sirali = {"ok": 0, "sinir": 1, "yok": 2}
    en_kotu = max(sat, key=lambda x: sirali[x["durum"]])["durum"]
    return {"satirlar": sat, "durum": {"ok": "yeterli", "sinir": "sınırda", "yok": "yetersiz"}[en_kotu]}


def degerlendir(bilesen_id: str, s: dict | None = None) -> dict:
    s = s or sistem()
    b = KATALOG[bilesen_id]
    secenekler = {}
    for k, sec in b["secenekler"].items():
        e = degerlendir_secenek(b, sec, s)
        secenekler[k] = {**{x: sec[x] for x in ("ad", "disk_gb", "ram_gb", "vram_gb", "kaynak")}, "not": sec.get("not_", ""), **e}
    sirali = {"yeterli": 0, "sınırda": 1, "yetersiz": 2}
    # bileşenin özeti: varsayılan seçenek (varsa) ya da en hafif seçenek
    ana = b.get("varsayilan_secenek") or min(secenekler, key=lambda k: (sirali[secenekler[k]["durum"]], secenekler[k]["disk_gb"]))
    return {"id": bilesen_id, "ad": b["ad"], "ne": b["ne"], "kurulum": b["kurulum"], "varsayilan": b["varsayilan"], "gpu": b["gpu"],
            "paylasilan": b.get("paylasilan", ""), "ana_secenek": ana, "durum": secenekler[ana]["durum"], "secenekler": secenekler}


def hepsi() -> dict:
    s = sistem()
    return {"sistem": s, "bilesenler": {k: degerlendir(k, s) for k in KATALOG}, "ilk_kurulum": ilk_kurulum(s)}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    h = hepsi()
    if len(sys.argv) > 1 and sys.argv[1] in KATALOG:
        h = degerlendir(sys.argv[1], h["sistem"])
    print(json.dumps(h, ensure_ascii=False, indent=1))
