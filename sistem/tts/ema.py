"""EMA Lightning (Apache-2.0): yerel, tek ses, yalnızca Türkçe. Kontroller: hız (yerel) + seed. Duygu/ses seçimi yok."""
import os

from . import Motor


class EMAMotor(Motor):
    ad = "ema"
    aciklama = "EMA Lightning: tek ses, hız + seed. Hızlı ve tutarlı; 'düz' tonlu."
    lisans = "Apache-2.0 (ema-lightning)"
    atif_gerekir = False
    desteklenen = {"hiz": True, "seed": True, "duygu": False, "ses": False, "klon": False, "sozluk": False}

    def __init__(self):
        self._ema = None

    def hazir_mi(self):
        try:
            import ema_lightning  # noqa: F401
        except ImportError:
            return "ema-lightning kurulu değil (Başlat.cmd kurulumu getirir)"
        return None

    def uret(self, isler, plan, workdir, sr):
        if self._ema is None:
            from ema_lightning import EMA
            self._ema = EMA()
        os.makedirs(workdir, exist_ok=True)
        cikti = {}
        for anahtar, p in isler:
            yol = os.path.join(workdir, f"{anahtar}.wav")
            self._ema.say(p["metin"], path=yol, speed=float(p.get("hiz", 1.0)), seed=p["seed"], sample_rate=sr)
            cikti[anahtar] = yol
        return cikti


MOTOR = EMAMotor()
