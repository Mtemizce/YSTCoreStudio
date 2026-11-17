"""Google Gemini görsel üretimi (ücretli, bulut). İstek biçimi resmî API belgesine göre yazılmıştır. Model adı Ayarlar'dan değişir.

POST {taban}/v1beta/models/{model}:generateContent   başlık: x-goog-api-key
gövde: {contents:[{parts:[{text}, {inlineData}?]}], generationConfig:{responseModalities:["IMAGE"], imageConfig:{aspectRatio}}}
yanıt: candidates[0].content.parts[].inlineData.{mimeType,data(base64)}
Sunucu imageConfig'i reddederse (400) oran istem metnine yazılarak imageConfig'siz yeniden denenir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ortak  # noqa: E402

ORANLAR = {"16:9": "16:9 yatay (widescreen)", "9:16": "9:16 dikey (portre)", "1:1": "1:1 kare", "4:5": "4:5 dikey"}


def _cikar(yanit: dict) -> tuple[bytes, str]:
    for c in yanit.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            d = p.get("inlineData") or p.get("inline_data")
            if d and d.get("data"):
                return ortak.b64_coz(d["data"]), d.get("mimeType") or d.get("mime_type") or "image/png"
    raise ortak.AgHatasi("yanıtta görsel yok (model görsel üretmedi ya da istem reddedildi)")


def gorsel(ctx: dict, istem: str, cikti: Path, en_boy: str = "16:9", referans: Path | None = None) -> dict:
    model = ctx["model"]
    if not model:
        raise ortak.IzinHatasi("model adı gerekli: panel → Ayarlar → Bağlayıcılar → model (varsayılan model yoktur, servisin güncel adını sen yaz)")
    parcalar: list = [{"text": f"{istem}\n\nGörsel oranı: {ORANLAR.get(en_boy, en_boy)}. Görselde okunur yazı, logo ya da filigran olmasın."}]
    if referans:
        import base64
        parcalar.append({"inlineData": {"mimeType": "image/png" if referans.suffix.lower() == ".png" else "image/jpeg",
                                         "data": base64.b64encode(referans.read_bytes()).decode()}})
    url = f"{ctx['taban']}/v1beta/models/{model}:generateContent"
    bas = {"x-goog-api-key": ctx["key"]}
    govde = {"contents": [{"parts": parcalar}], "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": en_boy}}}
    try:
        yanit = ortak.json_http("POST", url, bas, govde)
    except ortak.AgHatasi as e:
        if "HTTP 400" not in str(e):
            raise
        govde.pop("generationConfig")  # oran yalnızca istem metninde
        yanit = ortak.json_http("POST", url, bas, govde)
    veri, mime = _cikar(yanit)
    cikti = cikti.with_suffix(".jpg" if "jpeg" in mime else ".png")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_bytes(veri)
    return {"dosya": str(cikti), "bayt": len(veri), "model": model}


def duzenle(ctx: dict, istem: str, giris: bytes, mime: str, cikti: Path) -> dict:
    """Var olan fotoğrafı iyileştirir (çözünürlük/netlik). Üretken model: ayrıntı UYDURABİLİR; gerçeğe sadık kullanımda yerel modeli seç."""
    import base64
    model = ctx["model"]
    if not model:
        raise ortak.IzinHatasi("model adı gerekli: panel → Ayarlar → Bağlayıcılar → model (varsayılan model yoktur, servisin güncel adını sen yaz)")
    govde = {"contents": [{"parts": [{"text": istem}, {"inlineData": {"mimeType": mime, "data": base64.b64encode(giris).decode()}}]}],
             "generationConfig": {"responseModalities": ["IMAGE"]}}
    yanit = ortak.json_http("POST", f"{ctx['taban']}/v1beta/models/{model}:generateContent", {"x-goog-api-key": ctx["key"]}, govde, 300)
    veri, m = _cikar(yanit)
    cikti = cikti.with_suffix(".jpg" if "jpeg" in m else ".png")
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_bytes(veri)
    return {"dosya": str(cikti), "bayt": len(veri), "model": model}


def test(ctx: dict) -> str:
    d = ortak.json_http("GET", f"{ctx['taban']}/v1beta/models?pageSize=1", {"x-goog-api-key": ctx["key"]}, None, 30)
    return "bağlantı tamam" + (f" ({len(d.get('models', []))} model listelendi)" if "models" in d else "")
