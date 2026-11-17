"""OpenAI görsel üretimi (ücretli, bulut). İstek biçimi resmî API belgesine göre yazılmıştır.

POST {taban}/v1/images/generations   başlık: Authorization: Bearer <anahtar>
gövde: {model, prompt, size, n:1}  → data[0].b64_json  (referans görselli düzenleme bu bağdaştırıcıda yok)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ortak  # noqa: E402

BOYUT = {"16:9": "1536x1024", "9:16": "1024x1536", "1:1": "1024x1024", "4:5": "1024x1536"}


def gorsel(ctx: dict, istem: str, cikti: Path, en_boy: str = "16:9", referans: Path | None = None) -> dict:
    if referans:
        raise ortak.IzinHatasi("openai-gorsel bağdaştırıcısı referans görsel desteklemez; karakter tutarlılığı için gemini'yi seç")
    model = ctx["model"]
    if not model:
        raise ortak.IzinHatasi("model adı gerekli: panel → Ayarlar → Bağlayıcılar → model (varsayılan model yoktur, servisin güncel adını sen yaz)")
    govde = {"model": model, "prompt": f"{istem}\nGörselde okunur yazı, logo ya da filigran olmasın.", "size": BOYUT.get(en_boy, "1024x1024"), "n": 1}
    yanit = ortak.json_http("POST", f"{ctx['taban']}/v1/images/generations", {"Authorization": f"Bearer {ctx['key']}"}, govde)
    d = (yanit.get("data") or [{}])[0]
    if not d.get("b64_json"):
        raise ortak.AgHatasi("yanıtta görsel yok")
    veri = ortak.b64_coz(d["b64_json"])
    cikti = cikti.with_suffix(".png")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_bytes(veri)
    return {"dosya": str(cikti), "bayt": len(veri), "model": model}


def duzenle(ctx: dict, istem: str, giris: bytes, mime: str, cikti: Path) -> dict:
    """Var olan fotoğrafı iyileştirir (POST /v1/images/edits, multipart). Üretken model: ayrıntı UYDURABİLİR."""
    model = ctx["model"]
    if not model:
        raise ortak.IzinHatasi("model adı gerekli: panel → Ayarlar → Bağlayıcılar → model (varsayılan model yoktur, servisin güncel adını sen yaz)")
    ad = "foto.png" if "png" in mime else "foto.jpg"
    govde, tur = ortak.multipart({"model": model, "prompt": istem, "n": "1"}, {"image": (ad, giris, mime)})
    b, _ = ortak.http("POST", f"{ctx['taban']}/v1/images/edits", {"Authorization": f"Bearer {ctx['key']}", "Content-Type": tur}, govde, 300)
    import json as _j
    try:
        d = (_j.loads(b.decode("utf-8")).get("data") or [{}])[0]
    except ValueError:
        raise ortak.AgHatasi("sunucu JSON dışında bir yanıt verdi") from None
    if not d.get("b64_json"):
        raise ortak.AgHatasi("yanıtta görsel yok")
    veri = ortak.b64_coz(d["b64_json"])
    cikti = cikti.with_suffix(".png")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_bytes(veri)
    return {"dosya": str(cikti), "bayt": len(veri), "model": model}


def test(ctx: dict) -> str:
    d = ortak.json_http("GET", f"{ctx['taban']}/v1/models", {"Authorization": f"Bearer {ctx['key']}"}, None, 30)
    return "bağlantı tamam" + (f" ({len(d.get('data', []))} model)" if "data" in d else "")
