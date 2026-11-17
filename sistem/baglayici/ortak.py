"""Bağlayıcıların ortak parçaları: anahtar deposu, politika denetimi, HTTP, çağrı günlüğü.

Güvenlik ilkeleri (kullanıcının "ücretli servisler isteğe bağlı olsun" kararı; varsayılan yine tamamen yerel):
  - Anahtar YALNIZCA sistem/ortam/baglayici/anahtar.json'da (git'e girmez) ya da ortam değişkeninde durur; çıktıya/günlüğe/panele geri yazılmaz.
  - Bulut çağrısı için üç şey birlikte gerekir: bağlayıcı ETKİN + anahtar VAR + projede BULUT İZNİ (projeler/<ad>/ayar.json izin.bulut).
  - Her çağrı projeler/<ad>/bulut_gunlugu.md'ye işlenir (ne gitti, nereye); anahtar/uzun metin kırpılır.
  - Yalnızca https (yerel test için 127.0.0.1/localhost http serbest). Kaynak fotoğraflar, ayar açık değilse buluta gönderilmez.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KATALOG = ROOT / "sistem" / "baglayici" / "katalog.json"
ORTAM_B = ROOT / "sistem" / "ortam" / "baglayici"
ANAHTAR_DOSYA = ORTAM_B / "anahtar.json"
UA = "YSTCoreStudio-baglayici/1.0 (local tool)"
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,60}$")
SIR_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{10,}|AIza[0-9A-Za-z_\-]{10,}|xi-[A-Za-z0-9]{10,}|[A-Za-z0-9_\-]{32,})")


class IzinHatasi(Exception):
    pass


class AgHatasi(Exception):
    pass


def ayar_modul():
    spec = importlib.util.spec_from_file_location("yst_ayar", ROOT / "sistem" / "ayar" / "ayar.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ESKI_AD = {"ses": "tts", "gorsel": "gorsel-uret"}  # eski katalog tür adı → yetenek adı


def yapar(kat: dict, tur: str) -> bool:
    """Sağlayıcı bu türü/yeteneği yapar mı (eski ve yeni adlandırma)?"""
    t = set(kat.get("tur", []))
    return tur in t or ESKI_AD.get(tur) in t or any(ESKI_AD.get(x) == tur for x in t)


def katalog() -> dict:
    """Yerleşik sağlayıcılar + kullanıcının tanımladığı sağlayıcılar (kullanici.json → saglayicilar). Kullanıcı tanımlıların 'ozel': True işareti vardır."""
    k = json.loads(KATALOG.read_text(encoding="utf-8"))
    try:
        ozel = ayar_modul().coz().get("saglayicilar") or {}
    except Exception:  # noqa: BLE001
        ozel = {}
    for sid, m in ozel.items():
        if sid in k["saglayicilar"] or not isinstance(m, dict):
            continue
        mock = m.get("tur") == "mock"
        k["saglayicilar"][sid] = {
            "ad": m.get("ad", sid), "tur": list(m.get("yetenekler") or []), "yerel": mock, "ucretli": (not mock) and m.get("ucretli", True), "anahtar": None if mock else m.get("anahtar_adi"),
            "taban_url": m.get("taban_url"), "gonderilen": m.get("gonderilen") or ("hiçbir yere gitmez (sahte çıktı)" if mock else "çağrıdaki alanlar (istem, görsel vb.) bu servise gider"),
            "aciklama": m.get("aciklama", "Kullanıcı tanımlı sağlayıcı."), "dogrulama": "sahte, test amaçlı" if mock else "kullanıcı tanımlı sağlayıcı",
            "ozel": True, "tip": m.get("tur"), "on_ayar": m.get("on_ayar")}
    return k


# ------------------------------------------------------------------ anahtar deposu
def _anahtarlar() -> dict:
    try:
        return json.loads(ANAHTAR_DOSYA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def anahtar_oku(env_ad: str) -> str | None:
    return os.environ.get(env_ad) or _anahtarlar().get(env_ad) or None


def anahtar_var(env_ad: str | None) -> bool:
    return bool(env_ad and anahtar_oku(env_ad))


def anahtar_yaz(env_ad: str, deger: str) -> None:
    if not ENV_RE.match(env_ad or ""):
        raise ValueError("geçersiz anahtar adı")
    deger = (deger or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-\.~+/=:]{8,600}", deger):
        raise ValueError("anahtar 8-600 karakter olmalı ve yalnızca harf, rakam ve _ - . ~ + / = : içermeli (boşluk, tırnak, & % gibi karakterler olmaz)")
    ORTAM_B.mkdir(parents=True, exist_ok=True)
    d = _anahtarlar()
    d[env_ad] = deger
    ANAHTAR_DOSYA.write_text(json.dumps(d, indent=1), encoding="utf-8")
    try:
        os.chmod(ANAHTAR_DOSYA, 0o600)
    except OSError:
        pass


def anahtar_sil(env_ad: str) -> None:
    d = _anahtarlar()
    d.pop(env_ad, None)
    ORTAM_B.mkdir(parents=True, exist_ok=True)
    ANAHTAR_DOSYA.write_text(json.dumps(d, indent=1), encoding="utf-8")


def maskele(metin: str) -> str:
    """Günlük/hata çıktısı için olası sırları sil."""
    return SIR_RE.sub("[gizlendi]", metin or "")


# ------------------------------------------------------------------ politika
def model_sec(ayar_s: dict, tur: str) -> str | None:
    """Yetenek için seçilmiş model: baglayicilar.<id>.modeller.<yetenek> (listeden seçilen), yoksa eski tek 'model' alanı."""
    return ((ayar_s.get("modeller") or {}).get(ESKI_AD.get(tur, tur)) or (ayar_s.get("modeller") or {}).get(tur) or ayar_s.get("model")) or None


def sag_ayar(sid: str, proje: str | None) -> dict:
    return (ayar_modul().coz(proje).get("baglayicilar") or {}).get(sid, {})


def baglayici_durumu(sid: str, proje: str | None = None) -> dict:
    kat = katalog()["saglayicilar"][sid]
    a = sag_ayar(sid, proje)
    return {"id": sid, "ad": kat["ad"], "tur": kat["tur"], "yerel": kat.get("yerel", False), "ucretli": kat.get("ucretli", False),
            "etkin": bool(a.get("etkin")), "anahtar_adi": kat.get("anahtar"), "anahtar_var": anahtar_var(kat.get("anahtar")) if kat.get("anahtar") else None,
            "dogrulama": kat.get("dogrulama"), "gonderilen": kat.get("gonderilen"), "mcp": kat.get("mcp", False), "ozel": kat.get("ozel", False), "on_ayar": kat.get("on_ayar"), "tip": kat.get("tip")}


def izin_kontrol(sid: str, tur: str, proje: str | None) -> dict:
    """Bulut çağrısı yapılabilir mi? Yapılabilirse {'key','taban','model','ayar'} döndürür; değilse IzinHatasi."""
    kat = katalog()["saglayicilar"].get(sid)
    if not kat:
        raise IzinHatasi(f"bilinmeyen sağlayıcı: {sid}")
    if not yapar(kat, tur):
        raise IzinHatasi(f"{sid} '{tur}' üretmez (yapabildiği: {', '.join(kat['tur'])})")
    if kat.get("yerel"):
        return {"key": None, "taban": None, "model": None, "ayar": sag_ayar(sid, proje)}
    ay = ayar_modul()
    if not proje:
        raise IzinHatasi("bulut çağrısı için --proje gerekli (izin ve günlük projeye bağlıdır)")
    if not (ROOT / "projeler" / proje).is_dir():
        raise IzinHatasi(f"proje yok: {proje}")
    cz = ay.coz(proje)
    a = (cz.get("baglayicilar") or {}).get(sid, {})
    if not a.get("etkin"):
        raise IzinHatasi(f"'{sid}' bağlayıcısı KAPALI (panel → Ayarlar → Bağlayıcılar'dan aç)")
    key = anahtar_oku(kat["anahtar"]) if kat.get("anahtar") else None
    if kat.get("anahtar") and not key:
        raise IzinHatasi(f"'{sid}' için API anahtarı yok ({kat['anahtar']}): panel → Ayarlar → Bağlayıcılar")
    if not (cz.get("izin") or {}).get("bulut"):
        raise IzinHatasi("bu projede BULUT İZNİ verilmemiş (projeler/<ad>/ayar.json izin.bulut). İzin, panelde bulut özelliğini açıp onaylayınca yazılır.")
    taban = a.get("taban_url") or kat.get("taban_url")
    return {"key": key, "taban": taban.rstrip("/") if taban else None, "model": model_sec(a, tur), "ayar": a}


def izin_kontrol_arsiv(sid: str, tur: str) -> dict:
    """Projeye bağlı olmayan işlem (arşiv fotoğrafı iyileştirme): bağlayıcı ETKİN + anahtar VAR yeterli; işlem başına onay çağıran tarafta
    (panelde 'fotoğraflar seçtiğim servise gönderilecek' onayı) alınır ve sistem/ortam/arsiv/bulut_gunlugu.md'ye yazılır."""
    kat = katalog()["saglayicilar"].get(sid)
    if not kat or kat.get("yerel"):
        raise IzinHatasi(f"bilinmeyen ya da yerel sağlayıcı: {sid}")
    if not yapar(kat, tur):
        raise IzinHatasi(f"{sid} '{tur}' yapmaz (yapabildiği: {', '.join(kat['tur'])})")
    a = (ayar_modul().coz().get("baglayicilar") or {}).get(sid, {})
    if not a.get("etkin"):
        raise IzinHatasi(f"'{sid}' bağlayıcısı KAPALI (panel → Ayarlar → Bağlayıcılar'dan aç)")
    key = anahtar_oku(kat["anahtar"]) if kat.get("anahtar") else None
    if kat.get("anahtar") and not key:
        raise IzinHatasi(f"'{sid}' için API anahtarı yok ({kat['anahtar']}): panel → Ayarlar → Bağlayıcılar")
    taban = a.get("taban_url") or kat.get("taban_url")
    return {"key": key, "taban": taban.rstrip("/") if taban else None, "model": model_sec(a, tur), "ayar": a}


NL = chr(10)
CRLF = chr(13) + chr(10)


def izin_kontrol_genel(sid: str, yetenek: str, proje: str | None, onay: bool = False) -> dict:
    """Yetenek çağrısı için politika: yerel serbest; bulut = bağlayıcı etkin + anahtar + (proje bulut izni YA DA bu işlem için açık onay)."""
    kat = katalog()["saglayicilar"].get(sid)
    if not kat:
        raise IzinHatasi(f"bilinmeyen sağlayıcı: {sid}")
    if not yapar(kat, yetenek):
        raise IzinHatasi(f"{sid} '{yetenek}' yapmaz")
    if kat.get("yerel"):
        return {"key": None, "taban": None, "model": None, "ayar": sag_ayar(sid, proje)}
    if proje:
        return izin_kontrol(sid, yetenek, proje)
    if not onay:
        raise IzinHatasi("bu işlem verini bir bulut servisine gönderir: açık onay gerekli (proje dışında çağrıda --onay / panelde onay kutusu)")
    return izin_kontrol_arsiv(sid, yetenek)


def arsiv_gunluk(sid: str, tur: str, ozet: str, not_: str = "") -> None:
    p = ROOT / "sistem" / "ortam" / "arsiv" / "bulut_gunlugu.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(NL.join(["# Arşiv bulut çağrı günlüğü", "", "> Arşiv fotoğrafı iyileştirmede dışarı giden her çağrı burada. Anahtarlar yazılmaz.", "",
                              "| zaman | sağlayıcı | tür | ne gönderildi | not |", "|---|---|---|---|---|", ""]), encoding="utf-8")
    ozet = maskele(ozet).replace("|", "/").replace(NL, " ")[:200]
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%Y-%m-%d %H:%M:%S')} | {sid} | {tur} | {ozet} | {not_} |" + NL)


def multipart(alanlar: dict, dosyalar: dict) -> tuple[bytes, str]:
    """Standart kütüphane ile multipart/form-data. dosyalar: {alan: (ad, bayt, mime)}."""
    import uuid
    sinir = uuid.uuid4().hex
    parca = []
    for k, v in alanlar.items():
        parca.append(CRLF.join([f"--{sinir}", f'Content-Disposition: form-data; name="{k}"', "", str(v), ""]).encode("utf-8"))
    for k, (ad, bayt, mime) in dosyalar.items():
        bas_ = CRLF.join([f"--{sinir}", f'Content-Disposition: form-data; name="{k}"; filename="{ad}"', f"Content-Type: {mime}", "", ""]).encode("utf-8")
        parca.append(bas_ + bayt + CRLF.encode())
    parca.append(f"--{sinir}--".encode() + CRLF.encode())
    return b"".join(parca), f"multipart/form-data; boundary={sinir}"



def izinli_degil(sid: str, tur: str, proje: str | None) -> str | None:
    try:
        izin_kontrol(sid, tur, proje)
        return None
    except IzinHatasi as e:
        return str(e)


# ------------------------------------------------------------------ HTTP
def yerel_ag_mi(host: str | None) -> bool:
    """Döngü (localhost) ya da özel ağ adresi (10.x, 172.16-31.x, 192.168.x): Ollama/LM Studio gibi yerel sunucular için http serbest."""
    import ipaddress
    if not host:
        return False
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def _url_kontrol(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" and not (p.scheme == "http" and yerel_ag_mi(p.hostname)):
        raise AgHatasi("yalnızca https adresine bağlanılır (http yalnızca yerel/özel ağ adresleri için)")


def http(yontem: str, url: str, basliklar: dict | None = None, govde: dict | bytes | None = None, zaman: int = 180) -> tuple[bytes, dict]:
    _url_kontrol(url)
    h = {"User-Agent": UA, **(basliklar or {})}
    veri = None
    if isinstance(govde, dict):
        veri = json.dumps(govde).encode("utf-8")
        h["Content-Type"] = "application/json"
    elif isinstance(govde, bytes):
        veri = govde
    istek = urllib.request.Request(url, data=veri, headers=h, method=yontem)
    try:
        with urllib.request.urlopen(istek, timeout=zaman) as r:
            return r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        govde_s = maskele(e.read().decode("utf-8", "replace"))[:300]
        raise AgHatasi(f"HTTP {e.code}: {govde_s}") from None
    except urllib.error.URLError as e:
        raise AgHatasi(f"bağlanılamadı: {e.reason}") from None


def json_http(yontem, url, basliklar=None, govde=None, zaman=180) -> dict:
    b, _ = http(yontem, url, basliklar, govde, zaman)
    try:
        return json.loads(b.decode("utf-8"))
    except ValueError:
        raise AgHatasi("sunucu JSON dışında bir yanıt verdi") from None


def b64_coz(s: str) -> bytes:
    return base64.b64decode(s)


# ------------------------------------------------------------------ günlük
def gunluk(proje: str, sid: str, tur: str, ozet: str, cikti: str | None, not_: str = "") -> None:
    p = ROOT / "projeler" / proje / "bulut_gunlugu.md"
    if not p.exists():
        p.write_text(f"# Bulut çağrı günlüğü: {proje}\n\n> Dışarı giden her çağrı burada. Anahtarlar yazılmaz. Kaynak: sistem/baglayici/uret.py\n\n"
                     "| zaman | sağlayıcı | tür | ne gönderildi (kırpılmış) | çıktı | not |\n|---|---|---|---|---|---|\n", encoding="utf-8")
    ozet = maskele(ozet).replace("|", "/").replace("\n", " ")[:200]
    with open(p, "a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%Y-%m-%d %H:%M:%S')} | {sid} | {tur} | {ozet} | {cikti or ''} | {not_} |\n")
