#!/usr/bin/env python3
"""Ayar çözücü: varsayılan < kullanıcı (genel) < proje. Ajan başına model ve effort, üretim tercihleri, platformlar.

  python sistem/ayar/ayar.py goster [proje]                çözülmüş ayarın tamamı (JSON)
  python sistem/ayar/ayar.py ajan <ajan> [proje]           tek ajan: model, effort, bağlayıcı  (orkestratör her Agent çağrısında bunu kullanır)
  python sistem/ayar/ayar.py ajan-ayarla <ajan> --model opus --effort high [--calisma_ortami codex] [--proje <ad>]
  python sistem/ayar/ayar.py esitle                        genel ayarı .claude/agents/*.md frontmatter'ına (model:, effort:) yazar

Dosyalar: sistem/ayar/varsayilan.json (depoda) · sistem/ayar/kullanici.json (senin genel tercihin, depoda) · projeler/<ad>/ayar.json (proje).
Model: opus | sonnet | haiku | fable | inherit   Effort: low | medium | high | xhigh | max
Not: orkestratör (ana oturum) her ajanı çağırırken model ve effort'u AÇIKÇA geçirir; frontmatter yalnızca ajan doğrudan çağrıldığında (ör. saglik.py --canli) geçerlidir.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VARSAYILAN = ROOT / "sistem" / "ayar" / "varsayilan.json"
KULLANICI = ROOT / "sistem" / "ayar" / "kullanici.json"
AJANLAR = ROOT / ".claude" / "agents"
MODELLER = ("opus", "sonnet", "haiku", "fable", "inherit")
EFFORTLAR = ("low", "medium", "high", "xhigh", "max")
_KILIT = threading.Lock()
PROJE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def _oku(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _birlestir(a: dict, b: dict) -> dict:
    """b, a'nın üstüne (derin) biner. Listeler bütün olarak değişir."""
    out = copy.deepcopy(a)
    for k, v in b.items():
        if k.startswith("_"):
            continue
        if v is None:  # null = bu anahtarı kaldır (örn. eklenen bir modeli sil)
            out.pop(k, None)
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _birlestir(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def proje_dosyasi(proje: str) -> Path:
    if not PROJE_RE.match(proje or ""):
        raise ValueError("geçersiz proje adı")
    return ROOT / "projeler" / proje / "ayar.json"


def coz(proje: str | None = None) -> dict:
    a = _birlestir(_oku(VARSAYILAN), _oku(KULLANICI))
    if proje:
        a = _birlestir(a, _oku(proje_dosyasi(proje)))
    return a


def ajan(ad: str, proje: str | None = None, cz: dict | None = None, ork: str | None = None) -> dict:
    """cz (çözülmüş ayar) ve ork (orkestratör ortamı) verilirse ayar dosyaları yeniden okunmaz: döngüde (pano, ayar özeti) her ajan için
    tüm ayarı baştan çözüp derin kopyalamak proje sayısıyla doğru orantılı yavaşlıyordu."""
    a = (cz if cz is not None else coz(proje))["ajanlar"].get(ad)
    if not a:
        raise KeyError(f"ayarda böyle bir ajan yok: {ad}")
    o = etkin_ortam(a, ork)
    r = {**a, "calisma_ortami": a.get("calisma_ortami") or "", "etkin_ortam": o}
    if not model_gecerli(o, a.get("model")):
        r["model"] = ""  # kayıtlı model bu ortamın listesinde yok: ortamın varsayılanı kullanılır
    return r


def orkestrator_ortami() -> str:
    return (coz().get("orkestrator") or {}).get("calisma_ortami") or "claude-code"


_MODEL_ONBELLEK: dict = {}


def ortam_modelleri(ortam: str) -> list[dict]:
    """Bir çalışma ortamının KENDİ model listesi (elle yazılmaz, ortamdan okunur): Claude Code sabit takma adlar; Codex kendi önbelleğinden
    (~/.codex/models_cache.json); OpenCode `opencode models`; Gemini CLI model listesi vermez (boş = ortamın varsayılanı).
    Liste 60 sn önbelleğe alınır: OpenCode için her çağrıda komut çalıştırmak (pano her 4 sn'de ajan başına soruyordu) işlemciyi gereksiz yoruyordu."""
    if ortam == "claude-code":
        return [{"id": m, "ad": m} for m in MODELLER]
    e = _MODEL_ONBELLEK.get(ortam)
    if e and time.time() - e[0] < 60:
        return e[1]
    v = _ortam_modelleri_oku(ortam)
    _MODEL_ONBELLEK[ortam] = (time.time(), v)
    return v


def _ortam_modelleri_oku(ortam: str) -> list[dict]:
    if ortam in ("ollama", "lmstudio", "llamacpp"):
        sys.path.insert(0, str(ROOT / "sistem/araclar"))
        import orkestrator
        try:
            return orkestrator.models(ortam)
        except (OSError, ValueError):
            return []
    if ortam == "codex":
        try:
            d = json.loads((Path.home() / ".codex" / "models_cache.json").read_text(encoding="utf-8"))
            return [{"id": m["slug"], "ad": m.get("display_name") or m["slug"]} for m in d.get("models", []) if m.get("visibility") == "list" and m.get("slug")]
        except (OSError, ValueError, KeyError):
            return []
    if ortam == "opencode":
        import shutil
        import subprocess
        exe = shutil.which("opencode")
        if not exe:
            return []
        try:
            r = subprocess.run([exe, "models"], capture_output=True, text=True, timeout=20)
            return [{"id": ln.strip(), "ad": ln.strip()} for ln in (r.stdout or "").splitlines() if re.fullmatch(r"[A-Za-z0-9_.:/\-]{1,80}", ln.strip())]
        except (OSError, subprocess.SubprocessError):
            return []
    return []


def etkin_ortam(a: dict, ork: str | None = None) -> str:
    return a.get("calisma_ortami") or ork or orkestrator_ortami()


def model_gecerli(ortam: str, model) -> bool:
    if ortam == "claude-code":
        return model in MODELLER
    return model in ("", None) or model in {m["id"] for m in ortam_modelleri(ortam)}


def calisma_ortamlari() -> list[str]:
    d = _oku(ROOT / "sistem" / "baglayici" / "calisma_ortamlari.json")
    return [k for k in d if not k.startswith("_")]


def dogrula_ajan(model: str | None, effort: str | None) -> None:
    if model is not None and model not in MODELLER:
        raise ValueError(f"geçersiz model '{model}' (geçerli: {', '.join(MODELLER)})")
    if effort is not None and effort not in EFFORTLAR:
        raise ValueError(f"geçersiz effort '{effort}' (geçerli: {', '.join(EFFORTLAR)})")


MOTORLAR = ("realesrgan", "klasik", "bulut")
MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def _dogrula_isler(isler) -> None:
    """isler.<is>.modeller.<id> = {ad, motor, saglayici, model, etkin, not}; varsayılan var olan bir modele işaret etmeli."""
    if isler is None:
        return
    if not isinstance(isler, dict):
        raise ValueError("'isler' bir nesne olmalı")
    katalog = _oku(ROOT / "sistem" / "baglayici" / "katalog.json").get("saglayicilar", {})
    for is_ad, v in isler.items():
        if is_ad.startswith("_"):
            continue
        if is_ad not in (coz().get("isler") or {}):
            raise ValueError(f"bilinmeyen iş: {is_ad}")
        if not isinstance(v, dict):
            raise ValueError("iş bir nesne olmalı")
        for mid, m in (v.get("modeller") or {}).items():
            if not MODEL_ID_RE.match(mid):
                raise ValueError(f"model kimliği küçük harf/rakam/tire olmalı: {mid}")
            if m is None:
                continue
            if not isinstance(m, dict):
                raise ValueError("model bir nesne olmalı")
            if "motor" in m and m["motor"] not in MOTORLAR:
                raise ValueError(f"motor {MOTORLAR} olmalı")
            if "saglayici" in m and m["saglayici"] != "yerel" and m["saglayici"] not in katalog:
                raise ValueError(f"bilinmeyen sağlayıcı: {m['saglayici']}")
            for alan, uz in (("ad", 100), ("model", 100), ("not", 300)):
                if alan in m and not (isinstance(m[alan], str) and len(m[alan]) <= uz):
                    raise ValueError(f"'{alan}' en çok {uz} karakterlik metin olmalı")
        if "varsayilan" in v:
            birlesik = _birlestir(_oku(KULLANICI), {"isler": {is_ad: v}})
            tum = _birlestir(_oku(VARSAYILAN), birlesik)["isler"][is_ad]["modeller"]
            if v["varsayilan"] not in tum:
                raise ValueError("varsayılan model tanımlı olmalı")


def _budama(d: dict, ust: bool = True) -> dict:
    """Boş kalan iç nesneleri temizle (örn. son kullanıcı modeli silinince geriye boş 'isler' iskeleti kalmasın). Üst düzey 'ajanlar' korunur."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = _budama(v, False)
            if not v and not (ust and k == "ajanlar"):
                continue
        out[k] = v
    return out


YETENEK_ADLARI = {"gorsel-uret", "gorsel-duzenle", "gorsel-buyut", "video-uret", "avatar-video", "tts", "ses-klon", "stt", "muzik", "ses", "gorsel"}
SAGLAYICI_TURLERI = ("http-is", "openai-uyumlu", "mock", "baglanti")
ON_AYAR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
ORKESTRATORLER = ("claude-code", "codex", "gemini-cli", "opencode", "ollama", "lmstudio", "llamacpp")
YERLESIK_SAGLAYICILAR = {"ema", "elevenlabs", "gemini", "openai-gorsel", "heygen"}
ANAHTAR_AD_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,60}$")
BASLIK_RE = re.compile(r"^[A-Za-z0-9-]{1,40}$")


def _url_ok(u) -> bool:
    """https her yerde; http yalnızca localhost / özel ağ adresi (Ollama, LM Studio gibi yerel sunucular)."""
    import ipaddress
    import urllib.parse as up
    if not isinstance(u, str) or re.search(r"\s", u):
        return False
    p = up.urlparse(u)
    if not p.hostname:
        return False
    if p.scheme == "https":
        return True
    if p.scheme != "http":
        return False
    h = p.hostname
    if h == "localhost" or h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def dogrula_manifest(sid: str, m) -> None:
    """Kullanıcı tanımlı sağlayıcı manifesti: yalnızca yapı denetimi (kod çalıştırılmaz). ValueError."""
    if not re.match(r"^[a-z0-9][a-z0-9-]{0,40}$", sid or ""):
        raise ValueError(f"sağlayıcı kimliği küçük harf/rakam/tire olmalı: {sid!r}")
    if sid in YERLESIK_SAGLAYICILAR:
        raise ValueError(f"'{sid}' yerleşik bir sağlayıcının adı: başka bir kimlik seç")
    if not isinstance(m, dict):
        raise ValueError("manifest bir nesne olmalı")
    if len(json.dumps(m, ensure_ascii=False)) > 20000:
        raise ValueError("manifest çok büyük (en çok 20 KB)")
    if m.get("tur") not in SAGLAYICI_TURLERI:
        raise ValueError(f"tur {SAGLAYICI_TURLERI} olmalı")
    if not isinstance(m.get("ad"), str) or not 1 <= len(m["ad"]) <= 80:
        raise ValueError("ad (1-80 karakter) gerekli")
    y = m.get("yetenekler")
    bos_ok = m["tur"] == "baglanti"  # yalnızca model kaynağı (Anthropic, Ollama, LM Studio…): medya yeteneği olmayabilir
    if not isinstance(y, list) or (not y and not bos_ok) or not all(isinstance(x, str) and x in YETENEK_ADLARI for x in y):
        raise ValueError(f"yetenekler listesi gerekli; geçerli adlar: {sorted(YETENEK_ADLARI)}")
    if m.get("on_ayar") is not None and not ON_AYAR_RE.match(str(m["on_ayar"])):
        raise ValueError("on_ayar geçersiz")
    if m["tur"] == "mock":
        return
    if not _url_ok(m.get("taban_url")):
        raise ValueError("taban_url https:// ile başlamalı (http yalnızca localhost / yerel ağ adresleri için)")
    if m.get("anahtar_adi") is not None and not ANAHTAR_AD_RE.match(m.get("anahtar_adi") or ""):
        raise ValueError("anahtar_adi BÜYÜK_HARF_ve_alt_çizgi olmalı (örn. BENIM_SERVIS_KEY); anahtarın kendisi manifestte durmaz, panelden girilir")
    if m.get("anahtar_adi") is None and m["tur"] != "baglanti":
        raise ValueError("anahtar_adi gerekli")
    for ad, v in (m.get("basliklar") or {}).items():
        if not BASLIK_RE.match(ad) or not isinstance(v, str) or "\n" in v or "\r" in v:
            raise ValueError(f"geçersiz başlık: {ad!r}")
    k = m.get("kimlik")
    if k is not None and (not isinstance(k, dict) or not BASLIK_RE.match(k.get("baslik", "")) or "\n" in str(k.get("sablon", "")) or "\r" in str(k.get("sablon", ""))):
        raise ValueError("kimlik: {baslik, sablon} geçerli olmalı (örn. Authorization / 'Key {anahtar}')")
    if m["tur"] == "http-is":
        uc = m.get("uc")
        if not isinstance(uc, dict) or not uc:
            raise ValueError("http-is için 'uc' (yetenek → gonder/durum/cikti) gerekli")
        for yet, tanim in uc.items():
            if yet not in YETENEK_ADLARI or yet not in y:
                raise ValueError(f"uc.{yet}: yetenekler listesinde olmayan yetenek")
            g = (tanim or {}).get("gonder") or {}
            if not isinstance(g.get("yol"), str) or not g["yol"].startswith("/"):
                raise ValueError(f"uc.{yet}.gonder.yol '/' ile başlamalı (adres = taban_url + yol)")
            if g.get("yontem", "POST").upper() not in ("GET", "POST", "PUT"):
                raise ValueError("yontem GET/POST/PUT olmalı")
            d = tanim.get("durum")
            if d is not None and (not isinstance(d.get("yol"), str) or not d["yol"].startswith("/")):
                raise ValueError(f"uc.{yet}.durum.yol '/' ile başlamalı")
    for yet, c in (m.get("maliyet") or {}).items():
        if not isinstance(c, dict) or not any(isinstance(c.get(a), (int, float)) for a in ("sabit", "fiyat")):
            raise ValueError(f"maliyet.{yet}: {{sabit: sayı}} ya da {{birim_alani, fiyat: sayı}} olmalı")


def _dogrula_saglayicilar(sag) -> None:
    if sag is None:
        return
    if not isinstance(sag, dict):
        raise ValueError("'saglayicilar' bir nesne olmalı")
    for sid, m in sag.items():
        if m is not None:  # null = sil
            dogrula_manifest(sid, m)


def _dogrula_orkestrator(yama: dict) -> None:
    o = yama.get("orkestrator")
    if o is None:
        return
    if not isinstance(o, dict) or o.get("calisma_ortami", "claude-code") not in ORKESTRATORLER:
        raise ValueError(f"orkestrator.calisma_ortami {ORKESTRATORLER} olmalı")
    if "model" in o and (not isinstance(o["model"], str) or len(o["model"]) > 200):
        raise ValueError("Geçersiz orkestratör modeli")
    if "yerel_adresler" in o:
        sys.path.insert(0, str(ROOT / "sistem/araclar"))
        import orkestrator
        if not isinstance(o["yerel_adresler"], dict):
            raise ValueError("Yerel adresler nesne olmalı")
        for kind in o["yerel_adresler"]:
            if kind not in orkestrator.LOCAL:
                raise ValueError("Bilinmeyen yerel ortam")
            orkestrator.endpoint(kind, o)
    _MODEL_ONBELLEK.clear()


def _dogrula_yetenekler_butce(yama: dict) -> None:
    _dogrula_orkestrator(yama)
    y = yama.get("yetenekler")
    if y is not None:
        if not isinstance(y, dict):
            raise ValueError("'yetenekler' bir nesne olmalı")
        for ad, v in y.items():
            if ad not in YETENEK_ADLARI or not isinstance(v, dict):
                raise ValueError(f"bilinmeyen yetenek ya da biçim: {ad}")
            sira = v.get("sira", [])
            if not isinstance(sira, list) or not all(isinstance(x, str) and re.match(r"^[a-z0-9][a-z0-9-]{0,40}$", x) for x in sira):
                raise ValueError("sira: sağlayıcı kimliklerinin listesi olmalı")
    b = yama.get("butce")
    if b is not None:
        if not isinstance(b, dict):
            raise ValueError("'butce' bir nesne olmalı")
        if "mod" in b and b["mod"] not in ("observe", "warn", "cap"):
            raise ValueError("butce.mod observe | warn | cap olmalı")
        for a in ("gun_tavan", "onay_esigi"):
            if a in b and not (isinstance(b[a], (int, float)) and b[a] >= 0):
                raise ValueError(f"butce.{a} sıfır ya da pozitif sayı olmalı")


def kaydet(yama: dict, proje: str | None = None) -> dict:
    """yama'yı kullanıcı (genel) ya da proje ayar dosyasına derin birleştirerek yazar. Geçersiz model/effort reddedilir."""
    for ad, v in (yama.get("ajanlar") or {}).items():
        if ad not in coz()["ajanlar"]:
            raise ValueError(f"bilinmeyen ajan: {ad}")
        if v.get("calisma_ortami") not in (None, "") and v["calisma_ortami"] not in calisma_ortamlari():
            raise ValueError(f"geçersiz çalışma ortamı '{v['calisma_ortami']}' (geçerli: {', '.join(calisma_ortamlari())})")
        ort = v.get("calisma_ortami") or (yama.get("orkestrator") or {}).get("calisma_ortami") or orkestrator_ortami()
        if "model" in v and ort == "claude-code":
            dogrula_ajan(v.get("model"), None)
        elif "model" in v and not model_gecerli(ort, v["model"]):
            raise ValueError(f"'{v['model']}' modeli {ort} ortamının listesinde yok (liste ortamdan okunur; boş = ortamın varsayılanı)")
        dogrula_ajan(None, v.get("effort"))
    _dogrula_isler(yama.get("isler"))
    _dogrula_saglayicilar(yama.get("saglayicilar"))
    _dogrula_yetenekler_butce(yama)
    for k in ("uretim", "platformlar", "kurallar"):
        if k in yama and not isinstance(yama[k], dict):
            raise ValueError(f"'{k}' bir nesne olmalı")
    with _KILIT:  # eşzamanlı iki kayıt birbirinin üstüne yazmasın (panel çok iş parçacıklı)
        return _kaydet_kilitli(yama, proje)


def _kaydet_kilitli(yama: dict, proje: str | None) -> dict:
    p = proje_dosyasi(proje) if proje else KULLANICI
    if proje and not p.parent.is_dir():
        raise ValueError("proje yok")
    mevcut = _oku(p)
    for sid in (yama.get("saglayicilar") or {}):  # manifest bütün olarak değişir (derin birleştirme eski alt alanları bırakmasın)
        (mevcut.get("saglayicilar") or {}).pop(sid, None)
    yeni = _budama(_birlestir(mevcut, yama))
    p.write_text(json.dumps(yeni, ensure_ascii=False, indent=2), encoding="utf-8")
    return yeni


def esitle() -> list[str]:
    """Genel çözülmüş ayardaki model/effort'u ajan dosyalarının frontmatter'ına yazar. Değişen dosyaları döndürür."""
    degisen = []
    for ad, a in coz()["ajanlar"].items():
        f = AJANLAR / f"{ad}.md"
        if not f.exists():
            continue
        t = f.read_text(encoding="utf-8")
        m = re.match(r"^(---\r?\n)(.*?)(\r?\n---\r?\n)(.*)$", t, re.S)
        if not m:
            continue
        nl = "\r\n" if "\r\n" in t else "\n"
        satirlar = m.group(2).splitlines()
        for anahtar, deger in (("model", a["model"] if a["model"] in MODELLER else None), ("effort", a["effort"])):
            if deger is None:
                continue
            yeni = f"{anahtar}: {deger}"
            idx = next((i for i, s in enumerate(satirlar) if s.startswith(anahtar + ":")), None)
            if idx is None:
                satirlar.append(yeni)
            else:
                satirlar[idx] = yeni
        yeni_t = m.group(1) + nl.join(satirlar) + m.group(3) + m.group(4)
        if yeni_t != t:
            f.write_text(yeni_t, encoding="utf-8", newline="")
            degisen.append(f.name)
    return degisen


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    k = a[0]
    try:
        if k == "goster":
            print(json.dumps(coz(a[1] if len(a) > 1 else None), ensure_ascii=False, indent=2))
        elif k == "ajan":
            print(json.dumps(ajan(a[1], a[2] if len(a) > 2 else None), ensure_ascii=False))
        elif k == "ajan-ayarla":
            ad = a[1]
            kw = {a[i].lstrip("-"): a[i + 1] for i in range(2, len(a) - 1, 2)}
            kaydet({"ajanlar": {ad: {x: kw[x] for x in ("model", "effort", "calisma_ortami") if x in kw}}}, kw.get("proje"))
            print("kaydedildi:", json.dumps(ajan(ad, kw.get("proje")), ensure_ascii=False))
        elif k == "esitle":
            d = esitle()
            print("güncellenen ajan dosyaları:", ", ".join(d) or "yok (zaten eşit)")
        else:
            print(__doc__)
            return 2
    except (ValueError, KeyError) as e:
        print("HATA:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
