"""ElevenLabs seslendirme (ücretli, bulut). İstek biçimi resmî API belgesine göre; İstek biçimi resmî API belgesine göre yazılmıştır.

POST {taban}/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128   başlık: xi-api-key
gövde: {text, model_id, voice_settings{stability, similarity_boost, style, use_speaker_boost, speed}, seed?}  → ses baytları (mp3)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ortak  # noqa: E402

DUYGU = {  # duygu etiketi → (stabilite, stil): düşük stabilite = daha duygulu/değişken
    "": (0.5, 0.0), "duz": (0.55, 0.0), "mutlu": (0.35, 0.35), "sakin": (0.7, 0.0), "saskin": (0.3, 0.45), "uzgun": (0.6, 0.25), "kizgin": (0.3, 0.5),
}


def _model_yok():
    raise ortak.IzinHatasi("model adı gerekli: panel → Ayarlar → Bağlayıcılar → model (varsayılan model yoktur, servisin güncel adını sen yaz)")


def ses(ctx: dict, metin: str, cikti: Path, ses_id: str | None = None, hiz: float = 1.0, duygu: str = "", seed: int | None = None) -> dict:
    vid = ses_id or ctx["ayar"].get("ses_id")
    if not vid:
        raise ortak.IzinHatasi("ElevenLabs için ses kimliği (voice_id) yok: panel → Ayarlar → Bağlayıcılar → ElevenLabs → ses_id")
    stab, stil = DUYGU.get(duygu or "", DUYGU[""])
    govde = {"text": metin, "model_id": ctx["model"] or _model_yok(),
             "voice_settings": {"stability": stab, "similarity_boost": 0.75, "style": stil, "use_speaker_boost": True,
                                "speed": max(0.7, min(1.2, float(hiz)))}}
    if seed is not None:
        govde["seed"] = int(seed) % 4294967295
    url = f"{ctx['taban']}/v1/text-to-speech/{vid}?output_format=mp3_44100_128"
    b, _ = ortak.http("POST", url, {"xi-api-key": ctx["key"], "Accept": "audio/mpeg"}, govde)
    if len(b) < 200:
        raise ortak.AgHatasi("ses verisi boş/çok kısa geldi")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_bytes(b)
    return {"dosya": str(cikti), "bayt": len(b), "model": govde["model_id"]}


def test(ctx: dict) -> str:
    d = ortak.json_http("GET", f"{ctx['taban']}/v1/user", {"xi-api-key": ctx["key"]}, None, 30)
    return "bağlantı tamam" + (f" (plan: {d['subscription'].get('tier')})" if isinstance(d.get("subscription"), dict) else "")
