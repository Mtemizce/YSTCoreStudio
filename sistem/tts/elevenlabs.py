"""ElevenLabs motoru (ÜCRETLİ, BULUT; isteğe bağlı). Kullanım: plan.json'da {"motor": "elevenlabs", "proje": "<ad>", "ses_id": "<voice_id>"}.

Politika (sistem/baglayici/ortak.py): bağlayıcı etkin + anahtar var + projede bulut izni gerekir; her çağrı projeler/<ad>/bulut_gunlugu.md'ye yazılır.
Metin ElevenLabs'a GİDER (seslendirme metni). İstek biçimi resmî API belgesine göre yazılmıştır.
`--aday N` ücretli motorda tek alıma indirilir (her alım faturalanır); gerçekten istiyorsan plan.json'a "aday_ucretli": N yaz.
"""
import importlib.util
import os
import subprocess
import shutil
from pathlib import Path

from . import Motor, hiz_uygula

BAG = Path(__file__).resolve().parents[1] / "baglayici"


def _yukle(ad, yol):
    spec = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(BAG))
    spec.loader.exec_module(m)
    return m


class ElevenLabsMotor(Motor):
    ad = "elevenlabs"
    aciklama = "ElevenLabs: gerçekçi ücretli seslendirme (bulut). Duygu, ses seçimi, hız, seed."
    lisans = "Ücretli servis (ElevenLabs hizmet şartları); metin buluta gider"
    atif_gerekir = False
    ucretli = True
    desteklenen = {"hiz": True, "seed": True, "duygu": True, "ses": True, "klon": False, "sozluk": False}

    def hazir_mi(self):
        try:
            ortak = _yukle("yst_ortak", BAG / "ortak.py")
        except Exception as e:  # noqa: BLE001
            return f"bağlayıcı modülü yüklenemedi: {e}"
        return None if ortak.anahtar_var("ELEVENLABS_API_KEY") else "ELEVENLABS_API_KEY yok: panel → Ayarlar → Bağlayıcılar → ElevenLabs"

    def uret(self, isler, plan, workdir, sr):
        ortak = _yukle("yst_ortak", BAG / "ortak.py")
        el = _yukle("yst_elevenlabs", BAG / "saglayici" / "elevenlabs.py")
        proje = plan.get("proje")
        ctx = ortak.izin_kontrol("elevenlabs", "ses", proje)  # IzinHatasi: etkin değil / izin yok → voice_studio'yu durdurur
        os.makedirs(workdir, exist_ok=True)
        ff = shutil.which("ffmpeg") or "ffmpeg"
        cikti = {}
        for anahtar, p in isler:
            hiz = float(p.get("hiz", 1.0))
            yerel_hiz = max(0.7, min(1.2, hiz))
            mp3 = Path(workdir) / f"{anahtar}.mp3"
            el.ses(ctx, p["metin"], mp3, p.get("ses") or plan.get("ses_id"), yerel_hiz, p.get("duygu", ""), p.get("seed"))
            ortak.gunluk(proje, "elevenlabs", "ses", p["metin"], str(mp3.relative_to(ortak.ROOT)) if ortak.ROOT in mp3.resolve().parents else mp3.name,
                         f"{ctx['model']} · {len(p['metin'])} karakter")
            wav = Path(workdir) / f"{anahtar}.wav"
            r = subprocess.run([ff, "-v", "error", "-y", "-i", str(mp3), "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", str(wav)], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("ElevenLabs sesi WAV'a çevrilemedi: " + r.stderr.strip()[-160:])
            kalan = hiz / yerel_hiz
            if abs(kalan - 1.0) > 1e-3:  # servis aralığı dışındaki hız farkı perde korumalı uygulanır
                tmp = Path(workdir) / f"{anahtar}_h.wav"
                hiz_uygula(str(wav), str(tmp), kalan)
                wav = tmp
            cikti[anahtar] = str(wav)
        return cikti


MOTOR = ElevenLabsMotor()
