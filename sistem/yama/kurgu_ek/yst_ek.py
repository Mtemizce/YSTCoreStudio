"""YSTCore eklentisi (Kurgu'nun içinde çalışır): görsel kütüphanesi, seslendirme ve kalemle ara sahne.

Bu dosya Kurgu'ya kurulumda `sistem/kurulum/kurgu_yama.py` ile eklenir (Kurgu'nun kendi deposundan çekilir, sonra bu eklenti uygulanır).
Kurgu stüdyonun içinde (`<stüdyo>/kurgu/`) çalışıyorsa stüdyonun araçlarını doğrudan kullanır; değilse eklenti pasif kalır.
Rotalar `/api/yst/*` altındadır, Kurgu'nun kendi güvenlik denetimlerinden (aynı kaynak, yerel adres) geçer. Üretilen dosyalar projenin
`media/` klasörüne yazılır; arayüz (`web/js/yst.js`) onları Kurgu'nun kendi `addMedia` işleviyle zaman çizelgesine koyar.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from urllib.parse import quote

KURGU = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(KURGU)                                   # stüdyo kökü (Kurgu <stüdyo>/kurgu/ içindeyse)
STUDYO = os.path.isdir(os.path.join(KOK, "sistem", "araclar")) and os.path.isfile(os.path.join(KOK, "sistem", "araclar", "gorsel_kutuphane.py"))
_MOD = {}
_KILIT = threading.Lock()
ISLER = {}                                                     # iş kimliği -> durum (seslendirme ve ara sahne)
EN_COK_ES_ZAMANLI = 1


class Hata(Exception):
    """Kullanıcıya gösterilecek anlaşılır hata (HTTP 400)."""


def _modul(ad, rel):
    if ad not in _MOD:
        yol = os.path.join(KOK, *rel.split("/"))
        sp = importlib.util.spec_from_file_location(ad, yol)
        m = importlib.util.module_from_spec(sp)
        sys.modules[ad] = m
        sp.loader.exec_module(m)
        _MOD[ad] = m
    return _MOD[ad]


def _gorsel():
    return _modul("yst_gorsel_kutuphane", "sistem/araclar/gorsel_kutuphane.py")


def _kalem():
    p = os.path.join(KOK, "sistem", "araclar")
    if p not in sys.path:
        sys.path.insert(0, p)
    return _modul("yst_kalem_cizim_ek", "sistem/araclar/kalem_cizim.py")


def _tts():
    """Stüdyonun seslendirme adaptörleri (EMA Lightning, Pocket TTS Turkish). Kurgu'nun kendi tts.py'siyle karışmasın diye ayrı paket adıyla yüklenir."""
    if "yst_tts" not in sys.modules:
        yol = os.path.join(KOK, "sistem", "tts")
        sp = importlib.util.spec_from_file_location("yst_tts", os.path.join(yol, "__init__.py"), submodule_search_locations=[yol])
        m = importlib.util.module_from_spec(sp)
        sys.modules["yst_tts"] = m
        sp.loader.exec_module(m)
    return sys.modules["yst_tts"]


# ------------------------------------------------------------------ iş yöneticisi
def _is_baslat(tur, fn):
    with _KILIT:
        if sum(1 for i in ISLER.values() if i["durum"] == "calisiyor") >= EN_COK_ES_ZAMANLI:
            raise Hata("başka bir ses ya da ara sahne üretiliyor, bitmesini bekle")
        iid = "i" + os.urandom(4).hex()
        ISLER[iid] = {"id": iid, "tur": tur, "durum": "calisiyor", "mesaj": "başladı", "sonuc": None, "hata": None, "bas": time.time()}
        for eski in [k for k, v in ISLER.items() if v["durum"] != "calisiyor" and time.time() - v["bas"] > 3600]:
            del ISLER[eski]

    def kos():
        try:
            ISLER[iid]["sonuc"] = fn(lambda m: ISLER[iid].update(mesaj=m))
            ISLER[iid].update(durum="bitti", mesaj="bitti")
        except Exception as e:  # noqa: BLE001  (arka plan işi: hata arayüze iletilir)
            ISLER[iid].update(durum="hata", hata=str(e)[:400], mesaj="hata")

    threading.Thread(target=kos, daemon=True, name="yst-" + tur).start()
    return {"id": iid}


def _rel(app_dir, yol):
    return os.path.relpath(yol, app_dir).replace(os.sep, "/")


def _slug(s, n=28):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", str(s).translate(tr).lower()).strip("-")[:n] or "ses"


# ------------------------------------------------------------------ durum
def durum():
    d = {"studyo": STUDYO, "gorsel": {"kurulu": False}, "ses": {"motorlar": []}, "kalem": {"hazir": False}}
    if not STUDYO:
        return d
    try:
        g = _gorsel()
        d["gorsel"] = {"kurulu": bool(g.kurulu_mu()), "stiller": g.STILLER, "boyutlar": {a: list(v) for a, v in g.BOYUTLAR.items()}, "adet_en_cok": g.EN_COK_ADET, "is": g.is_durum()}
    except Exception as e:  # noqa: BLE001
        d["gorsel"]["hata"] = str(e)[:200]
    try:
        for ad, m in _tts().motorlar().items():
            d["ses"]["motorlar"].append({"id": ad, "aciklama": m.aciklama, "hazir": m.hazir_mi() is None, "neden": m.hazir_mi() or "", "desteklenen": m.desteklenen,
                                         "sesler": list(m.ses_listesi), "ucretli": bool(m.ucretli)})
        d["ses"]["klon_ornegi"] = os.path.isfile(os.path.join(KOK, "kimlik", "ses", "ornek.wav"))
    except Exception as e:  # noqa: BLE001
        d["ses"]["hata"] = str(e)[:200]
    try:
        k = _kalem()
        d["kalem"] = {"hazir": bool(shutil.which("ffmpeg")), "stiller": [{"id": a, "ad": v["ad"], "aciklama": v["aciklama"]} for a, v in k.STILLER.items()]}
    except Exception as e:  # noqa: BLE001
        d["kalem"]["hata"] = str(e)[:200]
    return d


# ------------------------------------------------------------------ seslendirme
def ses_uret(proje_dir, metin, motor="ema", hiz=1.0, ses=None, duygu=None, klon=False, tohum=None, ilerle=lambda m: None):
    """Metni yerel motorla seslendirir; WAV <proje>/media/tts/ altına yazılır. Aynı metin + ayar aynı dosyayı verir (önbellek). {path, sure}"""
    metin = str(metin or "").strip()
    if not 2 <= len(metin) <= 3000:
        raise Hata("metin 2-3000 karakter olmalı")
    hiz = max(0.5, min(2.0, float(hiz or 1.0)))
    m = _tts().motorlar().get(motor)
    if m is None:
        raise Hata(f"bilinmeyen seslendirme motoru: {motor}")
    neden = m.hazir_mi()
    if neden:
        raise Hata(f"{motor} kullanılamıyor: {neden}")
    plan = {}
    if klon:
        ornek = os.path.join(KOK, "kimlik", "ses", "ornek.wav")
        if not m.desteklenen.get("klon") or not os.path.isfile(ornek):
            raise Hata("ses klonlama için panelde bir örnek ses kaydetmelisin (Yeni proje → Sesimi klonla) ve Pocket TTS seçmelisin")
        plan["klon"] = ornek
    elif ses and m.desteklenen.get("ses"):
        plan["ses"] = str(ses)
    if duygu and m.desteklenen.get("duygu"):
        plan["duygu"] = str(duygu)
    anahtar = hashlib.sha1(json.dumps([metin, motor, hiz, plan, tohum], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    hedef_dir = os.path.join(proje_dir, "media", "tts")
    os.makedirs(hedef_dir, exist_ok=True)
    hedef = os.path.join(hedef_dir, f"{_slug(metin)}-{anahtar}.wav")
    if not os.path.isfile(hedef):
        ilerle("seslendiriliyor…")
        tohum = int(tohum) if str(tohum or "").strip() else int(anahtar, 16) % 100000
        with tempfile.TemporaryDirectory(prefix="yst-ses-") as td:
            sonuc = m.uret([("vo", {"metin": metin, "hiz": hiz, "seed": tohum})], plan, td, 48000)
            shutil.copy2(sonuc["vo"], hedef)
        if getattr(m, "atif_gerekir", False):
            with open(os.path.join(hedef_dir, "ATIF.txt"), "a", encoding="utf-8") as f:
                f.write(getattr(m, "atif", "") + "\n")
    with wave.open(hedef) as w:
        sure = w.getnframes() / float(w.getframerate())
    return {"path": _rel(proje_dir, hedef), "sure": round(sure, 2), "motor": motor}


# ------------------------------------------------------------------ kalemle ara sahne
def kalem_uret(proje_dir, kaynak_yol, stil="karakalem", zemin="", gecis=False, bekle=2.0, sure=8.0, kalem_sesi=True, ilerle=lambda m: None):
    """Bir resmi, videonun ilk karesini ya da (resim verilirse) görseli kalemle çizilen bir videoya çevirir; <proje>/media/ara-sahne/ altına yazılır. {path, sure}"""
    k = _kalem()
    if stil not in k.STILLER:
        raise Hata("bilinmeyen stil")
    k.zemin_rgb(zemin or None)
    sure = max(4.0, min(30.0, float(sure or 8)))
    bekle = max(0.5, min(10.0, float(bekle or 2)))
    uz = os.path.splitext(kaynak_yol)[1].lower()
    video = uz in k.VIDEO_UZ
    if not video and uz not in k.RESIM_UZ and uz not in (".svg", ".dwg"):
        raise Hata("kaynak resim, video, SVG ya da DWG olmalı")
    hedef_dir = os.path.join(proje_dir, "media", "ara-sahne")
    os.makedirs(hedef_dir, exist_ok=True)
    ad = f"{_slug(os.path.splitext(os.path.basename(kaynak_yol))[0])}-{stil}" + ("-gercege" if gecis and not video else ("-giris" if video else ""))
    hedef, n = os.path.join(hedef_dir, ad + ".mp4"), 2
    while os.path.exists(hedef):
        hedef = os.path.join(hedef_dir, f"{ad}-{n}.mp4")
        n += 1
    komut = [sys.executable, os.path.join(KOK, "sistem", "araclar", "kalem_cizim.py"), kaynak_yol, "-o", hedef, "--stil", stil, "--sure", str(sure)]
    if gecis and not video:
        komut += ["--gecis", "--bekle", str(bekle)]
    elif video:
        komut += ["--bekle", str(bekle)]
    if zemin:
        komut += ["--zemin", zemin]
    if not kalem_sesi:
        komut += ["--sessiz"]
    ilerle("çiziliyor ve videoya kodlanıyor… (genelde 30-120 sn)")
    r = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, env={**os.environ, "PYTHONUTF8": "1"},
                       creationflags=0x08000000 if os.name == "nt" else 0)
    if r.returncode != 0 or not os.path.isfile(hedef):
        raise Hata("ara sahne üretilemedi: " + ((r.stderr or r.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1].replace("HATA:", "").strip()[:250])
    try:
        sonuc = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        sonuc = {}
    return {"path": _rel(proje_dir, hedef), "stil": stil, "kare": sonuc.get("kare")}


# ------------------------------------------------------------------ HTTP
def _gorsel_eylem(h, method, yol, q):
    g = _gorsel()
    app = h.app
    if yol == "/api/yst/gorsel/liste" and method == "GET":
        return h.reply(200, {"ogeler": g.liste(q.get("durum") or None, q.get("seri") or None)})
    if yol == "/api/yst/gorsel/is" and method == "GET":
        return h.reply(200, g.is_durum())
    if yol == "/api/yst/gorsel/dosya" and method == "GET":
        p = g.yol(q.get("id", ""))
        if q.get("k"):
            from PIL import Image
            import io
            im = Image.open(p).convert("RGB")
            im.thumbnail((420, 420))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=80)
            return h.reply(200, b.getvalue(), "image/jpeg", cache="max-age=300")
        with open(p, "rb") as f:
            return h.reply(200, f.read(), "image/png", cache="max-age=300")
    if method != "POST":
        raise Hata("yöntem desteklenmiyor")
    b = h.read_json()
    gid = str(b.get("id") or "")
    if yol == "/api/yst/gorsel/uret":
        boyut = g.BOYUTLAR.get(str(b.get("boyut") or ""))
        gen, yuk = boyut if boyut else (1024, 576)
        return h.reply(200, g.is_baslat(str(b.get("istem") or ""), str(b.get("stil") or "") or None, gen, yuk, int(b.get("adet") or 1),
                                        int(b["tohum"]) if str(b.get("tohum") or "").strip() else None))
    if yol == "/api/yst/gorsel/yeniden":
        return h.reply(200, g.yeniden(gid))
    if yol == "/api/yst/gorsel/onayla":
        return h.reply(200, {"ok": True, "oge": g.onayla(gid)})
    if yol == "/api/yst/gorsel/reddet":
        return h.reply(200, {"ok": True, "oge": g.reddet(gid)})
    if yol == "/api/yst/gorsel/ekle":      # görseli projenin media/foto klasörüne kopyalar (zaman çizelgesine eklemeyi arayüz yapar)
        src = g.yol(gid)
        hedef_dir = os.path.join(app.dir, "media", "foto")
        os.makedirs(hedef_dir, exist_ok=True)
        hedef = os.path.join(hedef_dir, f"uretilen-{gid}.png")
        if not os.path.isfile(hedef):
            shutil.copy2(src, hedef)
        return h.reply(200, {"ok": True, "path": _rel(app.dir, hedef)})
    raise Hata("bilinmeyen görsel işlemi")


def api(h, method, yol, q):
    """Kurgu'nun `api()` yönlendiricisinden çağrılır. h: istek işleyicisi (reply/read_json/app)."""
    try:
        if yol == "/api/yst/durum" and method == "GET":
            return h.reply(200, durum())
        if not STUDYO:
            raise Hata("bu Kurgu stüdyonun içinde çalışmıyor: YSTCore eklentisi pasif")
        if yol.startswith("/api/yst/gorsel/"):
            return _gorsel_eylem(h, method, yol, q)
        if yol == "/api/yst/is" and method == "GET":
            i = ISLER.get(q.get("id", ""))
            if not i:
                return h.reply(404, {"error": "iş yok"})
            return h.reply(200, i)
        if yol == "/api/yst/ses/uret" and method == "POST":
            b = h.read_json()
            app_dir = h.app.dir
            return h.reply(200, _is_baslat("ses", lambda ilerle: ses_uret(app_dir, b.get("metin"), str(b.get("motor") or "ema"), b.get("hiz") or 1.0, b.get("ses"), b.get("duygu"),
                                                                          bool(b.get("klon")), b.get("tohum"), ilerle)))
        if yol == "/api/yst/kalem/uret" and method == "POST":
            b = h.read_json()
            app = h.app
            kaynak = b.get("kaynak")
            if isinstance(kaynak, dict) and "kare" in kaynak:    # oynatma başlığındaki kare: çizilecek resim olarak kaydedilir
                try:
                    t = float(kaynak["kare"])
                except (TypeError, ValueError):
                    raise Hata("kare zamanı sayı olmalı")
                dosya = app.frame(t)
                os.makedirs(os.path.join(app.dir, "media", "ara-sahne"), exist_ok=True)
                kaynak_yol = os.path.join(app.dir, "media", "ara-sahne", f"kare-{int(t * 100):06d}.png")
                shutil.copy2(dosya, kaynak_yol)
            else:
                kaynak_yol = app.media_path(str(kaynak or ""))
            app_dir = app.dir
            return h.reply(200, _is_baslat("kalem", lambda ilerle: kalem_uret(app_dir, kaynak_yol, str(b.get("stil") or "karakalem"), str(b.get("zemin") or ""), bool(b.get("gecis")),
                                                                              b.get("bekle") or 2.0, b.get("sure") or 8.0, b.get("kalem_sesi") is not False, ilerle)))
        return h.reply(404, {"error": "bilinmeyen YSTCore rotası"})
    except (Hata, ValueError) as e:
        return h.reply(400, {"error": str(e)})
    except RuntimeError as e:
        return h.reply(400, {"error": str(e)})
