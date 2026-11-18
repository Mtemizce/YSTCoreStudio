#!/usr/bin/env python3
"""Yetenek (capability) çekirdeği: stüdyo bir işi "yetenek" olarak ister (görsel üret, video üret…); hangi SAĞLAYICININ yapacağını kullanıcı belirler.
Hiçbir sağlayıcı ya da model varsayılan değildir: kullanıcı kendi servisini tanımlar (Ayarlar → Bağlayıcılar → Sağlayıcı ekle) ve yetenek başına
sıralı yedek listesi yapar (kredi bitti/ulaşılamıyorsa sıradaki denenir).

Sağlayıcı türleri (kullanıcı tanımlı manifest, kodsuz):
  http-is        asenkron HTTP servis: gönder → durum sorgula → çıktıyı indir (Higgsfield/Seedance/HeyGen/fal tipi servisler). Bildirimsel şablonlarla.
  openai-uyumlu  base URL + anahtar + model: /v1/images/generations, /v1/images/edits, /v1/audio/speech (OpenAI, DeepSeek-benzeri, yerel sunucular)
  mock           sahte çıktı (anahtarsız test; hiçbir yere bağlanmaz)
Mevcut kod bağdaştırıcıları (elevenlabs, gemini, openai-gorsel) ve yerel motorlar (ema) bu çekirdeğin dışında aynen çalışır.

  python sistem/baglayici/yetenek.py liste                                  yetenekler ve her biri için kullanılabilir sağlayıcılar
  python sistem/baglayici/yetenek.py cagir --yetenek video-uret --girdi '{"istem":"…"}' --cikti x/video [--saglayici id] [--proje ad] [--onay]
  python sistem/baglayici/yetenek.py butce                                  bugünkü harcama ve tavan
Çıkış kodları: 0 tamam · 2 girdi hatası · 3 izin/ayar · 4 ağ/servis · 7 bütçe tavanı
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortak  # noqa: E402

ROOT = ortak.ROOT
HARCAMA = ortak.ORTAM_B / "harcama.jsonl"
YETENEKLER = {
    "gorsel-uret": "Görsel / karakter üretimi", "gorsel-duzenle": "Fotoğraf iyileştirme / düzenleme", "gorsel-buyut": "Görsel büyütme",
    "video-uret": "Video üretimi (metinden / görselden)", "avatar-video": "Konuşan / yürüyen karakter videosu", "tts": "Seslendirme", "ses-klon": "Ses klonlama",
    "stt": "Konuşma → yazı", "muzik": "Müzik",
}
ESKI_AD = {"ses": "tts", "gorsel": "gorsel-uret"}  # eski kataloğun tür adları
MAX_INDIR = 600_000_000
_YOK = object()


class ButceHatasi(Exception):
    pass


class GirdiHatasi(Exception):
    pass


# ------------------------------------------------------------------ şablon motoru (kod çalıştırmaz, yalnızca yer değiştirir)
_TAM = re.compile(r"^\{([a-z_][a-z0-9_]*)(\?)?\}$")
_ICTE = re.compile(r"\{([a-z_][a-z0-9_]*)(\?)?\}")


def doldur(sablon, ctx: dict):
    """{alan} yer tutucularını doldurur. Tüm metin tek yer tutucuysa değer olduğu gibi (sayı/liste/nesne) konur. {alan?} eksikse alan düşer."""
    if isinstance(sablon, str):
        m = _TAM.match(sablon)
        if m:
            k, opt = m.group(1), bool(m.group(2))
            v = ctx.get(k)
            if v is None or v == "":
                if opt:
                    return _YOK
                raise GirdiHatasi(f"gerekli alan eksik: {k}")
            return v

        def yer(mo):
            v = ctx.get(mo.group(1))
            if v is None or v == "":
                if mo.group(2):
                    return ""
                raise GirdiHatasi(f"gerekli alan eksik: {mo.group(1)}")
            return str(v)
        return _ICTE.sub(yer, sablon)
    if isinstance(sablon, dict):
        out = {}
        for k, v in sablon.items():
            d = doldur(v, ctx)
            if d is not _YOK:
                out[k] = d
        return out
    if isinstance(sablon, list):
        return [d for d in (doldur(v, ctx) for v in sablon) if d is not _YOK]
    return sablon


def yol_al(obj, yol: str | None):
    """Çok basit JSONPath: $.a.b[0].c  (yoksa None)."""
    if not yol:
        return None
    s = yol[1:] if yol.startswith("$") else yol
    for ad, idx in re.findall(r"\.?([A-Za-z0-9_\-]+)|\[(\d+)\]", s):
        try:
            obj = obj[int(idx)] if idx != "" else obj[ad]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return obj


# ------------------------------------------------------------------ manifest doğrulama
def _ayar():
    return ortak.ayar_modul()


def ozel_saglayicilar() -> dict:
    return (_ayar().coz().get("saglayicilar") or {})


def manifest(sid: str) -> dict | None:
    return ozel_saglayicilar().get(sid)


# ------------------------------------------------------------------ HTTP yardımcıları
def _basliklar(m: dict, key: str | None) -> dict:
    h = {}
    k = m.get("kimlik") or {}
    if k.get("baslik") and key:
        h[k["baslik"]] = str(k.get("sablon", "{anahtar}")).replace("{anahtar}", key)
    for ad, v in (m.get("basliklar") or {}).items():
        h[ad] = str(v)
    return h


def _http_json(yontem: str, url: str, basliklar: dict, govde, zaman: int = 120) -> dict:
    ortak._url_kontrol(url)
    if isinstance(govde, dict) and yontem.upper() == "GET":
        govde = None
    b, _ = ortak.http(yontem.upper(), url, basliklar, govde, zaman)
    try:
        return json.loads(b.decode("utf-8"))
    except ValueError:
        raise ortak.AgHatasi("sunucu JSON dışında bir yanıt verdi") from None


def _indir(url: str, hedef: Path, basliklar: dict | None = None) -> int:
    ortak._url_kontrol(url)
    istek = urllib.request.Request(url, headers={"User-Agent": ortak.UA, **(basliklar or {})})
    try:
        with urllib.request.urlopen(istek, timeout=300) as r:
            ortak._url_kontrol(r.geturl())  # yönlendirme http'ye düşmesin
            n = 0
            hedef.parent.mkdir(parents=True, exist_ok=True)
            tmp = hedef.with_suffix(hedef.suffix + ".part")
            with open(tmp, "wb") as f:
                while True:
                    blok = r.read(1 << 20)
                    if not blok:
                        break
                    n += len(blok)
                    if n > MAX_INDIR:
                        f.close()
                        tmp.unlink(missing_ok=True)
                        raise ortak.AgHatasi("indirilen dosya sınırı aşıyor")
                    f.write(blok)
            tmp.replace(hedef)
            return n
    except urllib.error.HTTPError as e:
        raise ortak.AgHatasi(f"indirme HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise ortak.AgHatasi(f"indirilemedi: {e.reason}") from None


def _uzanti(url_ya_da_tur: str, varsayilan: str) -> str:
    m = re.search(r"\.([A-Za-z0-9]{2,4})(?:\?|$)", url_ya_da_tur or "")
    return "." + m.group(1).lower() if m and m.group(1).lower() in ("mp4", "mov", "webm", "png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a", "gif") else varsayilan


# ------------------------------------------------------------------ türler
def _http_is(m: dict, yetenek: str, girdi: dict, ctx: dict, cikti: Path) -> dict:
    uc = (m.get("uc") or {}).get(yetenek)
    if not uc:
        raise ortak.IzinHatasi(f"'{m['ad']}' bu yeteneği tanımlamamış: {yetenek}")
    taban = ctx["taban"]
    bas = _basliklar(m, ctx["key"])
    degerler = {"anahtar": ctx["key"] or "", "model": ctx["model"] or m.get("model", ""), **girdi}
    g = uc["gonder"]
    yanit = _http_json(g.get("yontem", "POST"), taban + doldur(g["yol"], degerler), bas, doldur(g.get("govde"), degerler), 180)
    cikti_tanim = uc.get("cikti") or {"yol": "$.url", "tur": "url"}
    durum = uc.get("durum")
    sonuc = yanit
    if durum:
        is_id = yol_al(yanit, g.get("sonuc_id", "$.id"))
        if is_id in (None, ""):
            raise ortak.AgHatasi("servis iş kimliği döndürmedi (manifest: gonder.sonuc_id)")
        degerler["id"] = str(is_id)
        bek = durum.get("bekle") or {}
        aralik, en_cok = max(1.0, float(bek.get("aralik", 5))), float(bek.get("en_cok", 900))
        t0 = time.time()
        while True:
            sonuc = _http_json(durum.get("yontem", "GET"), taban + doldur(durum["yol"], degerler), bas, doldur(durum.get("govde"), degerler), 60)
            d = str(yol_al(sonuc, durum.get("durum_alani", "$.status")))
            if d in [str(x) for x in durum.get("biten", ["completed", "succeeded", "done"])]:
                break
            if d in [str(x) for x in durum.get("hatali", ["failed", "error", "cancelled"])]:
                raise ortak.AgHatasi(f"servis işi başarısız bitirdi: {yol_al(sonuc, durum.get('hata_alani', '$.error')) or d}")
            if time.time() - t0 > en_cok:
                raise ortak.AgHatasi(f"zaman aşımı ({int(en_cok)} sn): iş hâlâ '{d}'")
            time.sleep(aralik)
    endpoint = uc.get("sonuc")
    if endpoint:
        path = doldur(endpoint["yol"], degerler)
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
            raise GirdiHatasi("Sonuç yolu sağlayıcının taban adresine göreli olmalı")
        sonuc = _http_json("GET", taban + path, bas, None, 60)
    tur = cikti_tanim.get("tur", "url")
    deger = yol_al(sonuc, cikti_tanim.get("yol"))
    if deger in (None, "", []):
        raise ortak.AgHatasi("yanıtta çıktı yok (manifest: cikti.yol)")
    if isinstance(deger, list):
        deger = deger[0]
    varsayilan_uz = ".mp4" if yetenek in ("video-uret", "avatar-video") else (".mp3" if yetenek in ("tts", "muzik", "ses-klon") else ".png")
    if tur == "b64":
        veri = base64.b64decode(deger)
        dosya = cikti.with_suffix(cikti_tanim.get("uzanti", varsayilan_uz))
        dosya.parent.mkdir(parents=True, exist_ok=True)
        dosya.write_bytes(veri)
        n = len(veri)
    else:
        dosya = cikti.with_suffix(_uzanti(str(deger), cikti_tanim.get("uzanti", varsayilan_uz)))
        n = _indir(str(deger), dosya, bas if cikti_tanim.get("kimlik") else None)
    return {"dosya": str(dosya), "bayt": n, "model": degerler.get("model") or ""}


def _openai_uyumlu(m: dict, yetenek: str, girdi: dict, ctx: dict, cikti: Path) -> dict:
    model = girdi.get("model") or ctx["model"] or m.get("model")
    if not model:
        raise ortak.IzinHatasi("model adı gerekli (Ayarlar → Bağlayıcılar → model)")
    bas = {"Authorization": f"Bearer {ctx['key']}"} if ctx["key"] else {}
    taban = ctx["taban"]
    if yetenek == "gorsel-uret":
        d = _http_json("POST", f"{taban}/v1/images/generations", bas, {"model": model, "prompt": girdi["istem"], "n": 1, **({"size": girdi["boyut"]} if girdi.get("boyut") else {})}, 300)
    elif yetenek == "gorsel-duzenle":
        raw = girdi.get("gorsel_bayt")
        if not raw:
            raise GirdiHatasi("gorsel_bayt gerekli")
        govde, tur = ortak.multipart({"model": model, "prompt": girdi["istem"], "n": "1"}, {"image": ("foto.jpg", raw, girdi.get("mime", "image/jpeg"))})
        b, _ = ortak.http("POST", f"{taban}/v1/images/edits", {**bas, "Content-Type": tur}, govde, 300)
        d = json.loads(b.decode("utf-8"))
    elif yetenek == "tts":
        b, _ = ortak.http("POST", f"{taban}/v1/audio/speech", bas, {"model": model, "input": girdi["metin"], "voice": girdi.get("ses", "alloy")}, 300)
        dosya = cikti.with_suffix(".mp3")
        dosya.parent.mkdir(parents=True, exist_ok=True)
        dosya.write_bytes(b)
        return {"dosya": str(dosya), "bayt": len(b), "model": model}
    else:
        raise ortak.IzinHatasi(f"openai-uyumlu türü bu yeteneği desteklemez: {yetenek}")
    o = (d.get("data") or [{}])[0]
    dosya = cikti.with_suffix(".png")
    dosya.parent.mkdir(parents=True, exist_ok=True)
    if o.get("b64_json"):
        dosya.write_bytes(base64.b64decode(o["b64_json"]))
    elif o.get("url"):
        _indir(o["url"], dosya)
    else:
        raise ortak.AgHatasi("yanıtta görsel yok")
    return {"dosya": str(dosya), "bayt": dosya.stat().st_size, "model": model}


def _mock(m: dict, yetenek: str, girdi: dict, ctx: dict, cikti: Path) -> dict:
    """Sahte çıktı: ağa çıkmaz. Akışları anahtarsız denemek için."""
    cikti.parent.mkdir(parents=True, exist_ok=True)
    metin = str(girdi.get("istem") or girdi.get("metin") or yetenek)[:60]
    if yetenek in ("video-uret", "avatar-video") and shutil.which("ffmpeg"):
        dosya = cikti.with_suffix(".mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=2", "-pix_fmt", "yuv420p", str(dosya)],
                       check=True, capture_output=True, creationflags=0x08000000 if sys.platform == "win32" else 0)
    elif yetenek in ("tts", "muzik", "ses-klon") and shutil.which("ffmpeg"):
        dosya = cikti.with_suffix(".wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(dosya)], check=True, capture_output=True,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    else:
        from PIL import Image, ImageDraw
        dosya = cikti.with_suffix(".png")
        im = Image.new("RGB", (640, 360), (60, 60, 80))
        ImageDraw.Draw(im).text((20, 160), "MOCK: " + metin, fill=(255, 255, 255))
        im.save(dosya)
    return {"dosya": str(dosya), "bayt": dosya.stat().st_size, "model": "mock"}


def _kod(m: dict, yetenek: str, girdi: dict, ctx: dict, cikti: Path) -> dict:
    """Yerleşik kod bağdaştırıcıları (elevenlabs, gemini, openai-gorsel): aynı yetenek arayüzünden çağrılır. Model adı yine kullanıcıdan gelir."""
    import uret
    mod = uret.sag_modul(ctx["sid"])
    if yetenek == "gorsel-uret" and hasattr(mod, "gorsel"):
        ref = girdi.get("referans")
        return mod.gorsel(ctx, girdi["istem"], cikti, girdi.get("en_boy", "16:9"), Path(ref) if ref else None)
    if yetenek == "gorsel-duzenle" and hasattr(mod, "duzenle"):
        return mod.duzenle(ctx, girdi["istem"], girdi["gorsel_bayt"], girdi.get("mime", "image/jpeg"), cikti)
    if yetenek == "tts" and hasattr(mod, "ses"):
        return mod.ses(ctx, girdi["metin"], cikti, girdi.get("ses"), float(girdi.get("hiz", 1.0)), girdi.get("duygu", ""))
    raise ortak.IzinHatasi(f"{ctx['sid']} bu yeteneği yapmaz: {yetenek}")


TURLER = {"http-is": _http_is, "openai-uyumlu": _openai_uyumlu, "mock": _mock, "kod": _kod}


# ------------------------------------------------------------------ bütçe
def butce_ayari() -> dict:
    b = {"mod": "cap", "gun_tavan": 5.0, "onay_esigi": 1.0, "para": "USD"}
    b.update({k: v for k, v in (_ayar().coz().get("butce") or {}).items() if k in b})
    return b


def bugun_harcama() -> float:
    gun = time.strftime("%Y-%m-%d")
    t = 0.0
    try:
        for s in HARCAMA.read_text(encoding="utf-8").splitlines():
            d = json.loads(s)
            if str(d.get("zaman", ""))[:10] == gun:
                t += float(d.get("tutar") or 0)
    except (OSError, ValueError):
        pass
    return round(t, 4)


def tahmin(m: dict | None, yetenek: str, girdi: dict) -> float | None:
    """Manifest `maliyet.<yetenek>` = {sabit: x} ya da {birim_alani: 'sure', fiyat: y}. Tanımsızsa None (maliyet bilinmiyor)."""
    c = ((m or {}).get("maliyet") or {}).get(yetenek)
    if not c:
        return None
    try:
        if "sabit" in c:
            return float(c["sabit"])
        return float(c["fiyat"]) * float(girdi.get(c.get("birim_alani", "adet"), 1))
    except (KeyError, TypeError, ValueError):
        return None


def butce_kapisi(t: float | None, onay: bool) -> str | None:
    """Tavan aşılacaksa ButceHatasi; uyarı metni (ya da None) döndürür."""
    b = butce_ayari()
    if t is None:
        return "maliyet bilinmiyor (manifest'te 'maliyet' tanımlı değil): tavan uygulanamaz"
    harcanan = bugun_harcama()
    if b["mod"] == "cap" and b["gun_tavan"] and harcanan + t > float(b["gun_tavan"]):
        raise ButceHatasi(f"günlük tavan aşılır: bugün {harcanan} + bu işlem ~{t} > {b['gun_tavan']} {b['para']} (Ayarlar → Bütçe)")
    if b["onay_esigi"] and t > float(b["onay_esigi"]) and not onay:
        raise ButceHatasi(f"tahmini maliyet ~{t} {b['para']} onay eşiğini ({b['onay_esigi']}) aşıyor: onay ver (--onay / panelde onay kutusu)")
    return None


def harcama_yaz(sid: str, yetenek: str, tutar: float | None, proje: str | None) -> None:
    ortak.ORTAM_B.mkdir(parents=True, exist_ok=True)
    with open(HARCAMA, "a", encoding="utf-8") as f:
        f.write(json.dumps({"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "saglayici": sid, "yetenek": yetenek, "tutar": tutar, "proje": proje}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ seçim ve çağrı
def yetenek_adlari(kat: dict) -> set[str]:
    return {ESKI_AD.get(t, t) for t in kat.get("tur", [])}


def adaylar(yetenek: str, tercih: str | None = None) -> list[str]:
    kat = ortak.katalog()["saglayicilar"]
    uygun = [sid for sid, k in kat.items() if yetenek in yetenek_adlari(k)]
    if tercih:
        return [tercih]
    sira = ((_ayar().coz().get("yetenekler") or {}).get(yetenek) or {}).get("sira") or []
    return [s for s in sira if s in uygun] + [s for s in uygun if s not in sira]


def hazir(sid: str, yetenek: str, proje: str | None, onay: bool) -> tuple[bool, str]:
    kat = ortak.katalog()["saglayicilar"].get(sid)
    if not kat:
        return False, "sağlayıcı yok"
    if yetenek not in yetenek_adlari(kat):
        return False, f"'{yetenek}' yapmaz"
    try:
        ortak.izin_kontrol_genel(sid, yetenek, proje, onay)
        return True, ""
    except ortak.IzinHatasi as e:
        return False, str(e)


def cagir(yetenek: str, girdi: dict, cikti: str | Path, tercih: str | None = None, proje: str | None = None, onay: bool = False, yedek: bool = True) -> dict:
    """Yeteneği ister; sıradaki hazır sağlayıcıyla yapar. Bulut için: bağlayıcı etkin + anahtar + (proje bulut izni YA DA onay=True). Dönüş: {dosya, saglayici, model, maliyet, denenen}"""
    if yetenek not in YETENEKLER:
        raise GirdiHatasi(f"bilinmeyen yetenek: {yetenek}")
    cikti = Path(cikti)
    cikti = (cikti if cikti.is_absolute() else ROOT / cikti)
    liste = adaylar(yetenek, tercih)
    if not liste:
        raise ortak.IzinHatasi(f"'{yetenek}' için tanımlı sağlayıcı yok: Ayarlar → Bağlayıcılar → Sağlayıcı ekle")
    denenen, son_hata = [], None
    for sid in liste:
        m = manifest(sid)
        tip = (m or {}).get("tur")
        if m is None and sid in ("elevenlabs", "gemini", "openai-gorsel"):
            tip, m = "kod", {}
        if tip not in TURLER:
            denenen.append({"saglayici": sid, "durum": "atlandı", "neden": "bu çekirdekle çağrılamaz (yerel motor ya da MCP: kendi aracını kullan)"})
            continue
        ok, neden = hazir(sid, yetenek, proje, onay)
        if not ok:
            denenen.append({"saglayici": sid, "durum": "atlandı", "neden": neden})
            son_hata = ortak.IzinHatasi(neden)
            continue
        t = tahmin(m, yetenek, girdi)
        uyari = butce_kapisi(t, onay)  # ButceHatasi yukarı çıkar: tavan aşılırsa zincir de durur
        ctx = ortak.izin_kontrol_genel(sid, yetenek, proje, onay)
        ctx["sid"] = sid
        try:
            r = TURLER[tip](m, yetenek, girdi, ctx, cikti)
        except (ortak.AgHatasi, ortak.IzinHatasi) as e:
            denenen.append({"saglayici": sid, "durum": "hata", "neden": ortak.maskele(str(e))[:200]})
            son_hata = e
            if not yedek:
                raise
            continue
        harcama_yaz(sid, yetenek, t, proje)
        ozet = json.dumps({k: (v if not isinstance(v, (bytes, bytearray)) else f"<{len(v)} bayt>") for k, v in girdi.items()}, ensure_ascii=False)[:180]
        rel = str(Path(r["dosya"]).relative_to(ROOT)) if ROOT in Path(r["dosya"]).parents else Path(r["dosya"]).name
        if not kat_yerel(sid):
            if proje:
                ortak.gunluk(proje, sid, yetenek, ozet, rel, f"model={r.get('model')} tahmin={t}")
            else:
                ortak.arsiv_gunluk(sid, yetenek, ozet, f"model={r.get('model')} tahmin={t}")
        denenen.append({"saglayici": sid, "durum": "tamam"})
        return {**r, "saglayici": sid, "maliyet": t, "uyari": uyari, "denenen": denenen}
    raise (son_hata if isinstance(son_hata, (ortak.AgHatasi, ortak.IzinHatasi)) else ortak.IzinHatasi(
        f"'{yetenek}' için kullanılabilir sağlayıcı yok: " + "; ".join(f"{d['saglayici']}: {d['neden']}" for d in denenen)))


def kat_yerel(sid: str) -> bool:
    return bool(ortak.katalog()["saglayicilar"].get(sid, {}).get("yerel"))


def liste() -> dict:
    out = {}
    for y, ad in YETENEKLER.items():
        out[y] = {"ad": ad, "saglayicilar": [{"id": s, "hazir": hazir(s, y, None, True)[0], "neden": hazir(s, y, None, True)[1]} for s in adaylar(y)]}
    return out


# ------------------------------------------------------------------ komut satırı
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="k", required=True)
    sp.add_parser("liste")
    sp.add_parser("butce")
    c = sp.add_parser("cagir")
    c.add_argument("--yetenek", required=True)
    c.add_argument("--girdi", default="{}")
    c.add_argument("--cikti", required=True)
    c.add_argument("--saglayici")
    c.add_argument("--proje")
    c.add_argument("--onay", action="store_true")
    a = ap.parse_args()
    try:
        if a.k == "liste":
            for y, d in liste().items():
                print(f"{y:15} {d['ad']}")
                for s in d["saglayicilar"]:
                    print(f"   {'hazır ' if s['hazir'] else 'YOK   '} {s['id']}  {s['neden']}")
        elif a.k == "butce":
            b = butce_ayari()
            print(json.dumps({"bugun_harcama": bugun_harcama(), **b}, ensure_ascii=False))
        else:
            r = cagir(a.yetenek, json.loads(a.girdi), a.cikti, a.saglayici, a.proje, a.onay)
            print(json.dumps(r, ensure_ascii=False))
    except (GirdiHatasi, ValueError) as e:
        print("GİRDİ:", e)
        return 2
    except ortak.IzinHatasi as e:
        print("İZİN/AYAR:", e)
        return 3
    except ortak.AgHatasi as e:
        print("AĞ/SERVİS:", ortak.maskele(str(e)))
        return 4
    except ButceHatasi as e:
        print("BÜTÇE:", e)
        return 7
    return 0


if __name__ == "__main__":
    sys.exit(main())
