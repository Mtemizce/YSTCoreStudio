"""Pocket TTS Turkish (CC-BY-4.0; ATIF GEREKİR): yerel, işlemcide çalışan Türkçe motor; 6 hazır ses, duygu etiketi ve SES KLONLAMA.

Kullanım (plan.json):
  {"motor": "pocket-tr", "ses": "female_2", "duygu": "sakin"}                       hazır ses (female_1..3, male_1..3)
  {"motor": "pocket-tr", "klon": "klon/ornek.wav"}                                  örnek sesin tınısıyla okur
Klonlama panelde "Sesimi klonla" seçilince açılır; kullanıcı orada uyarıyı (yalnızca kendi sesi ya da sahibinin izniyle) kabul eder.
Motor kendi başına ek onay istemez: onay kapısı panel arayüzündedir.
Örnek ses: 3-10 sn temiz, tek kişi, arka plan müziği yok; iki sözcük arasındaki sessizlikte biten kayıt en iyi sonucu verir (paket fazlasını keser ve uyarır).
Kurulum: panel → Ayarlar → Sistem → "Ses klonlama (Pocket TTS Turkish)" → Kur (pip paketi + ~0,45 GB model).

Atıf (CC-BY-4.0): "Pocket TTS Turkish by wite-tech, CC-BY-4.0, derived from Kyutai's Pocket TTS (CC-BY-4.0) with Turkish fine-tuning and
six-layer distillation." README ve panel → Sistem → Lisanslar'da yer alır; bu motorla üretilen her çıktının yanına ATIF.txt yazılır.
"""
import os
import shutil
import subprocess
from pathlib import Path

from . import Motor, hiz_uygula

ROOT = Path(__file__).resolve().parents[2]
ATIF = ("Pocket TTS Turkish by wite-tech (https://huggingface.co/wite-tech/pocket-tts-turkish), CC-BY-4.0, derived from Kyutai's Pocket TTS "
        "(CC-BY-4.0) with Turkish fine-tuning and six-layer distillation.")
SESLER = ("female_1", "female_2", "female_3", "male_1", "male_2", "male_3")
DUYGULAR = ("mutlu", "üzgün", "kızgın", "şaşkın", "sakin")


class PocketMotor(Motor):
    ad = "pocket-tr"
    aciklama = "Pocket TTS Turkish: işlemcide hızlı, 6 hazır ses, duygu etiketi ve ses klonlama. Atıf gerektirir (CC-BY-4.0)."
    lisans = "CC-BY-4.0 (atıf gerekir): Pocket TTS Turkish (wite-tech), Kyutai Pocket TTS türevi"
    atif_gerekir = True
    atif = ATIF
    ses_listesi = list(SESLER)
    desteklenen = {"hiz": True, "seed": True, "duygu": True, "ses": True, "klon": True, "sozluk": False}

    def __init__(self):
        self._tts = None
        self._sesler = {}

    def hazir_mi(self):
        try:
            import pocket_tts_turkish  # noqa: F401
        except ImportError:
            return "pocket-tts-turkish kurulu değil: panel → Ayarlar → Sistem → Ses klonlama → Kur"
        return None

    def _ses(self, p, plan, kok):
        klon = p.get("klon") or plan.get("klon")
        if klon:
            yol = Path(klon)
            if not yol.is_absolute():
                yol = Path(kok) / yol
            if not yol.is_file():
                raise RuntimeError(f"klon örnek sesi bulunamadı: {yol}")
            anahtar = (str(yol), yol.stat().st_mtime_ns)
            if anahtar not in self._sesler:
                self._sesler[anahtar] = self._tts.voice_from_file(str(yol))
            return self._sesler[anahtar]
        ses = p.get("ses") or plan.get("ses") or "female_1"
        if ses not in SESLER:
            raise RuntimeError(f"bilinmeyen ses '{ses}': {', '.join(SESLER)}")
        return ses

    def uret(self, isler, plan, workdir, sr):
        if self._tts is None:
            from pocket_tts_turkish import TurkishTTS
            self._tts = TurkishTTS.from_pretrained()
        from pocket_tts_turkish import save_wav
        proje = plan.get("proje")
        kok = str(ROOT / "projeler" / proje) if proje and (ROOT / "projeler" / proje).is_dir() else os.getcwd()  # göreli klon yolu proje klasörüne göre
        os.makedirs(workdir, exist_ok=True)
        ff = shutil.which("ffmpeg") or "ffmpeg"
        cikti = {}
        for anahtar, p in isler:
            duygu = p.get("duygu") or plan.get("duygu") or None
            if duygu and duygu not in DUYGULAR:
                raise RuntimeError(f"bilinmeyen duygu '{duygu}': {', '.join(DUYGULAR)}")
            try:
                import torch
                torch.manual_seed(int(p.get("seed", plan.get("seed", 1))))
            except ImportError:
                pass
            kwargs = {"voice": self._ses(p, plan, kok)}
            if duygu:
                kwargs["emotion"] = duygu
            ham = os.path.join(workdir, f"{anahtar}_ham.wav")
            save_wav(ham, self._tts.generate(p["metin"], **kwargs), self._tts.sample_rate)
            hizli = os.path.join(workdir, f"{anahtar}_hiz.wav")
            hiz_uygula(ham, hizli, float(p.get("hiz", 1.0)))
            yol = os.path.join(workdir, f"{anahtar}.wav")
            r = subprocess.run([ff, "-v", "error", "-y", "-i", hizli, "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", yol], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError("ses dönüştürülemedi: " + r.stderr.strip()[-160:])
            cikti[anahtar] = yol
        return cikti


MOTOR = PocketMotor()
