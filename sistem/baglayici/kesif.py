#!/usr/bin/env python3
"""Model keşfi: sağlayıcıya bağlanır, servisin KENDİ model listesini çeker, yeteneğe göre sınıflar, önbelleğe alır. Model adı elle YAZILMAZ: listeden seçilir
(yazım hatası ya da olmayan model mümkün değil). Ön ayarlar onayarlar.json'da (adres + kimlik + liste uç noktası; model seçmez).

  python sistem/baglayici/kesif.py kesfet <sağlayıcı>       listeyi çek (anahtar yoksa ne eksik söyler)
  python sistem/baglayici/kesif.py liste <sağlayıcı> [yetenek]
Önbellek: sistem/ortam/baglayici/modeller/<sağlayıcı>.json (yeniden üretilebilir; dışa aktarmaya girmez).
Sınıflandırma: Gemini (supportedGenerationMethods), LM Studio (type), Ollama (/api/show capabilities), ElevenLabs (can_do_text_to_speech) servisin kendi alanından;
OpenAI ve genel OpenAI-uyumlu servislerde yetenek alanı yoktur, tür model adından TAHMİN edilir ('tahmin': true).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortak  # noqa: E402
from yetenek import yol_al  # noqa: E402

ONAYARLAR = Path(__file__).resolve().parent / "onayarlar.json"
KLASOR = ortak.ORTAM_B / "modeller"


def onayarlar() -> dict:
    d = json.loads(ONAYARLAR.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}


def sag_onayar(sid: str) -> tuple[dict, dict, str]:
    """(katalog girdisi, ön ayar, taban adres) ya da IzinHatasi."""
    kat = ortak.katalog()["saglayicilar"].get(sid)
    if not kat:
        raise ortak.IzinHatasi(f"bilinmeyen sağlayıcı: {sid}")
    oa_id = kat.get("on_ayar")
    oa = onayarlar().get(oa_id) if oa_id else None
    if not oa:
        raise ortak.IzinHatasi(f"'{kat.get('ad', sid)}' için model keşfi tanımlı değil (manifestte on_ayar yok): model listesini manifestte 'modeller' olarak ver")
    ay = (ortak.ayar_modul().coz().get("baglayicilar") or {}).get(sid, {})
    taban = (ay.get("taban_url") or kat.get("taban_url") or oa.get("taban_url") or "").rstrip("/")
    if not taban:
        raise ortak.IzinHatasi("taban adres boş: Bağlayıcılar → taban adres (servisin belgesindeki adres)")
    return kat, oa, taban


# ------------------------------------------------------------------ sınıflandırma
def _kalip(i: str) -> list[str]:
    low = i.lower()
    if "embed" in low:
        return ["embedding"]
    if re.search(r"whisper|transcribe", low):
        return ["stt"]
    if re.search(r"tts|speech", low):
        return ["tts"]
    if re.search(r"gpt-image|dall-e|imagen|flux|stable-diffusion|sdxl", low):
        return ["gorsel-uret", "gorsel-duzenle"]
    if re.search(r"sora|veo|video", low):
        return ["video-uret"]
    if "moderation" in low:
        return ["moderasyon"]
    return ["llm"]


def _gemini(i: str, yontemler: list) -> list[str]:
    low = i.lower()
    if "embed" in low or "embedContent" in (yontemler or []):
        return ["embedding"]
    if "imagen" in low:
        return ["gorsel-uret"]
    if "veo" in low:
        return ["video-uret"]
    if "tts" in low:
        return ["tts"]
    if "image" in low and "generateContent" in (yontemler or []):
        return ["gorsel-uret", "gorsel-duzenle"]
    if "generateContent" in (yontemler or []):
        return ["llm"]
    return []


def _istek(yontem: str, url: str, basliklar: dict, govde=None, zaman: int = 30):
    b, _ = ortak.http(yontem, url, basliklar, govde, zaman)
    return json.loads(b.decode("utf-8"))


def _basliklar_alt(oa: dict, key: str | None) -> list[dict]:
    """Kimlik başlığı alternatifleri (ilki çalışmazsa sıradaki). Anahtar yoksa ve zorunlu değilse başlıksız tek deneme."""
    alts = (oa["kesif"].get("kimlik") or [{}])
    out = []
    for a in alts:
        if any("{anahtar}" in v for v in a.values()):
            if key:
                out.append({k: v.replace("{anahtar}", key) for k, v in a.items()})
        else:
            out.append(dict(a))
    if not out and not oa.get("anahtar_gerekli"):
        out = [{}]
    return out


def _cek(oa: dict, taban: str, key: str | None, yol: str, parametre: dict | None) -> tuple[object, str | None]:
    """Kimlik alternatiflerini sırayla dener; (yanıt, kullanılan başlık adı)."""
    son = None
    for bas in _basliklar_alt(oa, key):
        url = taban + yol + (("?" + urllib.parse.urlencode(parametre)) if parametre else "")
        try:
            return _istek("GET", url, bas), ",".join(bas)
        except ortak.AgHatasi as e:
            son = e
            if not re.search(r"HTTP (400|401|403)", str(e)):
                raise
    if son:
        raise son
    raise ortak.IzinHatasi("API anahtarı gerekli (Bağlayıcılar → anahtar)")


def kesfet(sid: str) -> dict:
    kat, oa, taban = sag_onayar(sid)
    key = ortak.anahtar_oku(kat["anahtar"]) if kat.get("anahtar") else None
    if oa.get("anahtar_gerekli") and not key:
        raise ortak.IzinHatasi(f"önce API anahtarını gir ({kat.get('anahtar')}): Bağlayıcılar → anahtar")
    ks = oa["kesif"]
    ham: list = []
    sayfa_param = dict(ks.get("parametre") or {})
    yol, liste_yolu, id_yolu = ks["yol"], ks["liste"], ks["id"]
    kullanilan = None
    for _ in range(40):  # sayfalama üst sınırı
        try:
            d, kullanilan = _cek(oa, taban, key, yol, sayfa_param)
        except ortak.AgHatasi as e:
            if ks.get("yedek_yol") and yol == ks["yol"] and "HTTP 404" in str(e):  # LM Studio: yeni uç nokta yoksa OpenAI-uyumlu olana düş
                yol, liste_yolu, id_yolu = ks["yedek_yol"], ks.get("yedek_liste", liste_yolu), ks.get("yedek_id", id_yolu)
                continue
            raise
        ham += (d if liste_yolu == "$" else (yol_al(d, liste_yolu) or []))
        sp = ks.get("sayfa")
        if not sp or not isinstance(d, dict):
            break
        devam = yol_al(d, sp["devam"])
        imlec = yol_al(d, sp["imlec"])
        if not devam or not imlec:
            break
        sayfa_param[sp["parametre"]] = imlec
    modeller = []
    for it in ham:
        mid = yol_al(it, id_yolu) if isinstance(it, dict) else str(it)
        if not mid:
            continue
        if ks.get("onek_sil") and str(mid).startswith(ks["onek_sil"]):
            mid = str(mid)[len(ks["onek_sil"]):]
        ad = (yol_al(it, ks.get("ad", id_yolu)) or mid) if isinstance(it, dict) else mid
        tip = oa.get("siniflandir")
        tahmin = tip == "ad-kalibi"
        if oa.get("sabit_yetenek"):
            y = list(oa["sabit_yetenek"])
        elif tip == "gemini":
            y = _gemini(str(mid), yol_al(it, ks.get("yontemler")) or [])
        elif tip == "lmstudio":
            t = (yol_al(it, ks.get("tur_alani", "$.type")) or "llm") if isinstance(it, dict) else "llm"
            y = ["embedding"] if t == "embedding" else _kalip(str(mid)) if t == "llm" and _kalip(str(mid)) != ["llm"] else ["llm"]
            tahmin = False
        elif tip == "elevenlabs":
            y = ["tts"] if yol_al(it, ks.get("tts_alani")) else []
        else:
            y = _kalip(str(mid))
        modeller.append({"id": str(mid), "ad": str(ad), "yetenekler": y, "tahmin": tahmin})
    if ks.get("ollama_show"):  # Ollama: her model için capabilities (en çok 60)
        for m in modeller[:60]:
            try:
                d = _istek("POST", f"{taban}/api/show", {}, {"model": m["id"]}, 15)
                caps = d.get("capabilities") or []
                m["yetenekler"] = (["embedding"] if "embedding" in caps else ["llm"]) + (["gorsel-girdi"] if "vision" in caps else [])
                m["tahmin"] = False
            except (ortak.AgHatasi, ValueError):
                m["yetenekler"] = ["llm"]
    sesler = []
    if ks.get("ses_yol"):
        try:
            d, _ = _cek(oa, taban, key, ks["ses_yol"], None)
            sesler = [{"id": yol_al(v, ks["ses_id"]), "ad": yol_al(v, ks["ses_ad"]) or yol_al(v, ks["ses_id"])} for v in (yol_al(d, ks["ses_liste"]) or []) if yol_al(v, ks["ses_id"])]
        except (ortak.AgHatasi, ValueError):
            sesler = []
    if not modeller:
        raise ortak.AgHatasi("sunucu model listesi döndürmedi (adres/anahtar doğru mu?)")
    sonuc = {"saglayici": sid, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "taban": taban, "kimlik": kullanilan, "modeller": modeller, "sesler": sesler}
    KLASOR.mkdir(parents=True, exist_ok=True)
    tmp = KLASOR / f"{sid}.json.part"
    tmp.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(KLASOR / f"{sid}.json")
    return sonuc


def onbellek(sid: str) -> dict | None:
    try:
        return json.loads((KLASOR / f"{sid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def modeller_yetenek(sid: str, yetenek: str | None = None) -> list[dict]:
    c = onbellek(sid)
    if not c:
        return []
    if not yetenek:
        return c["modeller"]
    yetenek = ortak.ESKI_AD.get(yetenek, yetenek)
    return [m for m in c["modeller"] if yetenek in m["yetenekler"]]


def model_gecerli(sid: str, yetenek: str | None, model: str) -> tuple[bool, str]:
    """Seçilen model, servisin kendi listesinde var mı? (Elle yazılan/uydurma ad reddedilir.)"""
    c = onbellek(sid)
    if not c:
        return False, "önce 'Bağlan ve modelleri getir': model adı listeden seçilir"
    m = next((x for x in c["modeller"] if x["id"] == model), None)
    if not m:
        return False, f"'{model}' servisin model listesinde yok (liste {c['zaman']}'de alındı; yenile ya da listeden seç)"
    if yetenek and m["yetenekler"] and not m["tahmin"] and ortak.ESKI_AD.get(yetenek, yetenek) not in m["yetenekler"]:
        return False, f"'{model}' servise göre '{yetenek}' için uygun değil ({', '.join(m['yetenekler'])})"
    return True, ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    try:
        if len(a) >= 2 and a[0] == "kesfet":
            r = kesfet(a[1])
            print(f"{len(r['modeller'])} model, {len(r['sesler'])} ses ({r['zaman']})")
        elif len(a) >= 2 and a[0] == "liste":
            for m in modeller_yetenek(a[1], a[2] if len(a) > 2 else None):
                print(f"{m['id']:45} {','.join(m['yetenekler']):28} {'(tahmin)' if m['tahmin'] else ''}")
        else:
            print(__doc__)
            return 2
    except (ortak.IzinHatasi, ortak.AgHatasi) as e:
        print("HATA:", ortak.maskele(str(e)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
