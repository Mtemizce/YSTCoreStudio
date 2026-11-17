"""Konuşma (TTS) motor adaptörleri. Her motor bu klasörde TEK bir .py dosyasıdır ve bir `MOTOR` nesnesi dışa aktarır.

Yeni bir açık kaynak Türkçe motor eklemek için:
  1. tts/<ad>.py oluştur, `Motor`'dan türeyen bir sınıf yaz, dosya sonunda `MOTOR = Sinif()`.
  2. `uret(isler, plan, workdir, sr)` her iş için bir WAV üretip {anahtar: yol} döndürsün; `parca["hiz"]` UYGULANMIŞ olsun
     (motor yerel hız desteklemiyorsa `hiz_uygula` yardımcısını kullan).
  3. Lisansı `lisans` alanına yaz. Atıf (attribution) gerektiren (CC-BY vb.) motor eklerken atıf gereği yerine getirilir:
     `atif_gerekir = True` ve `atif = "<atıf metni>"` ver; voice_studio çıktının yanına ATIF.txt yazar, README ve panel (Sistem → Lisanslar) listeler.
     (Pocket TTS Turkish bu yolla eklendi: pocket.py.)
  4. Modeli varsa varlik/varliklar.db'ye `varlik.py ekle` ile kaydet. Planda `"motor": "<ad>"` ile seç.
Gerisini (parçalama, duraklama, ton adayı seçimi, ses işleme, ölçüm) `voice_studio.py` yapar: motordan bağımsızdır.
"""
from __future__ import annotations

import importlib
import pkgutil
import shutil
import subprocess
import sys


class Motor:
    ad = ""
    aciklama = ""
    lisans = ""
    atif_gerekir = False          # True ise paylaşımda atıf satırı gerekir
    ucretli = False               # True ise her alım faturalanır (bulut): voice_studio aday sayısını 1'e indirir
    ses_listesi: list = []        # varsa seçilebilir ses adları
    desteklenen = {"hiz": True, "seed": True, "duygu": False, "ses": False, "klon": False, "sozluk": False}

    def hazir_mi(self):
        """Kullanılabilirse None, değilse nedenini (Türkçe) döndür."""
        return None

    def uret(self, isler, plan, workdir, sr):
        """isler: [(anahtar, parça)] -> {anahtar: wav yolu}. Parçadaki hız motor tarafından uygulanmış olmalı."""
        raise NotImplementedError


def hiz_uygula(src, dst, hiz):
    """Perde korumalı hız (ffmpeg atempo; 0.5-2 aralığı zincirlenir)."""
    zincir, s = [], hiz
    while s > 2.0:
        zincir.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        zincir.append("atempo=0.5")
        s /= 0.5
    if abs(s - 1.0) > 1e-3:
        zincir.append(f"atempo={s:.4f}")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-v", "error", "-y", "-i", src] + (["-af", ",".join(zincir)] if zincir else []) + [dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg hız hatası: " + r.stderr.strip()[-200:])


def motorlar():
    out = {}
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{m.name}")
        if hasattr(mod, "MOTOR"):
            out[mod.MOTOR.ad] = mod.MOTOR
    return out


def al(ad):
    m = motorlar()
    if ad not in m:
        sys.exit(f"bilinmeyen TTS motoru '{ad}'. Kurulu motorlar: {', '.join(m) or 'yok'}")
    neden = m[ad].hazir_mi()
    if neden:
        sys.exit(f"TTS motoru '{ad}' kullanılamıyor: {neden}")
    return m[ad]
