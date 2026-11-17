#!/usr/bin/env python3
"""Ses klonlama örneğinin kalite ölçütleri ve klon denemesi. Hiçbir ölçüt klonlamayı ENGELLEMEZ: kullanıcıya bilgi verir.

  python klon_olc.py sinyal <ses> [--temiz]        süre, gürültü oranı (SNR), patlama (kırpılma), seviye, konuşma oranı; JSON
  python klon_olc.py dene <ornek.wav> <cikti.wav>  örnek sesle bir cümle üretir, Whisper ile geri çözer, anlaşılırlık %'sini yazar; JSON

Ölçütler iyi / orta / zayıf diye derecelenir ve yanında ne yapılacağı yazılır. "Zayıf" bile olsa klonlama denenebilir.
Anlaşılırlık sesin BOZUK olup olmadığını gösterir (sözcükler çözülebiliyor mu); benzerliği ölçmez: benzerliğe kulakla karar verilir.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SISTEM = Path(__file__).resolve().parents[1]
DENEME_CUMLESI = "Merhaba, bugün hava çok güzel. Yeni projemizin tanıtım videosuna şimdi başlıyoruz."
NW = 0x08000000 if sys.platform == "win32" else 0
KARE_SN = 0.03  # analiz penceresi


def _ff() -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ses_temizle
    return ses_temizle._ff()


def _oku(yol: str):
    import numpy as np
    r = subprocess.run([_ff(), "-v", "error", "-i", str(yol), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True, creationflags=NW)
    if r.returncode != 0 or len(r.stdout) < 3200:
        raise RuntimeError("ses okunamadı ya da çok kısa")
    return np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _derece(deger: float, iyi: float, orta: float, ters: bool = False) -> str:
    """Eşikler: deger>=iyi → iyi, >=orta → orta, aksi zayıf. ters=True ise küçük olan iyidir."""
    if ters:
        return "iyi" if deger <= iyi else "orta" if deger <= orta else "zayif"
    return "iyi" if deger >= iyi else "orta" if deger >= orta else "zayif"


def sinyal(yol: str, temizlenmis: bool = False) -> dict:
    """Kayıt sinyalinden ölçütler. temizlenmis=True: dosya zaten gürültü azaltma/kırpma görmüş (gürültü ve seviye tahmini daha az güvenilir)."""
    import numpy as np
    x = _oku(yol)
    n = int(16000 * KARE_SN)
    kare = len(x) // n
    if kare < 10:
        raise RuntimeError("ses çok kısa")
    k = x[: kare * n].reshape(kare, n)
    rms = np.sqrt((k ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    gurultu_db = max(float(np.percentile(db, 10)), -80.0)  # sayısal sessizlik (-180 dB) oranı şişirmesin
    konusma_db = float(np.percentile(db, 90))
    esik = gurultu_db + (konusma_db - gurultu_db) * 0.5
    konusan = db > esik
    konusma_sn = float(konusan.sum() * KARE_SN)
    toplam_sn = float(len(x) / 16000)
    oran = float(konusan.mean())
    snr = konusma_db - gurultu_db
    kirpilma = float((np.abs(x) >= 0.99).mean() * 100)
    tepe_db = float(20 * np.log10(np.abs(x).max() + 1e-9))

    olcut = []

    def ekle(kod, ad, deger_metin, seviye, ipucu):
        olcut.append({"kod": kod, "ad": ad, "deger": deger_metin, "seviye": seviye, "ipucu": ipucu})

    s = _derece(konusma_sn, 5, 3)
    ekle("sure", "Konuşma süresi", f"{konusma_sn:.1f} sn", s,
         {"iyi": "Yeterli uzunlukta.", "orta": "Biraz kısa; 5-10 sn konuşursan klon daha tutarlı olur.", "zayif": "Çok kısa; en az 5-10 saniye net konuş."}[s])
    if temizlenmis:
        ekle("gurultu", "Arka plan gürültüsü", "ölçülemedi", "orta", "Bu kayıt kaydedilirken temizlenmişti; gürültü oranı tahminidir.")
    else:
        s = _derece(snr, 25, 15)
        ekle("gurultu", "Arka plan gürültüsü", f"ses/gürültü ≈ {snr:.0f} dB", s,
             {"iyi": "Ortam sessiz.", "orta": "Biraz arka plan sesi var; sessiz bir odada klon daha temiz çıkar.", "zayif": "Arka plan sesi yüksek; sessiz bir yerde, mikrofona yakın kaydet."}[s])
    s = _derece(kirpilma, 0.1, 1.0, ters=True)
    ekle("patlama", "Patlama (kırpılma)", f"%{kirpilma:.2f}", s,
         {"iyi": "Ses patlamıyor.", "orta": "Hafif patlama var; mikrofondan biraz uzaklaş.", "zayif": "Ses patlıyor (bozulmuş); mikrofondan uzaklaş ya da kayıt seviyesini düşür."}[s])
    s = _derece(konusma_db, -30, -40)
    ekle("seviye", "Ses seviyesi", f"{konusma_db:.0f} dB", s,
         {"iyi": "Seviye uygun.", "orta": "Biraz kısık; mikrofona yaklaş.", "zayif": "Çok kısık; mikrofona yaklaş ya da kayıt seviyesini yükselt."}[s])
    if temizlenmis:
        ekle("oran", "Konuşma oranı", "ölçülemedi", "orta", "Boşluklar kayıt sırasında kırpılmıştı.")
    else:
        s = _derece(oran, 0.6, 0.35)
        ekle("oran", "Konuşma oranı", f"%{oran * 100:.0f}", s,
             {"iyi": "Aralıksız konuşulmuş.", "orta": "Araya biraz sessizlik girmiş.", "zayif": "Çoğu sessizlik; kesintisiz konuş."}[s])
    zayif = sum(1 for o in olcut if o["seviye"] == "zayif")
    orta = sum(1 for o in olcut if o["seviye"] == "orta")
    genel = "zayif" if zayif >= 2 else "orta" if (zayif or orta >= 2) else "iyi"
    metin = {"iyi": "Örnek kalitesi iyi: klon büyük olasılıkla temiz çıkar.",
             "orta": "Örnek kalitesi orta: klon çalışır, ama aşağıdaki ipuçlarıyla daha iyi olur.",
             "zayif": "Örnek kalitesi zayıf: yine de kullanabilirsin, ama sonuç bozuk çıkabilir; ipuçlarına göre yeniden kaydetmen önerilir."}[genel]
    return {"genel": genel, "ozet": metin, "olcutler": olcut,
            "ham": {"sure": round(toplam_sn, 2), "konusma_sn": round(konusma_sn, 2), "snr_db": round(snr, 1), "kirpilma_yuzde": round(kirpilma, 3),
                    "seviye_db": round(konusma_db, 1), "tepe_db": round(tepe_db, 1), "oran": round(oran, 3)}}


def _kelimeler(metin: str) -> list[str]:
    t = metin.replace("İ", "i").replace("I", "ı").lower()
    return re.findall(r"[a-zçğıöşü0-9]+", t)


def _uret(ornek: str, cikti: str) -> None:
    """Klon motoruyla deneme cümlesini üretir (ayrı süreçte çalışır: model belleği iş bitince boşalır)."""
    sys.path.insert(0, str(SISTEM))
    from tts.pocket import MOTOR
    with tempfile.TemporaryDirectory() as td:
        r = MOTOR.uret([("deneme", {"metin": DENEME_CUMLESI, "klon": ornek, "seed": 7})], {}, td, 24000)
        Path(cikti).parent.mkdir(parents=True, exist_ok=True)
        Path(cikti).write_bytes(Path(r["deneme"]).read_bytes())


def dene(ornek: str, cikti: str) -> dict:
    """Örnek sesle cümle üret → Whisper ile geri çöz → sözcük eşleşmesi. Süreçler ayrı: ağır modeller birlikte bellekte durmaz."""
    py = sys.executable
    r = subprocess.run([py, str(Path(__file__).resolve()), "_uret", ornek, cikti], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420, creationflags=NW)
    if r.returncode != 0 or not Path(cikti).is_file():
        raise RuntimeError("klon üretilemedi: " + ((r.stderr or r.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1][:200])
    with tempfile.TemporaryDirectory() as td:
        j = Path(td) / "yazi.json"
        c = subprocess.run([py, str(Path(__file__).resolve().parent / "yazi_cikar.py"), cikti, "-o", str(j), "--dil", "tr", "--model", "small"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=420, creationflags=NW)
        if c.returncode != 0 or not j.is_file():
            raise RuntimeError("üretilen ses geri çözülemedi: " + ((c.stderr or c.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1][:200])
        cozum = " ".join(x["metin"] for x in json.loads(j.read_text(encoding="utf-8"))["cumleler"]).strip()
    beklenen, bulunan = _kelimeler(DENEME_CUMLESI), _kelimeler(cozum)
    oran = difflib.SequenceMatcher(None, beklenen, bulunan).ratio() if bulunan else 0.0
    yuzde = round(oran * 100)
    seviye = "iyi" if yuzde >= 85 else "orta" if yuzde >= 60 else "zayif"
    mesaj = {"iyi": "Klon sesi net: sözcükler doğru çözülüyor.",
             "orta": "Klon çoğunlukla anlaşılıyor ama bazı sözcükler bozuk; örneği daha temiz/uzun kaydetmek yardımcı olur.",
             "zayif": "Klon sesinde bozulma var: sözcükler çözülemiyor. Örneği sessiz ortamda, 5-10 sn net konuşarak yeniden kaydetmen önerilir (yine de kullanabilirsin)."}[seviye]
    return {"anlasilirlik": yuzde, "seviye": seviye, "mesaj": mesaj, "cumle": DENEME_CUMLESI, "cozum": cozum,
            "not": "Bu sayı sesin bozuk olup olmadığını gösterir; sesin sana benzeyip benzemediğini kulağınla değerlendir."}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    try:
        if len(a) >= 2 and a[0] == "sinyal":
            print(json.dumps(sinyal(a[1], "--temiz" in a), ensure_ascii=False))
        elif len(a) >= 3 and a[0] == "dene":
            print(json.dumps(dene(a[1], a[2]), ensure_ascii=False))
        elif len(a) >= 3 and a[0] == "_uret":
            _uret(a[1], a[2])
        else:
            print(__doc__)
            return 2
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print("HATA:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
