"""PATH hazırlığı: kurulumun kendi getirdiği araçlar (ffmpeg/ffprobe: Kurgu'nun indiricisi; rclone) sistemde yoksa da bulunsun.

Sorun: sistemde ffmpeg olmayan Linux/macOS makinede kurulum ffmpeg'i `sistem/ortam/yerel/veri/ffmpeg/` altına indiriyordu, ama panel ve araçlar yalnızca PATH'e baktığı için
"ffmpeg bulunamadı" diyordu (sağlık denetimi HATA, ses temizleme/klon/altyazı çalışmıyordu). Sistemdeki ffmpeg her zaman önceliklidir; kurulumunki yedek olarak PATH'in SONUNA eklenir.

  import yol; yol.hazirla()            # bu sürecin PATH'ini düzeltir; alt süreçler devralır
  yol.hazirla(env)                     # verilen ortam sözlüğünü düzeltir
  yol.klasorler()                      # eklenecek (var olan) klasörler
  yol.kapsama()                        # TEK KLASÖR kuralı: indirilen her şeyin (modeller, önbellekler) stüdyo klasörü içine gitmesini sağlayan ortam değişkenleri
  yol.hf_tasi()                        # eski (klasör dışı) Hugging Face önbelleğindeki stüdyo modellerini klasör içine KOPYALAR (indirmeyi tekrarlamamak için)

Kural: stüdyonun indirdiği/ürettiği her şey bu klasörde kalır; bilgisayarın başka yerine (AppData, ~/.cache, Belgeler...) yazılmaz. Silmek için klasörü silmek yeter.
İstisnalar (kurulum öncesi ya da stüdyodan bağımsız şeyler) docs/KULLANIM.md "Kaldırma" bölümünde ve `python sistem/kurulum/kaldir.py` çıktısında listelenir.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORTAM = ROOT / "sistem" / "ortam"


def kapsama() -> dict:
    """Süreçlerin her indirmeyi/önbelleği stüdyo klasörüne yazması için ortam değişkenleri (hepsi sistem/ortam altında)."""
    yerel = ORTAM / "yerel"
    onb = yerel / "onbellek"
    e = {
        "KURGU_CONFIG": str(ORTAM / "kurgu-ayar"), "KURGU_MODELS": str(ORTAM / "modeller"), "KURGU_DATA": str(yerel / "veri"),
        "HF_HUB_CACHE": str(ORTAM / "modeller" / "hf" / "hub"),
        "HF_HOME": str(ORTAM / "modeller" / "hf"),              # Hugging Face: Pocket TTS, Whisper, EMA, derinlik, Z-Image...
        "TORCH_HOME": str(ORTAM / "modeller" / "torch"),
        "XDG_CACHE_HOME": str(onb),                             # ~/.cache kullanan Python araçları (EMA parti boyutu, ...)
        "npm_config_cache": str(onb / "npm"),
        "PIP_NO_CACHE_DIR": "1",                                # pip önbelleği klasörü şişirmesin (tekerlekler zaten venv'e kurulur)
        "HF_HUB_DISABLE_TELEMETRY": "1", "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1", "PYTHONUTF8": "1",
    }
    # HyperFrames ev dizinini (~/.cache/hyperframes: Chrome, yazı tipleri) sabit kodlu kullanır: yalnızca onun sürecinde ev dizinini klasöre çeviren ön yükleyici
    cjs = ROOT / "sistem" / "kurulum" / "ev_yonlendir.cjs"
    if cjs.is_file():
        mevcut = os.environ.get("NODE_OPTIONS", "")
        ek = '--require "%s"' % cjs.as_posix()
        e["NODE_OPTIONS"] = mevcut if ek in mevcut else (mevcut + " " + ek).strip()
        e["YST_NODE_EV"] = str(yerel / "ev")
    # HyperFrames kendi Chrome'unu ~/.cache/hyperframes altına indirir (sabit kodlu): onun yerine klasördeki Remotion'un chrome-headless-shell'i kullanılır
    for kok in sorted((ROOT / "node_modules" / ".remotion" / "chrome-headless-shell").glob("*/*")):
        for ad in ("chrome-headless-shell.exe", "chrome-headless-shell"):
            if (kok / ad).is_file():
                e["HYPERFRAMES_BROWSER_PATH"] = str(kok / ad)
                break
    return e


_HF_STUDYO = ("models--wite-tech--pocket-tts-turkish", "models--Systran--faster-whisper-small", "models--canberkkkkkk--ema-lightning")


def hf_tasi() -> list[str]:
    """Eski ortak Hugging Face önbelleğinde (~/.cache/huggingface/hub) duran STÜDYO modellerini klasörün içine kopyalar (yoksa). Kaynağa dokunmaz.
    Döner: kopyalanan model klasörlerinin adları."""
    import shutil
    eski = Path.home() / ".cache" / "huggingface" / "hub"   # kapsama() öncesi varsayılan; HF_HOME artık klasörün içini gösterir
    yeni = ORTAM / "modeller" / "hf" / "hub"
    out = []
    for ad in _HF_STUDYO:
        if (eski / ad).is_dir() and not (yeni / ad).exists():
            yeni.mkdir(parents=True, exist_ok=True)
            shutil.copytree(eski / ad, yeni / ad, symlinks=True)
            out.append(ad)
    return out


def klasorler() -> list[str]:
    veri = ORTAM / "yerel" / "veri"
    adaylar = [veri / "ffmpeg", veri / "Kurgu" / "ffmpeg", veri / "Kurgu", ORTAM / "arac"]
    return [str(d) for d in adaylar if d.is_dir()]


def hazirla(env: dict | None = None) -> dict:
    e = os.environ if env is None else env
    e.update(kapsama())
    mevcut = (e.get("PATH") or "").split(os.pathsep)
    ek = [d for d in klasorler() if d not in mevcut]
    if ek:
        e["PATH"] = os.pathsep.join([p for p in mevcut if p] + ek)
    return e
