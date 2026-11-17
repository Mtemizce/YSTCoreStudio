"""Klon örneği ölçütleri (sistem/araclar/klon_olc.py): sentetik seslerle, model ve panel gerekmeden.
Konuşma yerine kısa ton patlamaları kullanılır; ölçütlerin yönü ve eşikleri doğrulanır."""
import importlib.util
import json
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


sp = importlib.util.spec_from_file_location("klon_olc", R / "sistem/araclar/klon_olc.py")
K = importlib.util.module_from_spec(sp)
sp.loader.exec_module(K)
TMP = Path(tempfile.mkdtemp(prefix="yst-klon-"))
SR = 16000
rng = np.random.default_rng(1)


def yaz(ad, x):
    p = TMP / ad
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return str(p)


def konusma(sn, seviye=0.3, oran=0.8, gurultu=0.0005):
    """Hece benzeri ton patlamaları + taban gürültüsü."""
    n = int(SR * sn)
    t = np.arange(n) / SR
    zarf = (np.sin(2 * np.pi * 3 * t) > (1 - 2 * oran)).astype(np.float32)  # ~3 Hz açık/kapalı
    x = seviye * zarf * np.sin(2 * np.pi * 180 * t) + gurultu * rng.standard_normal(n)
    return x.astype(np.float32)


def seviye(o, kod):
    return next(x["seviye"] for x in o["olcutler"] if x["kod"] == kod)


iyi = K.sinyal(yaz("iyi.wav", konusma(8)))
ok(iyi["genel"] == "iyi" and all(x["seviye"] == "iyi" for x in iyi["olcutler"]), f"temiz, yeterli uzunlukta örnek iyi: {[(x['kod'], x['seviye']) for x in iyi['olcutler']]}")
ok(len(iyi["olcutler"]) == 5 and all(x["ipucu"] for x in iyi["olcutler"]), "beş ölçüt, her birinin açıklaması var")

kisa = K.sinyal(yaz("kisa.wav", konusma(1.2)))
ok(seviye(kisa, "sure") == "zayif", "1,2 sn konuşma süre bakımından zayıf")

gur = K.sinyal(yaz("gur.wav", konusma(8, gurultu=0.05)))
ok(seviye(gur, "gurultu") == "zayif" and seviye(iyi, "gurultu") == "iyi", "gürültülü kayıtta gürültü ölçütü zayıf, temizde iyi")

pat = K.sinyal(yaz("pat.wav", konusma(8, seviye=3.0)))
ok(seviye(pat, "patlama") == "zayif", "kırpılan (patlayan) kayıt zayıf")

kisik = K.sinyal(yaz("kisik.wav", konusma(8, seviye=0.003, gurultu=0.00001)))
ok(seviye(kisik, "seviye") == "zayif", "çok kısık kayıt seviye bakımından zayıf")

seyrek = K.sinyal(yaz("seyrek.wav", np.concatenate([konusma(2), np.zeros(SR * 10, dtype=np.float32)])))
ok(seviye(seyrek, "oran") == "zayif", "çoğu sessizlik olan kayıtta konuşma oranı zayıf")
ok(seyrek["ham"]["snr_db"] < 100, "sayısal sessizlik oranı şişirmez (SNR sınırlı)")

temiz = K.sinyal(yaz("temiz.wav", konusma(8)), temizlenmis=True)
ok(seviye(temiz, "gurultu") == "orta" and "tahmin" in next(x["ipucu"] for x in temiz["olcutler"] if x["kod"] == "gurultu"), "temizlenmiş kayıtta gürültü ölçütü 'tahmini' olarak işaretlenir")

zayif2 = K.sinyal(yaz("z2.wav", konusma(1.2, gurultu=0.05)))
ok(zayif2["genel"] == "zayif", "iki zayıf ölçüt genel kaliteyi zayıf yapar")
ok("engellemez" in K.__doc__ or "ENGELLEMEZ" in K.__doc__, "modül belgesi ölçütlerin engellemediğini belirtir")

try:
    K.sinyal(yaz("cok_kisa.wav", konusma(0.05)))
    ok(False, "çok kısa ses hata vermeli")
except RuntimeError:
    ok(True, "çok kısa ses okunamaz hatası verir (arayüz bunu 'ölçülemedi' diye gösterir)")

ok(K._kelimeler("Merhaba, bugün HAVA çok güzel!") == ["merhaba", "bugün", "hava", "çok", "güzel"], "kelime ayrıştırma Türkçe büyük/küçük harfi doğru işler")
ok(K._kelimeler("İstanbul ILIK") == ["istanbul", "ılık"], "İ/I büyük-küçük harf dönüşümü Türkçe")
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
