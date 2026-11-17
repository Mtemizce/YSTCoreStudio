"""Panel ek API'leri: ayar (model/effort), bağlayıcılar (ücretli servisler, MCP), marka kitleri, üretim isteği, onay, seslendirme metni.

panel.py bilinmeyen yolları buraya yönlendirir. Hatalar ValueError/RuntimeError ile döner (panel 400'e çevirir).
Güvenlik: API anahtarı YALNIZCA yazılır, hiçbir yanıtta geri dönmez; bulut izni projede açıkça onaylanmadan yazılmaz.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SISTEM = Path(__file__).resolve().parents[1]
ROOT = SISTEM.parent
ORTAM = SISTEM / "ortam"
VENV_PY = ORTAM / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
if not VENV_PY.exists():  # kurulumsuz çalışma (geliştirme/CI): panelin kendi yorumlayıcısı
    VENV_PY = Path(sys.executable)
AD_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
_M: dict = {}


def modul(ad: str, rel: str):
    if ad not in _M:
        spec = importlib.util.spec_from_file_location(ad, SISTEM / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _M[ad] = m
    return _M[ad]


def ayar():
    return modul("yst_ayar", "ayar/ayar.py")


def ortak():
    return modul("yst_ortak", "baglayici/ortak.py")


def mcp():
    return modul("yst_mcp", "baglayici/mcp.py")


def marka():
    return modul("yst_marka", "marka/marka.py")


def durum():
    return modul("yst_durum", "araclar/durum.py")


def konum():
    return modul("yst_konum", "araclar/konum.py")


def arsiv_m():
    return modul("yst_arsiv_ek", "arsiv/arsiv.py")


def onkosul():
    return modul("yst_onkosul", "kurulum/onkosul.py")


def profil_m():
    return modul("yst_profil", "araclar/profil.py")


YEDEK_AD_RE = re.compile(r"^[A-Za-z0-9._-]{1,90}\.(json|zip)$")


def yedek_dosya(ad: str) -> Path:
    """Yalnızca sistem/ortam/yedek/ içindeki dosyalar (yol gezintisi yok)."""
    if not YEDEK_AD_RE.match(ad or ""):
        raise ValueError("geçersiz dosya adı")
    p = ROOT / "sistem" / "ortam" / "yedek" / ad
    if not p.is_file():
        raise ValueError("dosya yok")
    return p


def profil_yuklendi(ad: str) -> dict:
    """Yüklenen profil dosyasının özeti (şifreliyse yalnızca 'şifreli' bilgisi)."""
    p = yedek_dosya(ad)
    try:
        return {"ok": True, "ad": ad, "ozet": profil_m().ozet(str(p), None)}
    except ValueError as e:
        raise ValueError(str(e)) from None


AGIR = {"calisiyor": False, "mesaj": "", "bitti": False}


def agir_derinlik_kur() -> dict:
    """İsteğe bağlı: derinlik modeli paketini (transformers) venv'e kurar. Kullanıcı düğmeye bastığında, arka planda."""
    import threading
    if AGIR["calisiyor"]:
        return {"ok": False, "mesaj": "kurulum sürüyor"}

    def is_():
        AGIR.update({"calisiyor": True, "bitti": False, "mesaj": "pip çalışıyor (birkaç dakika)…"})
        try:
            r = subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", str(SISTEM / "kurulum" / "gereksinim_agir.txt")], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800, creationflags=0x08000000 if os.name == "nt" else 0)
            AGIR["mesaj"] = "kuruldu: ilk mekân gezisinde model ağırlığı (~100 MB) iner" if r.returncode == 0 else "HATA: " + (r.stderr or r.stdout)[-300:]
        except Exception as e:  # noqa: BLE001
            AGIR["mesaj"] = f"HATA: {e}"
        AGIR.update({"calisiyor": False, "bitti": True})

    threading.Thread(target=is_, daemon=True).start()
    return {"ok": True}


def agir_durum() -> dict:
    import importlib.util
    return {**AGIR, "kurulu": importlib.util.find_spec("transformers") is not None}


def donanim_m():
    return modul("yst_donanim", "araclar/donanim.py")


def arka_indirme_m():
    return modul("yst_arka_indirme", "araclar/arka_indirme.py")


def bilesen_m():
    return modul("yst_bilesen", "araclar/bilesen.py")


def gorsel_k():
    return modul("yst_gorsel_kutuphane", "araclar/gorsel_kutuphane.py")


YEREL_GORSEL_ID = "yerel-zimage"


def _gorsel_var(gid: str) -> bool:
    try:
        gorsel_k().yol(gid)
        return True
    except ValueError:
        return False


def gorsel_durum() -> dict:
    k = gorsel_k()
    try:
        kurulu = bool(k.kurulu_mu())
    except Exception:  # noqa: BLE001
        kurulu = False
    return {"kurulu": kurulu, "is": k.is_durum(), "stiller": k.STILLER, "boyutlar": {a: list(v) for a, v in k.BOYUTLAR.items()},
            "adet_en_cok": k.EN_COK_ADET, "sayim": {d: len(k.liste(d)) for d in ("taslak", "onayli", "reddedildi")}}


def yerel_video_m():
    import yerel_video
    return yerel_video


def yerel_gorsel_m():
    import yerel_gorsel
    return yerel_gorsel


def guncelleme_m():
    import guncelleme
    return guncelleme


def bulut_disk_m():
    return modul("yst_bulut_disk", "araclar/bulut_disk.py")


def karakter_m():
    return modul("yst_karakter", "araclar/karakter.py")


def seri_m():
    return modul("yst_seri", "araclar/seri.py")


def depolama_m():
    return modul("yst_depolama", "araclar/depolama.py")


def ses_temizle_m():
    return modul("yst_ses_temizle", "araclar/ses_temizle.py")


def ses_kaydet(proje: str, veri: bytes, uzanti: str) -> dict:
    """Panelden kaydedilen sesi (dikte mikrofonu) yerelde temizleyip projenin kaynak/ses/ klasörüne koyar."""
    p = proje_kontrol(proje)
    d = p / "kaynak" / "ses"
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.glob("kayit-*.wav"))) + 1
    hedef = d / f"kayit-{n:02d}.wav"
    r = ses_temizle_m().bayttan(veri, str(hedef), uzanti)
    return {"ok": True, "dosya": f"kaynak/ses/{hedef.name}", "once": r["once"], "sonra": r["sonra"]}


# ------------------------------------------------------------------ ses klonlama örneği ("Sesimi klonla")
KLON_ORNEK = ROOT / "kimlik" / "ses" / "ornek.wav"  # kullanıcıya özel, git'e girmez
KLON_EN_UZUN = 20  # sn: Pocket TTS zaten fazlasını keser; gereksiz uzun örnek işlemi yavaşlatır
KLON_EN_KISA = 1.5


def klon_durum() -> dict:
    """Ses klonlama bileşeni kurulu mu, kayıtlı örnek ses var mı ve kaç saniye."""
    sure = None
    if KLON_ORNEK.is_file():
        try:
            sure = ses_temizle_m().olc(KLON_ORNEK)["sure"]
        except (RuntimeError, OSError):
            sure = None
    kalite = None
    if KLON_KALITE.is_file():
        try:
            kalite = json.loads(KLON_KALITE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            kalite = None
    return {"hazir": importlib.util.find_spec("pocket_tts_turkish") is not None, "ornek": KLON_ORNEK.is_file(), "sure": sure, "kalite": kalite,
            "en_iyi": "3-10 sn temiz, tek kişi, arka plan müziği yok"}


KLON_KALITE = ROOT / "kimlik" / "ses" / "ornek.json"  # son ölçüm (sinyal ölçütleri + varsa klon denemesi)
KLON_DENEME = ROOT / "kimlik" / "ses" / "deneme.wav"
KLON_DENE: dict = {"calisiyor": False, "hata": None}


def _klon_olc(yol, temiz: bool) -> dict | None:
    """Ses ölçütleri (ayrı süreçte: panel numpy/PyTorch yüklemesin). Ölçülemezse None: klonlamayı engellemez."""
    cmd = [str(VENV_PY), str(SISTEM / "araclar" / "klon_olc.py"), "sinyal", str(yol)] + (["--temiz"] if temiz else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, creationflags=ses_temizle_m().NW)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def _klon_kalite_yaz(kalite: dict | None) -> None:
    """Yeni örnek: eski ölçüm ve deneme sesi geçersiz olur."""
    KLON_DENEME.unlink(missing_ok=True)
    if kalite is None:
        KLON_KALITE.unlink(missing_ok=True)
    else:
        KLON_KALITE.write_text(json.dumps(kalite, ensure_ascii=False), encoding="utf-8")


def klon_ornek_kaydet(veri: bytes, uzanti: str) -> dict:
    """Panelde kaydedilen sesi (dikte ya da 'Sesimi kaydet') temizleyip klon örneği olarak saklar; önceki örneğin yerine geçer."""
    import tempfile
    st = ses_temizle_m()
    KLON_ORNEK.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        temiz = Path(td) / "temiz.wav"
        ham = Path(td) / ("ham" + (uzanti if re.fullmatch(r"\.[a-z0-9]{2,4}", uzanti) else ".webm"))
        ham.write_bytes(veri)
        kalite = _klon_olc(ham, False)  # gürültü ve patlama temizlikten ÖNCE ölçülür
        r = st.bayttan(veri, str(temiz), uzanti)
        sure = r["sonra"]["sure"] or 0
        if sure < KLON_EN_KISA:
            raise ValueError("kayıt çok kısa: en az birkaç saniye konuş (en iyisi 5-10 sn)")
        kes = subprocess.run([st._ff(), "-v", "error", "-y", "-i", str(temiz), "-t", str(KLON_EN_UZUN), "-ar", "24000", "-ac", "1", str(KLON_ORNEK)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=st.NW)
        if kes.returncode != 0:
            raise RuntimeError("örnek ses kaydedilemedi: " + (kes.stderr or "")[-200:])
    sure = min(sure, KLON_EN_UZUN)
    uyari = ""
    if sure < 3:
        uyari = "Örnek kısa; 5-10 saniye konuşursan klon daha doğal çıkar."
    _klon_kalite_yaz(kalite)
    return {"ok": True, "sure": round(sure, 1), "uyari": uyari, "kalite": kalite}


def klon_ornek_sil() -> dict:
    if KLON_ORNEK.is_file():
        KLON_ORNEK.unlink()
    _klon_kalite_yaz(None)
    return {"ok": True}


def klon_dene_baslat() -> dict:
    """Örnek sesle bir cümle üretip Whisper'la geri çözer (anlaşılırlık %). Arka planda çalışır; sonuç klon_dene_durum'dan okunur. Başarısızlık sayılmaz."""
    import os
    import threading
    if not KLON_ORNEK.is_file():
        raise ValueError("önce bir ses örneği kaydet")
    if importlib.util.find_spec("pocket_tts_turkish") is None:
        raise ValueError("ses klonlama bileşeni kurulu değil: Ayarlar → Sistem → Ses klonlama → Kur")
    if KLON_DENE.get("calisiyor"):
        raise ValueError("deneme zaten sürüyor")
    KLON_DENE.update(calisiyor=True, hata=None, sonuc=None, bas=time.time())
    imza = KLON_ORNEK.stat().st_mtime_ns

    def is_():
        try:
            r = subprocess.run([str(VENV_PY), str(SISTEM / "araclar" / "klon_olc.py"), "dene", str(KLON_ORNEK), str(KLON_DENEME)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=900, creationflags=ses_temizle_m().NW, env={**os.environ, "PYTHONUTF8": "1"})
            if r.returncode != 0:
                raise RuntimeError(((r.stderr or r.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1].replace("HATA:", "").strip())
            sonuc = json.loads(r.stdout)
            if KLON_ORNEK.is_file() and KLON_ORNEK.stat().st_mtime_ns == imza:  # deneme sürerken örnek değiştiyse sonuç eskidir
                k = json.loads(KLON_KALITE.read_text(encoding="utf-8")) if KLON_KALITE.is_file() else {}
                k["dene"] = sonuc
                KLON_KALITE.write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
                KLON_DENE["sonuc"] = sonuc
        except Exception as e:  # noqa: BLE001  (arka plan işi: hata kullanıcıya iletilir)
            KLON_DENE["hata"] = str(e)[:300]
        finally:
            KLON_DENE["calisiyor"] = False

    threading.Thread(target=is_, daemon=True).start()
    return {"ok": True}


def klon_dene_durum() -> dict:
    return {"calisiyor": bool(KLON_DENE.get("calisiyor")), "hata": KLON_DENE.get("hata"), "sonuc": KLON_DENE.get("sonuc"),
            "ses": KLON_DENEME.is_file() and bool(KLON_DENE.get("sonuc"))}


def klon_projeden(proje: str, dosya: str, onay: bool) -> dict:
    """Proje sayfasında kaydedilen sesi (kaynak/ses/kayit-NN.wav) klon örneği yapar ve bu projenin seslendirmesini o sese bağlar."""
    if not onay:
        raise ValueError("ses klonlama uyarısı kabul edilmedi")
    if importlib.util.find_spec("pocket_tts_turkish") is None:
        raise ValueError("ses klonlama bileşeni kurulu değil: Ayarlar → Sistem → Ses klonlama → Kur")
    p = proje_kontrol(proje)
    ad = Path(str(dosya)).name
    if not re.fullmatch(r"kayit-\d+\.wav", ad) or not (p / "kaynak" / "ses" / ad).is_file():
        raise ValueError("bu projede böyle bir ses kaydı yok")
    st = ses_temizle_m()
    KLON_ORNEK.parent.mkdir(parents=True, exist_ok=True)
    kes = subprocess.run([st._ff(), "-v", "error", "-y", "-i", str(p / "kaynak" / "ses" / ad), "-t", str(KLON_EN_UZUN), "-ar", "24000", "-ac", "1", str(KLON_ORNEK)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=st.NW)
    if kes.returncode != 0:
        raise RuntimeError("örnek ses hazırlanamadı: " + (kes.stderr or "")[-200:])
    sure = st.olc(KLON_ORNEK)["sure"] or 0
    if sure < KLON_EN_KISA:
        KLON_ORNEK.unlink(missing_ok=True)
        raise ValueError("kayıt çok kısa: en az birkaç saniye konuş (en iyisi 5-10 sn)")
    kalite = _klon_olc(KLON_ORNEK, True)  # proje kaydı zaten temizlenmişti: gürültü/oran tahmini
    _klon_kalite_yaz(kalite)
    yol = klon_projeye(p.name)
    up = p / "uretim.json"
    u = json.loads(up.read_text(encoding="utf-8")) if up.is_file() else {}
    u["seslendirme"] = {**(u.get("seslendirme") or {}), "acik": True, "saglayici": "ema", "motor": "pocket-tr", "klon": True, "klon_yol": yol,
                        "klon_onay": time.strftime("%Y-%m-%d %H:%M:%S")}
    up.write_text(json.dumps(u, ensure_ascii=False, indent=2), encoding="utf-8")
    bp = p / "brief.md"
    if bp.is_file():
        with bp.open("a", encoding="utf-8") as f:
            f.write("\n\n## Seslendirme güncellemesi\nKullanıcı seslendirmenin KENDİ SESİYLE yapılmasını istedi (panelde onayladı): plan'da `\"motor\": \"pocket-tr\", \"klon\": \"klon/ornek.wav\"` kullan.\n")
    return {"ok": True, "sure": round(min(sure, KLON_EN_UZUN), 1), "uyari": "Örnek kısa; 5-10 saniye konuşursan klon daha doğal çıkar." if sure < 3 else "", "kalite": kalite}


# ------------------------------------------------------------------ ara sahne şablonları (kalemle çizim)
ARA_SAHNE: dict = {"calisiyor": False, "hata": None, "sonuc": None}
ARA_KAYNAK_UZ = (".dwg", ".svg")
ARA_FOTO_UZ = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")
ARA_VIDEO_UZ = (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi")


def kalem_m():
    return modul("yst_kalem_cizim", "araclar/kalem_cizim.py")


def _dwg_okunur() -> bool:
    return sys.platform == "win32" and (SISTEM / "araclar" / "dis" / "libredwg" / "dwg2SVG.exe").is_file()


def ara_sahne_sablonlar(proje: str | None = None) -> dict:
    """Ara sahne şablon galerisi: şablon, stiller ve önizleme adresleri; proje verilirse o projenin kaynaklarındaki çizimler de."""
    import shutil
    km = kalem_m()
    sablonlar = [{"id": "kalem-cizim", "ad": "Kalemle çizim", "kaynak": "DWG/SVG çizimi, herhangi bir resim ya da videonun ilk karesi",
                  "aciklama": "Kaynaktaki çizim ya da resim, kâğıt üstünde kalemle kademeli çizilir; istersen çizim bitince bulanıklaşıp gerçek resme (ya da videoya) dönüşür.",
                  "stiller": [{"id": k, "ad": v["ad"], "aciklama": v["aciklama"], "onizleme": f"/api/ara-sahne/onizleme?id={k}"} for k, v in km.STILLER.items()]}]
    r = {"sablonlar": sablonlar,
         "hazir": {"tarayici": (ROOT / "node_modules" / ".remotion" / "chrome-headless-shell").is_dir() or bool(__import__("os").environ.get("CHROME")),
                   "ffmpeg": bool(shutil.which("ffmpeg")), "dwg_okuma": _dwg_okunur()}}
    if proje:
        p = proje_kontrol(proje)
        kaynaklar = []
        for klasor, uzler, kat in (("belge", ARA_KAYNAK_UZ, "cizim"), ("foto", ARA_FOTO_UZ, "resim"), ("video", ARA_VIDEO_UZ, "video")):
            d = p / "kaynak" / klasor
            for f in sorted(d.glob("*")) if d.is_dir() else []:
                if f.suffix.lower() in uzler and f.is_file() and not f.name.startswith("ara-sahne-"):
                    kaynaklar.append({"ad": f.name, "yol": f"kaynak/{klasor}/{f.name}", "tur": f.suffix[1:].lower(), "kat": kat,
                                      "okunur": f.suffix.lower() != ".dwg" or _dwg_okunur()})
        r["kaynaklar"] = kaynaklar
    return r


def ara_sahne_onizleme(sid: str) -> Path | None:
    if sid not in kalem_m().STILLER:
        return None
    p = SISTEM / "kit" / "kalem" / "onizleme" / f"{sid}.jpg"
    return p if p.is_file() else None


def ara_sahne_uret(b: dict) -> dict:
    """Seçilen çizimi seçilen stille kalem çizimi videosuna çevirir (arka planda); sonuç projenin kaynak/video/ klasörüne yazılır."""
    import threading
    p = proje_kontrol(str(b.get("proje") or ""))
    stil = str(b.get("stil") or "")
    if stil not in kalem_m().STILLER:
        raise ValueError("geçersiz stil")
    kaynaklar = {k["yol"]: k for k in ara_sahne_sablonlar(p.name)["kaynaklar"]}
    k = kaynaklar.get(str(b.get("kaynak") or ""))
    if not k:
        raise ValueError("kaynak bulunamadı (kaynak/belge içinde .dwg/.svg, kaynak/foto içinde resim ya da kaynak/video içinde video olmalı)")
    if not k["okunur"]:
        raise ValueError("DWG okuma yalnızca Windows'ta paketli LibreDWG ile yapılır: çizimi SVG olarak dışa aktarıp ekle")
    try:
        sure = max(4.0, min(30.0, float(b.get("sure") or 8)))
    except (TypeError, ValueError):
        raise ValueError("süre sayı olmalı (4-30 sn)")
    gecis = bool(b.get("gecis")) and k["kat"] == "resim"
    try:
        bekle = max(0.5, min(10.0, float(b.get("bekle") or 2)))
    except (TypeError, ValueError):
        raise ValueError("bekleme süresi sayı olmalı (0,5-10 sn)")
    komut_ek = ["--gecis", "--bekle", str(bekle)] if gecis else (["--bekle", str(bekle)] if k["kat"] == "video" else [])
    zemin = str(b.get("zemin") or "").strip()
    try:
        kalem_m().zemin_rgb(zemin)
    except ValueError as e:
        raise ValueError(str(e)) from e
    if zemin:
        komut_ek += ["--zemin", zemin]
    if b.get("kalem_sesi") is False:
        komut_ek += ["--sessiz"]
    if ARA_SAHNE.get("calisiyor"):
        raise ValueError("başka bir ara sahne üretiliyor")
    hedef_dir = p / "kaynak" / "video"
    hedef_dir.mkdir(parents=True, exist_ok=True)
    ad = f"ara-sahne-{Path(k['ad']).stem}-{stil}" + ("-gercege" if gecis else ("-giris" if k["kat"] == "video" else ""))
    ad = re.sub(r"[^A-Za-z0-9_\-]+", "_", ad)[:80]
    hedef, n = hedef_dir / f"{ad}.mp4", 2
    while hedef.exists():
        hedef = hedef_dir / f"{ad}-{n}.mp4"
        n += 1
    ARA_SAHNE.update(calisiyor=True, hata=None, sonuc=None, bas=time.time(), proje=p.name)

    def is_():
        import os
        try:
            r = subprocess.run([str(VENV_PY), str(SISTEM / "araclar" / "kalem_cizim.py"), str(p / k["yol"]), "-o", str(hedef), "--stil", stil, "--sure", str(sure), *komut_ek],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1200, env={**os.environ, "PYTHONUTF8": "1"},
                               creationflags=ses_temizle_m().NW)
            if r.returncode != 0:
                raise RuntimeError(((r.stderr or r.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1].replace("HATA:", "").strip())
            ARA_SAHNE["sonuc"] = {"dosya": f"kaynak/video/{hedef.name}", "boyut_mb": round(hedef.stat().st_size / 1e6, 1), "sure": sure, "stil": stil, "zemin": zemin or None, "kalem_sesi": b.get("kalem_sesi") is not False, "gecis": gecis, "kat": k["kat"], **json.loads(r.stdout.strip().splitlines()[-1])}
        except Exception as e:  # noqa: BLE001  (arka plan işi: hata kullanıcıya iletilir)
            ARA_SAHNE["hata"] = str(e)[:300]
        finally:
            ARA_SAHNE["calisiyor"] = False

    threading.Thread(target=is_, daemon=True, name="ara-sahne").start()
    return {"ok": True, "hedef": f"kaynak/video/{hedef.name}"}


KAPAK_DIZIN = SISTEM / "ortam" / "yerel" / "kapak"


def kapak(proje: str) -> Path | None:
    """Pano'daki video kartı için kapak resmi: projenin `cikti/` klasöründeki en yeni mp4'ten bir kare (süresinin ~%25'i, en çok 60. sn), 640 px JPEG.
    Önbellekli (proje + dosya zamanı + boyutu); video yoksa ya da kare alınamazsa None."""
    import shutil
    p = proje_kontrol(proje)
    d = p / "cikti"
    videolar = sorted((f for f in d.glob("*.mp4") if f.is_file()), key=lambda f: f.stat().st_mtime, reverse=True) if d.is_dir() else []
    if not videolar or not shutil.which("ffmpeg"):
        return None
    v = videolar[0]
    st = v.stat()
    hedef = KAPAK_DIZIN / f"{proje}-{int(st.st_mtime)}-{st.st_size}.jpg"
    if hedef.is_file():
        return hedef
    KAPAK_DIZIN.mkdir(parents=True, exist_ok=True)
    for eski in KAPAK_DIZIN.glob(f"{proje}-*.jpg"):  # aynı projenin eski kapakları
        eski.unlink(missing_ok=True)
    sure = 0.0
    if shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True, timeout=20, creationflags=ses_temizle_m().NW)
        try:
            sure = float(r.stdout.strip())
        except ValueError:
            sure = 0.0
    ss = min(60.0, sure * 0.25) if sure > 0 else 0.0
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(hedef)],
                       capture_output=True, text=True, timeout=60, creationflags=ses_temizle_m().NW)
    return hedef if r.returncode == 0 and hedef.is_file() else None


def ara_sahne_durum() -> dict:
    return {k: ARA_SAHNE.get(k) for k in ("calisiyor", "hata", "sonuc", "proje")}


def klon_projeye(proje: str) -> str:
    """Kayıtlı örneği projeye kopyalar; plan'daki göreli yol (proje klasörüne göre) döner."""
    import shutil
    p = proje_kontrol(proje)
    hedef = p / "klon" / "ornek.wav"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KLON_ORNEK, hedef)
    return "klon/ornek.wav"


def b_plani_ayarla(b: dict) -> dict:
    """Mevcut projeye B planı (dijital sunucu) bilgisini yazar; Claude penceresi ayrıca /api/claude ile açılır."""
    p = proje_kontrol(b.get("proje", ""))
    k = karakter_m()
    ok_, eksik = k.hazir(str(b.get("karakter") or ""))
    if not ok_:
        raise ValueError("B planı için karakter hazır değil: " + "; ".join(eksik))
    uretken = bool(b.get("uretken"))
    up = p / "uretim.json"
    u = json.loads(up.read_text(encoding="utf-8")) if up.is_file() else {}
    u["b_plani"] = {"karakter": k.slug(b["karakter"]), "etiket": bool(b.get("etiket")), "etiket_metin": str(b.get("etiket_metin") or "Dijital sunum")[:60], "uretken": uretken,
                    "zaman": time.strftime("%Y-%m-%d %H:%M:%S")}
    up.write_text(json.dumps(u, ensure_ascii=False, indent=2), encoding="utf-8")
    durum().yaz(p.name, "planlama", "B planı: dijital sunucu")
    return {"ok": True, "b_plani": u["b_plani"]}


def kesif_m():
    return modul("yst_kesif", "baglayici/kesif.py")


def on_ayarlar() -> list[dict]:
    out = []
    for k, v in kesif_m().onayarlar().items():
        out.append({"id": k, "ad": v["ad"], "taban_url": v.get("taban_url", ""), "anahtar_adi": v.get("anahtar_adi"), "anahtar_gerekli": bool(v.get("anahtar_gerekli")),
                    "motor": v.get("motor"), "yetenekler": v.get("yetenekler", []), "dogrulama": v.get("dogrulama", "")})
    return out


def orkestratorler() -> dict:
    import shutil
    d = json.loads((ROOT / "sistem" / "baglayici" / "calisma_ortamlari.json").read_text(encoding="utf-8"))
    sec = (ayar().coz().get("orkestrator") or {}).get("calisma_ortami", "claude-code")
    liste = [{"id": k, "ad": v["ad"], "durum": v.get("durum"), "not": v.get("not", ""), "kurulu": bool(shutil.which(v["komut"])), "komut": v["komut"]} for k, v in d.items() if not k.startswith("_")]
    import orkestrator
    cfg = ayar().coz().get("orkestrator", {})
    for o in liste:
        if o["id"] in orkestrator.LOCAL:
            try:
                o["modeller"] = orkestrator.models(o["id"])
                o["kurulu"] = True
            except (OSError, ValueError) as e:
                o.update(kurulu=False, modeller=[], hata=str(e))
            o["adres"] = orkestrator.endpoint(o["id"], cfg)
        else:
            o["modeller"] = ayar().ortam_modelleri(o["id"])
    return {"secili": sec, "liste": liste, "model": cfg.get("model", "")}


def model_kontrol(sid: str, yetenek: str | None, model: str) -> None:
    ok, neden = kesif_m().model_gecerli(sid, yetenek, model)
    if not ok:
        raise ValueError(neden)


def isler_model_kontrol(yama: dict) -> None:
    """Ayar yamasındaki bulut model seçimleri servisin kendi listesinden olmalı (elle yazılan/uydurma ad reddedilir)."""
    kat = ortak().katalog()["saglayicilar"]
    for _, v in ((yama.get("isler") or {}).items()):
        for mid, m in ((v or {}).get("modeller") or {}).items():
            if isinstance(m, dict) and m.get("model") and m.get("saglayici") in kat and not kat[m["saglayici"]].get("yerel"):
                model_kontrol(m["saglayici"], "gorsel-duzenle", m["model"])


def yetenek_m():
    return modul("yst_yetenek", "baglayici/yetenek.py")


def saglayici_ornekleri() -> list[dict]:
    out = []
    d = ROOT / "sistem" / "baglayici" / "ornekler"
    for p in sorted(d.glob("*.json")):
        try:
            out.append({"ad": p.stem, "manifest": json.loads(p.read_text(encoding="utf-8"))})
        except (OSError, ValueError):
            pass
    return out


def yetenek_ozeti() -> dict:
    Y = yetenek_m()
    cz = ayar().coz()
    return {"yetenekler": Y.liste(), "sira": {k: (v or {}).get("sira", []) for k, v in (cz.get("yetenekler") or {}).items()}, "butce": Y.butce_ayari(), "bugun_harcama": Y.bugun_harcama()}


def iyilestir_m():
    return modul("yst_iyilestir", "arsiv/iyilestir.py")


IYI = {"thread": None, "dur": False, "durum": {"calisiyor": False, "bitti": True, "toplam": 0, "sira": 0, "tamam": 0, "hata": 0, "sonuclar": [], "model": None, "mesaj": ""}}


def proje_kontrol(ad: str) -> Path:
    if not AD_RE.match(ad or ""):
        raise ValueError("geçersiz proje adı")
    p = ROOT / "projeler" / ad
    if not p.is_dir():
        raise ValueError("proje yok")
    return p


def slug(s: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9]+", "-", s.translate(tr).lower()).strip("-")


def ayar_ozeti(proje: str | None) -> dict:
    a = ayar()
    cz = a.coz(proje)
    ork = a.orkestrator_ortami()
    return {"ajanlar": cz["ajanlar"], "uretim": cz["uretim"], "platformlar": cz["platformlar"], "kurallar": cz["kurallar"], "izin": cz.get("izin", {}),
            "isler": cz.get("isler", {}), "modeller": list(a.MODELLER), "effortlar": list(a.EFFORTLAR),
            "ortamlar": modul("yst_ajan_cagir", "araclar/ajan_cagir.py").ortam_listesi(), "orkestrator_ortami": ork,
            "ortam_modelleri": {o: a.ortam_modelleri(o) for o in a.calisma_ortamlari()},
            "ajan_etkin": {ad: {"ortam": a.etkin_ortam(v, ork), "model": a.ajan(ad, proje, cz, ork)["model"]} for ad, v in cz["ajanlar"].items()}}


def baglayicilar(proje: str | None) -> dict:
    o = ortak()
    kat = o.katalog()
    cz = ayar().coz(proje).get("baglayicilar", {})
    out = []
    for sid, k in kat["saglayicilar"].items():
        d = o.baglayici_durumu(sid, proje)
        d["aciklama"] = k.get("aciklama")
        d["ayar"] = {a: v for a, v in cz.get(sid, {}).items() if a in ("model", "modeller", "ses_id", "taban_url")}
        out.append(d)
    gd = gorsel_durum()
    out.insert(0, {"id": YEREL_GORSEL_ID, "ad": "Yerel: Z-Image-Turbo (bu bilgisayarda)", "tur": ["gorsel"], "yerel": True, "ucretli": False, "etkin": gd["kurulu"], "kurulu": gd["kurulu"],
                   "anahtar_adi": None, "anahtar_var": None, "aciklama": "Görselleri bu bilgisayarda, ücretsiz ve hesapsız üretir. Kurulu değilse seçince kurulum yönlendirmesi çıkar."})
    return {"saglayicilar": out, "kategoriler": kat["kategoriler"], "mcp": mcp().liste()}


def uretim_durumu(proje: str) -> dict:
    p = proje_kontrol(proje)
    d = durum().oku(proje)
    u = {}
    try:
        u = json.loads((p / "uretim.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    bulut = (p / "bulut_gunlugu.md")
    cagri = max(0, len(bulut.read_text(encoding="utf-8").splitlines()) - 6) if bulut.exists() else 0
    return {"durum": d, "uretim": {k: u.get(k) for k in ("platformlar", "seslendirme", "gorsel_uret", "sure", "marka", "seri")}, "bulut_cagri": cagri,
            "onay": (p / "onay.json").exists(), "ajan_ayari_var": (p / "ayar.json").exists()}


# ------------------------------------------------------------------ GET
def get(yol: str, q: dict):
    if yol == "/api/yerelvideo":
        return yerel_video_m().durum()
    if yol == "/api/dikte/durum":
        return dikte_durum()
    if yol == "/api/ayar":
        return ayar_ozeti(q.get("proje") or None)
    if yol == "/api/baglayici":
        return baglayicilar(q.get("proje") or None)
    if yol == "/api/gorsel":
        return gorsel_durum()
    if yol == "/api/gorsel/liste":
        return {"ogeler": gorsel_k().liste(q.get("durum") or None, q.get("seri") or None)}
    if yol == "/api/marka":
        return {"kitler": marka().liste(), "varsayilan": ayar().coz()["uretim"].get("marka_kiti")}
    if yol == "/api/marka/kit":
        return marka().oku(q.get("id", ""))
    if yol == "/api/proje/durum":
        return uretim_durumu(q.get("proje", ""))
    if yol == "/api/ses-metin":
        return {"satirlar": modul("yst_sesd", "araclar/ses_duzenle.py").goster(proje_kontrol(q.get("proje", "")).name, q.get("format", "ana"))}
    if yol == "/api/donanim":
        return donanim_m().hepsi()
    if yol == "/api/klon":
        return klon_durum()
    if yol == "/api/klon/dene":
        return klon_dene_durum()
    if yol == "/api/ara-sahne":
        return ara_sahne_sablonlar(q.get("proje") or None)
    if yol == "/api/ara-sahne/durum":
        return ara_sahne_durum()
    if yol == "/api/bilesen":
        return bilesen_m().durum()
    if yol == "/api/arka-indirme":
        return arka_indirme_m().durum()
    if yol == "/api/yerelgorsel":
        return yerel_gorsel_m().durum()
    if yol == "/api/guncelleme":
        return guncelleme_m().durum()
    if yol == "/api/bulutdisk":
        d = bulut_disk_m().durum()
        d["onbellek_mb"] = round(bulut_disk_m().onbellek_boyut() / 1e6, 1)
        return d
    if yol == "/api/agir/durum":
        return agir_durum()
    if yol == "/api/karakter":
        return {"karakterler": karakter_m().liste(), "riza_metni": karakter_m().RIZA_METNI}
    if yol == "/api/seri/detay":
        k = seri_m().oku(q.get("id", ""))
        for m in k["model_seti"]:
            m["gorsel_var"] = [g for g in m["gorseller"] if _gorsel_var(g)]
        return {"seri": k, "bolumler": seri_m().bolumler(k["id"])}
    if yol == "/api/seri":
        return {"seriler": seri_m().liste(), "karakterler": [k["id"] for k in karakter_m().liste()]}
    if yol == "/api/depolama":
        return depolama_m().durum()
    if yol == "/api/on-ayar":
        return {"on_ayarlar": on_ayarlar()}
    if yol == "/api/orkestrator":
        return orkestratorler()
    if yol == "/api/baglayici/modeller":
        sid = q.get("saglayici", "")
        if sid not in ortak().katalog()["saglayicilar"]:
            raise ValueError("bilinmeyen sağlayıcı")
        c = kesif_m().onbellek(sid)
        return c or {"saglayici": sid, "modeller": [], "sesler": [], "zaman": None}
    if yol == "/api/saglayici/ornekler":
        return {"ornekler": saglayici_ornekleri()}
    if yol == "/api/yetenek":
        return yetenek_ozeti()
    if yol == "/api/arsiv/kutuphane":
        A = arsiv_m()
        tur = (q.get("tur") or "").strip() or None
        kelime = (q.get("kelime") or "").strip() or None
        kok = int(q["kok"]) if (q.get("kok") or "").isdigit() else None
        lim = max(1, min(int(q.get("limit") or 60) if str(q.get("limit") or "60").isdigit() else 60, 200))
        kokler = {a["id"]: a["ad"] for a in A.arsivler()}
        sat = A.ara(None, tur, kelime, None, lim, kok_id=kok)
        return {"turler": A.durum().get("kategoriler", []), "arsivler": [{"id": i, "ad": a} for i, a in kokler.items()],
                "sonuc": [{"id": r["id"], "ad": r["ad"], "tur": r["tur"], "kategori": A.TUR_ETIKET.get(r["tur"], r["tur"]), "klasor": r["klasor"], "sure": r["sure"],
                           "boyut": r["boyut"], "yil": r["yil"], "arsiv": kokler.get(r["kok_id"], ""), "cevrimdisi": bool(r["cevrimdisi"])} for r in sat]}
    if yol == "/api/arsiv/iyilestirme/modeller":
        return iyilestir_m().modeller()
    if yol == "/api/arsiv/iyilestirme/durum":
        return IYI["durum"]
    if yol == "/api/konum":
        return konum_ozeti()
    if yol == "/api/sistem":
        return sistem_ozeti(False)
    return None


def iyi_baslat(b: dict) -> dict:
    """Seçilen fotoğrafları arka planda iyileştirir. Bulut modeli: bağlayıcı etkin + anahtar + BU işlem için onay şart (başlamadan kontrol edilir)."""
    I = iyilestir_m()
    if IYI["thread"] and IYI["thread"].is_alive():
        return {"ok": False, "mesaj": "bir iyileştirme zaten sürüyor"}
    idler = [int(x) for x in (b.get("idler") or [])][:300]
    if not idler:
        raise ValueError("fotoğraf seçilmedi")
    model = str(b.get("model") or "")
    m = next((x for x in I.modeller()["modeller"] if x["id"] == model), None)
    if not m or not m["etkin"]:
        raise ValueError("model seçilemedi (Ayarlar → İşler ve modeller'de listeye açık olmalı)")
    if not m["kullanilabilir"]:
        raise ValueError(f"{m['ad']} kullanılamıyor: {m['neden']}")
    onay = bool(b.get("bulut_onay"))
    if not m["yerel"] and not onay:
        raise ValueError(f"{len(idler)} fotoğraf {m['saglayici']} servisine gönderilecek: onay kutusunu işaretle")
    olcek = float(b.get("olcek") or 2.0)
    keskin = float(b.get("keskinlik") if b.get("keskinlik") is not None else 0.5)
    IYI["dur"] = False
    d = IYI["durum"]
    d.update({"calisiyor": True, "bitti": False, "toplam": len(idler), "sira": 0, "tamam": 0, "hata": 0, "sonuclar": [], "model": model, "mesaj": "başladı"})

    def ilerleme(x):
        d.update({"sira": x["sira"], "tamam": x["tamam"], "hata": x["hata"]})
        d["sonuclar"].append(x["son"])

    def is_():
        try:
            I.iyilestir(idler, model, olcek, keskin, onay, durdur=lambda: IYI["dur"], ilerleme=ilerleme)
            d["mesaj"] = "durduruldu" if IYI["dur"] else "bitti"
        except Exception as e:  # noqa: BLE001
            d["mesaj"] = f"hata: {type(e).__name__}: {e}"[:300]
        finally:
            d.update({"calisiyor": False, "bitti": True})

    import threading
    IYI["thread"] = threading.Thread(target=is_, daemon=True)
    IYI["thread"].start()
    return {"ok": True, "toplam": len(idler)}


def konum_ozeti() -> dict:
    K, A = konum(), arsiv_m()
    c = A.baglan()
    try:
        if not c.execute("SELECT 1 FROM kok WHERE ad='studyo'").fetchone():
            K.studyo_guncelle(c)  # Başlat.cmd dışından açıldıysa da bu klasörün yeri kayıtlı olsun
        return {"makine": K.makine(), "studyo": str(ROOT), "kokler": K.kok_listesi(c), "damga": K.damga_oku(),
                "bilgi": {"env_ornegi": K.env_adi("arsiv") + "=D:\\Arsiv", "yedek_klasoru": str(ROOT / "sistem" / "ortam" / "yedek")}}
    finally:
        c.close()


def sistem_ozeti(ag: bool) -> dict:
    o = onkosul().tara(ag=ag)
    log = ROOT / "sistem" / "ortam" / "yerel" / "onarim.log"
    try:
        o["onarim_son"] = log.read_text(encoding="utf-8")[-1500:] if log.exists() else ""
    except OSError:
        o["onarim_son"] = ""
    return o


# ------------------------------------------------------------------ POST
def post(yol: str, q: dict, b: dict):
    if yol == "/api/yerelvideo/kur":
        return yerel_video_m().kur()
    if yol == "/api/yerelvideo/uret":
        return yerel_video_m().baslat(b.get("proje", ""), b.get("istem", ""), b.get("kare", 49))
    if yol == "/api/yerelvideo/iptal":
        return yerel_video_m().iptal(b.get("proje"))
    if yol == "/api/ayar":
        proje = b.get("proje") or None
        if proje:
            proje_kontrol(proje)
        yama = b.get("yama") or {}
        if not isinstance(yama, dict):
            raise ValueError("yama bir nesne olmalı")
        izinli = {k: yama[k] for k in ("ajanlar", "uretim", "kurallar", "baglayicilar", "izin", "isler", "saglayicilar", "yetenekler", "butce", "orkestrator") if k in yama}
        if not proje and "izin" in izinli:
            raise ValueError("bulut izni yalnızca proje bazında verilir")
        isler_model_kontrol(izinli)
        ayar().kaydet(izinli, proje)
        esit = ayar().esitle() if (not proje and "ajanlar" in izinli) else []
        return {"ok": True, "esitlenen": esit}
    if yol == "/api/baglayici/etkin":
        sid = b.get("saglayici", "")
        if sid not in ortak().katalog()["saglayicilar"]:
            raise ValueError("bilinmeyen sağlayıcı")
        ayar().kaydet({"baglayicilar": {sid: {"etkin": bool(b.get("etkin"))}}}, None)
        return {"ok": True}
    if yol == "/api/baglayici/ayar":
        sid = b.get("saglayici", "")
        if sid not in ortak().katalog()["saglayicilar"]:
            raise ValueError("bilinmeyen sağlayıcı")
        yeni = {}
        for alan, uz in (("ses_id", 80), ("taban_url", 200)):
            if alan in b:
                v = str(b[alan] or "").strip()[:uz]
                if alan == "taban_url" and v:
                    ortak()._url_kontrol(v)
                if re.search(r"[\s\"'&%]", v):
                    raise ValueError(f"{alan} geçersiz karakter içeriyor")
                if alan == "ses_id" and v:
                    c = kesif_m().onbellek(sid)
                    if c and c.get("sesler") and v not in {x["id"] for x in c["sesler"]}:
                        raise ValueError("ses kimliği servisin ses listesinde yok: listeden seç")
                yeni[alan] = v
        # MODEL ELLE YAZILMAZ: servisin kendi listesinden seçilir (yetenek → model)
        if "modeller" in b:
            if not isinstance(b["modeller"], dict):
                raise ValueError("modeller {yetenek: model} olmalı")
            yeni["modeller"] = {}
            for y, mdl in b["modeller"].items():
                mdl = str(mdl or "").strip()
                if mdl:
                    model_kontrol(sid, y, mdl)
                yeni["modeller"][str(y)] = mdl
        if "model" in b and str(b["model"] or "").strip():
            model_kontrol(sid, None, str(b["model"]).strip())
            yeni["model"] = str(b["model"]).strip()
        elif "model" in b:
            yeni["model"] = ""
        ayar().kaydet({"baglayicilar": {sid: yeni}}, None)
        return {"ok": True}
    if yol == "/api/baglayici/anahtar":
        sid = b.get("saglayici", "")
        kat = ortak().katalog()["saglayicilar"].get(sid)
        if not kat or not kat.get("anahtar"):
            raise ValueError("bu sağlayıcı anahtar kullanmaz")
        if b.get("sil"):
            ortak().anahtar_sil(kat["anahtar"])
        else:
            ortak().anahtar_yaz(kat["anahtar"], str(b.get("deger", "")))
        return {"ok": True, "anahtar_var": ortak().anahtar_var(kat["anahtar"])}  # değer ASLA geri dönmez
    if yol == "/api/baglayici/test":
        sid = b.get("saglayici", "")
        r = subprocess.run([str(VENV_PY), str(SISTEM / "baglayici" / "uret.py"), "test", sid], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(ROOT), timeout=90, creationflags=ses_temizle_m().NW)
        return {"ok": r.returncode == 0, "cikti": ortak().maskele((r.stdout + r.stderr).strip())[-300:]}
    if yol == "/api/mcp/kaydet":
        k = mcp().kaydet(str(b.get("ad", "")), str(b.get("tur", "")), str(b.get("komut", "")), str(b.get("url", "")), str(b.get("anahtar_adi", "")), bool(b.get("etkin", True)))
        if b.get("anahtar") and k.get("anahtar_adi"):
            ortak().anahtar_yaz(k["anahtar_adi"], str(b["anahtar"]))
        return {"ok": True}
    if yol == "/api/mcp/sil":
        mcp().sil(str(b.get("ad", "")))
        return {"ok": True}
    if yol == "/api/marka/kaydet":
        k = dict(b.get("kit") or {})
        if not k.get("id") and not (k.get("ad") or k.get("isim")):
            raise ValueError("kit adı gerekli")
        return {"ok": True, "kit": marka().kaydet(k)}
    if yol == "/api/marka/sil":
        marka().sil(str(b.get("id", "")))
        return {"ok": True}
    if yol == "/api/onay":
        p = proje_kontrol(b.get("proje", ""))
        d = durum().oku(p.name)
        if d.get("asama") != "taslak-hazir":
            raise ValueError(f"onay yalnızca 'taslak hazır' aşamasında verilebilir (şu an: {d.get('etiket') or d.get('asama')})")
        (p / "onay.json").write_text(json.dumps({"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "onaylayan": "kullanıcı (panel)"}, ensure_ascii=False), encoding="utf-8")
        durum().yaz(p.name, "onaylandi", "kullanıcı panelden onayladı")
        return {"ok": True}
    if yol == "/api/arsiv/iyilestirme/adaylar":
        yil = None
        if b.get("yil0"):
            yil = f"{int(b['yil0'])}-{int(b.get('yil1') or b['yil0'])}"
        sat = iyilestir_m().adaylar(yil, (b.get("proje") or "").strip() or None, float(b.get("en_cok_puan") or 6.0), max(1, min(int(b.get("limit") or 60), 300)),
                                    int(b["kok"]) if b.get("kok") else None, bool(b.get("yapilmislar")))
        return {"adaylar": sat}
    if yol == "/api/arsiv/iyilestirme/baslat":
        return iyi_baslat(b)
    if yol == "/api/arsiv/iyilestirme/durdur":
        IYI["dur"] = True
        return {"ok": True}
    if yol == "/api/arsiv/iyilestirme/liste":
        return {"liste": iyilestir_m().liste([int(x) for x in (b.get("idler") or [])][:300] or None)}
    if yol == "/api/arsiv/iyilestirme/kullan":
        return iyilestir_m().kullan(int(b.get("id") or 0), bool(b.get("kullan")))
    if yol == "/api/arsiv/iyilestirme/sil":
        return iyilestir_m().sil(int(b.get("id") or 0))
    if yol == "/api/konum/gozat":
        return konum().gozat(str(b.get("yol") or "").strip().strip('"') or None)
    if yol == "/api/konum/arsiv":
        ad = slug(str(b.get("ad") or "arsiv"))[:30] or "arsiv"
        yol_s = str(b.get("yol") or "").strip().strip('"')
        if not yol_s:
            raise ValueError("klasör yolu gerekli")
        r = arsiv_m().ayarla(yol_s, ad, bool(b.get("zorla")))
        return {"ok": True, "arsiv": r}
    if yol == "/api/konum/yeniden-bul":
        K, A = konum(), arsiv_m()
        c = A.baglan()
        z = K.kok_coz(c, int(b.get("id") or 0), True)
        c.close()
        return {"ok": z["yol"] is not None, "yol": str(z["yol"]) if z["yol"] else None, "yontem": z["yontem"], "not": z["not"]}
    if yol == "/api/konum/arsiv-sil":
        K, A = konum(), arsiv_m()
        c = A.baglan()
        r = c.execute("SELECT tur FROM kok WHERE id=?", (int(b.get("id") or 0),)).fetchone()
        if not r or r[0] != "arsiv":
            c.close()
            raise ValueError("yalnızca arşiv kayıtları silinebilir")
        n = K.kok_sil(c, int(b["id"]))
        c.close()
        return {"ok": True, "silinen_kayit": n, "not": "Yalnızca veritabanı kaydı silindi; arşivdeki dosyalara dokunulmadı."}
    if yol == "/api/sistem/tara":
        return sistem_ozeti(True)
    if yol == "/api/klon/sil":
        return klon_ornek_sil()
    if yol == "/api/klon/dene":
        return klon_dene_baslat()
    if yol == "/api/ara-sahne/uret":
        return ara_sahne_uret(b)
    if yol == "/api/klon/projeden":
        return klon_projeden(str(b.get("proje") or ""), str(b.get("dosya") or ""), bool(b.get("onay")))
    if yol == "/api/arka-indirme/baslat":
        return arka_indirme_m().baslat(True, ses=arka_indirme_m().son_ses())
    if yol == "/api/arka-indirme/atla":
        return arka_indirme_m().atla()
    if yol == "/api/arka-indirme/ses":
        return arka_indirme_m().baslat(True, ses=True)
    if yol == "/api/arka-indirme/gpu-gerek-yok":
        return arka_indirme_m().gpu_istemiyor()
    if yol == "/api/arka-indirme/ses-gerek-yok":
        return arka_indirme_m().ses_istemiyor(True)
    if yol == "/api/bilesen/kur":
        return bilesen_m().kur(str(b.get("id") or ""), str(b.get("secenek") or ""))
    if yol == "/api/bilesen/kaldir":
        return bilesen_m().kaldir(str(b.get("id") or ""), str(b.get("secenek") or ""))
    if yol == "/api/kimlik/kaydet":
        k = modul("yst_kimlik_sablon", "araclar/kimlik_sablon.py")
        return k.kaydet(str(b.get("ad") or ""), str(b.get("marka") or ""), str(b.get("rol") or ""), str(b.get("sehir") or ""))
    if yol == "/api/yerelgorsel/kur":
        return yerel_gorsel_m().kur(str(b.get("kalite") or "") or None)
    if yol == "/api/yerelgorsel/sil":
        return {"ok": True, "silinen_mb": round(yerel_gorsel_m().sil() / 1e6)}
    if yol == "/api/guncelleme/ayar":
        return guncelleme_m().ayar_yaz(str(b.get("repo") or ""), str(b.get("jeton") or "") or None, str(b.get("dal")) if b.get("dal") is not None else None)
    if yol == "/api/guncelleme/kontrol":
        return guncelleme_m().kontrol()
    if yol == "/api/guncelleme/baslat":
        return guncelleme_m().guncelle_baslat()
    if yol == "/api/guncelleme/jeton-sil":
        guncelleme_m().jeton_sil()
        return {"ok": True}
    if yol == "/api/guncelleme/yeniden-baslat":
        guncelleme_m().yeniden_baslat()
        return {"ok": True}
    if yol == "/api/bulutdisk/kur":
        return bulut_disk_m().kur()
    if yol == "/api/bulutdisk/baglan":
        return bulut_disk_m().baglan_baslat(str(b.get("ad") or ""), str(b.get("tur") or ""))
    if yol == "/api/bulutdisk/klasorler":
        return {"klasorler": bulut_disk_m().klasorler(str(b.get("uzak") or ""))}
    if yol == "/api/bulutdisk/sil":
        bulut_disk_m().sil(str(b.get("ad") or ""))
        return {"ok": True}
    if yol == "/api/bulutdisk/onbellek-bosalt":
        return {"ok": True, "bosalan_mb": round(bulut_disk_m().onbellegi_bosalt() / 1e6, 1)}
    if yol == "/api/agir/derinlik-kur":
        return agir_derinlik_kur()
    if yol == "/api/karakter/olustur":
        k = karakter_m()
        return {"ok": True, "karakter": k.olustur(str(b.get("ad") or ""), str(b.get("veren") or ""), bool(b.get("onay")), k.b64_coz(b.get("boy_b64") or ""), k.b64_coz(b.get("portre_b64") or ""))}
    if yol == "/api/karakter/sil":
        karakter_m().sil(str(b.get("id") or ""))
        return {"ok": True}
    if yol == "/api/b-plani":
        return b_plani_ayarla(b)
    if yol.startswith("/api/gorsel/"):
        k = gorsel_k()
        gid = str(b.get("id") or "")
        if yol == "/api/gorsel/uret":
            seri = b.get("seri") if isinstance(b.get("seri"), dict) and b["seri"].get("id") else None
            if seri:
                seri = {"id": str(seri["id"])[:40], "sezon": int(seri.get("sezon") or 1), "bolum": int(seri.get("bolum") or 1)}
            istem, stil = str(b.get("istem") or ""), str(b.get("stil") or "") or None
            mdl = b.get("model") if isinstance(b.get("model"), dict) else None
            if mdl:   # dizi model seti: sabit istem eki ve serinin görsel stili (stil seçilmediyse)
                istem, sstil = seri_m().model_istemi(str(mdl.get("seri") or ""), str(mdl.get("id") or ""), istem)
                stil = stil or sstil
                seri = seri or {"id": str(mdl.get("seri"))[:40], "sezon": 1, "bolum": 1}
            boyut = k.BOYUTLAR.get(str(b.get("boyut") or ""), None)
            gen, yuk = boyut if boyut else (int(b.get("genislik") or 1024), int(b.get("yukseklik") or 576))
            return k.is_baslat(istem, stil, gen, yuk, int(b.get("adet") or 1),
                               int(b["tohum"]) if str(b.get("tohum") or "").strip() else None, int(b.get("adim") or 8), seri)
        if yol == "/api/gorsel/yeniden":
            return k.yeniden(gid)
        if yol == "/api/gorsel/onayla":
            return {"ok": True, "oge": k.onayla(gid)}
        if yol == "/api/gorsel/reddet":
            return {"ok": True, "oge": k.reddet(gid)}
        if yol == "/api/gorsel/sil":
            k.sil(gid)
            return {"ok": True}
        if yol == "/api/gorsel/not":
            return {"ok": True, "oge": k.not_yaz(gid, str(b.get("not") or ""))}
        if yol == "/api/gorsel/projeye":
            return {"ok": True, **k.projeye(gid, str(b.get("proje") or ""), str(b.get("format") or "ana"))}
    if yol == "/api/seri/olustur":
        return {"ok": True, "seri": seri_m().olustur(str(b.get("ad") or ""), str(b.get("tur") or "dizi"), str(b.get("aciklama") or ""), [str(x) for x in (b.get("karakterler") or [])],
                                                      str(b.get("stil") or ""), str(b.get("gorsel_stil") or ""))}
    if yol == "/api/seri/guncelle":
        kar = [str(x) for x in b["karakterler"]] if isinstance(b.get("karakterler"), list) else None
        return {"ok": True, "seri": seri_m().guncelle(str(b.get("id") or ""), b.get("ad"), b.get("aciklama"), b.get("stil"), b.get("gorsel_stil"), kar)}
    if yol == "/api/seri/bolum":
        return {"ok": True, "bolum": seri_m().bolum_ekle(str(b.get("seri") or ""), int(b.get("sezon") or 1), str(b.get("ad") or ""), str(b.get("ozet") or ""), True,
                                                          str(b.get("senaryo") or ""), [str(x) for x in (b.get("gorunenler") or [])])}
    if yol == "/api/seri/bolum/guncelle":
        return {"ok": True, "bolum": seri_m().bolum_guncelle(str(b.get("seri") or ""), int(b.get("sezon") or 1), int(b.get("bolum") or 1), b.get("ad"), b.get("ozet"), b.get("senaryo"),
                                                              [str(x) for x in b["gorunenler"]] if isinstance(b.get("gorunenler"), list) else None, b.get("durum"))}
    if yol == "/api/seri/model/ekle":
        return {"ok": True, "model": seri_m().model_ekle(str(b.get("seri") or ""), str(b.get("tur") or "karakter"), str(b.get("ad") or ""), str(b.get("aciklama") or ""), str(b.get("istem_eki") or ""))}
    if yol == "/api/seri/model/guncelle":
        return {"ok": True, "model": seri_m().model_guncelle(str(b.get("seri") or ""), str(b.get("id") or ""), b.get("ad"), b.get("aciklama"), b.get("istem_eki"))}
    if yol == "/api/seri/model/sil":
        seri_m().model_sil(str(b.get("seri") or ""), str(b.get("id") or ""))
        return {"ok": True}
    if yol == "/api/seri/model/gorsel":
        return {"ok": True, "model": seri_m().model_gorsel(str(b.get("seri") or ""), str(b.get("id") or ""), str(b.get("gorsel") or ""), bool(b.get("ana")), bool(b.get("kaldir")))}
    if yol == "/api/seri/ozet":
        return {"ok": True, "bolum": seri_m().ozet_yaz(str(b.get("seri") or ""), int(b.get("sezon") or 1), int(b.get("bolum") or 1), str(b.get("ozet") or ""))}
    if yol == "/api/depolama/liste":
        return {"liste": depolama_m().liste(str(b.get("uzak") or ""), int(b.get("derinlik") or 1))[:500]}
    if yol == "/api/depolama/indir":
        return depolama_m().indir(str(b.get("uzak") or ""), str(b.get("proje") or ""))
    if yol == "/api/depolama/yukle":
        return depolama_m().yukle(str(b.get("dosya") or ""), str(b.get("uzak") or ""), bool(b.get("onay")))
    if yol == "/api/depolama/paylas":
        return depolama_m().paylas(str(b.get("dosya") or ""), bool(b.get("onay")))
    if yol == "/api/baglayici/kesfet":
        sid = b.get("saglayici", "")
        if sid not in ortak().katalog()["saglayicilar"]:
            raise ValueError("bilinmeyen sağlayıcı")
        try:
            return kesif_m().kesfet(sid)
        except Exception as e:  # noqa: BLE001  (kesif.py kendi ortak kopyasını yükler: istisna sınıfı farklı örnek olabilir, ada bak)
            if type(e).__name__ in ("IzinHatasi", "AgHatasi"):
                raise ValueError(ortak().maskele(str(e))) from None
            raise
    if yol == "/api/saglayici/dogrula":
        sid = slug(str(b.get("id") or ""))
        m = b.get("manifest")
        if isinstance(m, str):
            try:
                m = json.loads(m)
            except ValueError as e:
                raise ValueError(f"manifest geçerli JSON değil: {e}") from None
        ayar().dogrula_manifest(sid, m)
        return {"ok": True, "id": sid}
    if yol == "/api/profil/disa-aktar":
        sifre = str(b.get("sifre") or "")
        if not sifre and not b.get("sifresiz"):
            raise ValueError("parola gir (en az 8 karakter) ya da 'şifresiz' kutusunu işaretle")
        if sifre and len(sifre) < 8:
            raise ValueError("parola en az 8 karakter olmalı")
        return profil_m().disa_aktar(None, sifre or None, bool(b.get("anahtarlar", True)), bool(b.get("arsiv", True)), bool(b.get("ornekler", True)),
                                     bool(b.get("iyilestirilmis")), bool(b.get("projeler")))
    if yol == "/api/profil/ozet":
        p = yedek_dosya(str(b.get("ad") or ""))
        return {"ozet": profil_m().ozet(str(p), str(b.get("sifre") or "") or None)}
    if yol == "/api/profil/ice-aktar":
        p = yedek_dosya(str(b.get("ad") or ""))
        return profil_m().ice_aktar(str(p), str(b.get("sifre") or "") or None, bool(b.get("kuru")), "atla" if b.get("cakisma") == "atla" else "uzerine")
    if yol == "/api/ses-metin":
        p = proje_kontrol(b.get("proje", ""))
        degis = b.get("degisiklik") or {}
        if not isinstance(degis, dict) or not all(isinstance(v, list) for v in degis.values()):
            raise ValueError("degisiklik {satır: [metinler]} olmalı")
        return modul("yst_sesd", "araclar/ses_duzenle.py").uygula(p.name, degis, b.get("format", "ana"))
    return None


# ------------------------------------------------------------------ üretim isteği
PLATFORM_AD = None


def uret_hazirla(b: dict) -> dict:
    """Panelin 'Üret' isteğini doğrula; proje adı, biçimler, ayar yaması, sihirbaz özeti ve uretim.json içeriğini hazırla (proje oluşturmadan)."""
    a = ayar()
    cz = a.coz()
    prompt = str(b.get("prompt", "")).strip()
    if len(prompt) < 8:
        raise ValueError("prompt çok kısa: ne istediğini bir iki cümleyle anlat")
    prompt = prompt[:4000]
    plats = [p for p in (b.get("platformlar") or []) if p in cz["platformlar"]]
    if not plats:
        raise ValueError("en az bir platform seç")
    formatlar = []
    for p in plats:
        f = cz["platformlar"][p]["format"]
        if f not in formatlar:
            formatlar.append(f)
    ad = slug(str(b.get("ad") or " ".join(prompt.split()[:5])))[:40] or "video"
    taban, n = ad, 2
    while (ROOT / "projeler" / ad).exists():
        ad = f"{taban}-{n}"
        n += 1
    ses = b.get("seslendirme") or {}
    gor = b.get("gorsel_uret") or {}
    mk = b.get("marka") or {}
    sure = str(b.get("sure") or "").strip()
    if sure and not re.fullmatch(r"\d{1,3}", sure):
        raise ValueError("süre saniye olarak sayı olmalı (boş bırakabilirsin)")
    klon = bool(ses.get("klon"))
    if klon:  # "Sesimi klonla": yerel Pocket TTS + kayıtlı örnek; panelde uyarı kabul edilmeden gelmez
        kd = klon_durum()
        if not ses.get("klon_onay"):
            raise ValueError("ses klonlama uyarısı kabul edilmedi")
        if not kd["hazir"]:
            raise ValueError("ses klonlama bileşeni kurulu değil: Ayarlar → Sistem → Ses klonlama → Kur")
        if not kd["ornek"]:
            raise ValueError("'Sesimi klonla' seçili ama ses örneği yok: promptu konuşarak yaz ya da 'Sesimi kaydet' düğmesini kullan")
        ses = {"acik": True, "saglayici": "ema", "motor": "pocket-tr", "klon": True, "klon_yol": "klon/ornek.wav", "klon_onay": time.strftime("%Y-%m-%d %H:%M:%S")}
    o = ortak()
    bulut_kullan = []
    if ses.get("acik") and ses.get("saglayici") and not o.katalog()["saglayicilar"].get(ses["saglayici"], {}).get("yerel", True):
        bulut_kullan.append(("ses", ses["saglayici"]))
    if gor.get("acik"):
        if len(str(gor.get("tarif") or "").strip()) < 5:
            raise ValueError("görsel üretimi açık: karakter/görsel tarifini yaz")
        sag = gor.get("saglayici") or cz["uretim"]["gorsel_uret"]["saglayici"]
        gor["saglayici"] = sag
        if sag == YEREL_GORSEL_ID:   # yerel model: bulut izni/anahtar gerekmez, kurulu olmalı
            if not b.get("taslak") and not gorsel_durum()["kurulu"]:
                raise ValueError("Yerel Z-Image-Turbo kurulu değil: Ayarlar → Servisler ve modeller → Yerel görsel üretim → Kur")
            gor["yerel"] = True
        else:
            bulut_kullan.append(("gorsel", sag))
    sorunlar = []
    for tur, sid in bulut_kullan:
        d = o.baglayici_durumu(sid)
        if not d["etkin"]:
            sorunlar.append(f"{d['ad']} KAPALI (Ayarlar → Bağlayıcılar'dan aç)")
        elif d["anahtar_adi"] and not d["anahtar_var"]:
            sorunlar.append(f"{d['ad']} için API anahtarı yok (Ayarlar → Bağlayıcılar)")
    if sorunlar:
        raise ValueError("; ".join(sorunlar))
    if bulut_kullan and not b.get("bulut_izni"):
        raise ValueError("ücretli/bulut servis seçili: 'Bu projede verilerimin bu servise gönderilmesine izin veriyorum' kutusunu işaretle")
    ajan_ov = {}
    for k, v in (b.get("ajanlar") or {}).items():
        if k in cz["ajanlar"] and isinstance(v, dict):
            ajan_ov[k] = {x: v[x] for x in ("model", "effort", "calisma_ortami") if v.get(x)}
    ayar_yama = {"izin": {"bulut": bool(bulut_kullan and b.get("bulut_izni"))},
                 "uretim": {"seslendirme": {"acik": bool(ses.get("acik")), "saglayici": ses.get("saglayici") or cz["uretim"]["seslendirme"]["saglayici"]},
                            "gorsel_uret": {"acik": bool(gor.get("acik")), "saglayici": gor.get("saglayici") or cz["uretim"]["gorsel_uret"]["saglayici"]},
                            "platformlar": plats, "arsivden_bul": bool(b.get("arsivden_bul"))}}
    if ajan_ov:
        ayar_yama["ajanlar"] = ajan_ov
    marka_secim = {"kit": mk.get("kit") or cz["uretim"].get("marka_kiti") or "varsayilan",
                   **{k: bool(mk.get(k)) for k in ("intro", "outro", "filigran", "iletisim", "kapak_filigran")}}
    pn = {p: cz["platformlar"][p]["ad"] for p in plats}
    sihirbaz = {
        "seslendirme": ("Kapalı" if not ses.get("acik") else
                        ("Açık: KULLANICININ KENDİ SESİ klonlanacak (yerel Pocket TTS; plan'da \"motor\": \"pocket-tr\", \"klon\": \"klon/ornek.wav\"; kullanıcı panelde onayladı)" if klon
                         else f"Açık: {ses.get('saglayici') or 'ema'}")),
        "gorsel_uret": ("Kapalı" if not gor.get("acik") else f"Açık: {gor['saglayici']}"),
        "gorsel_tarif": str(gor.get("tarif") or "")[:1500] if gor.get("acik") else "",
        "sure": (f"{sure} sn" if sure else "prompttan al; yoksa Claude önersin"),
        "platformlar": ", ".join(pn.values()),
        "marka_ozet": f"{marka_secim['kit']}: intro {'açık' if marka_secim['intro'] else 'kapalı'}, outro {'açık' if marka_secim['outro'] else 'kapalı'}, "
                      f"filigran {'açık' if marka_secim['filigran'] else 'kapalı'}, iletişim bilgisi {'görünsün' if marka_secim['iletisim'] else 'görünmesin'}",
        "arsivden_bul": "evet (prompttaki yıl/anahtar kelimelerden)" if b.get("arsivden_bul") else "hayır",
        "bulut_izni": "verildi" if ayar_yama["izin"]["bulut"] else "yok (yalnızca yerel araçlar)",
        "notlar": str(b.get("notlar") or "")[:1500],
    }
    uretim = {"prompt": prompt, "platformlar": plats, "formatlar": formatlar, "seslendirme": ses, "gorsel_uret": gor, "sure": sure, "marka": marka_secim,
              "arsivden_bul": bool(b.get("arsivden_bul")), "olusturma": time.strftime("%Y-%m-%d %H:%M:%S")}
    bp = b.get("b_plani") or {}
    if bp.get("acik"):  # B planı: kişi çekime gidemedi → dijital sunucu + gerçek mekân görüntüleri
        k = karakter_m()
        ok_, eksik = k.hazir(str(bp.get("karakter") or ""))
        if not ok_:
            raise ValueError("B planı için karakter hazır değil: " + "; ".join(eksik) + " (Ayarlar → Karakterler)")
        if bp.get("uretken") and not b.get("bulut_izni"):
            raise ValueError("üretken (bulut) ikiz seçili: bulut iznini işaretle")
        uretim["b_plani"] = {"karakter": k.slug(bp["karakter"]), "etiket": bool(bp.get("etiket")), "etiket_metin": str(bp.get("etiket_metin") or "Dijital sunum")[:60], "uretken": bool(bp.get("uretken"))}
        sihirbaz["notlar"] = (sihirbaz["notlar"] + "\n" if sihirbaz["notlar"] else "") + (
            f"B PLANI (acil durum): kişi çekime gidemedi. Karakter: {uretim['b_plani']['karakter']}; gerçek mekân görüntüleri + dijital sunucu; "
            f"etiket {'AÇIK' if uretim['b_plani']['etiket'] else 'kapalı'}; üretken bulut ikiz {'denenecek' if uretim['b_plani']['uretken'] else 'yok (yalnızca yerel/kodla)'}.")[:1500]
    ars = b.get("ara_sahne") or {}
    if ars.get("stil"):  # ara sahne şablonu seçildi: orkestratöre açık talimat (kaynak çizim yüklendikten sonra araçla üretilir)
        if ars["stil"] not in kalem_m().STILLER:
            raise ValueError("geçersiz ara sahne stili")
        uretim["ara_sahne"] = {"sablon": "kalem-cizim", "stil": ars["stil"]}
        sihirbaz["notlar"] = (sihirbaz["notlar"] + "\n" if sihirbaz["notlar"] else "") + (
            f"ARA SAHNE İSTENDİ (kalem-cizim, stil: {ars['stil']}): kaynaktaki bir çizimi (DWG/SVG), resmi ya da bir videonun ilk karesini kalemle çizilen ara sahneye çevir: "
            f"`python sistem/araclar/kalem_cizim.py projeler/{ad}/kaynak/<belge|foto|video>/<dosya> -o projeler/{ad}/kaynak/video/ara-sahne.mp4 --stil {ars['stil']}`; "
            "resimde `--gecis --bekle 2` çizim bitince gerçek resme dönüştürür, video verilirse çizim gerçeğe dönüşüp video kesintisiz devam eder "
            "(DWG yalnızca Windows'ta okunur; olmazsa SVG iste). Videoyu uygun bir yere ara sahne olarak yerleştir; sonucu kareye bakarak doğrula.")[:1500]
    return {"ad": ad, "prompt": prompt, "formatlar": formatlar, "ayar_yama": ayar_yama, "marka": marka_secim, "sihirbaz": sihirbaz, "uretim": uretim}


def claude_ek(proje: str | None, gorev: str | None) -> tuple[str, list[str]]:
    """Claude komutu için: (--mcp-config argümanı, cmd'ye eklenecek ortam satırları). MCP yoksa boş."""
    arg, satir = "", []
    try:
        yol = mcp().olustur()
        if yol:
            arg = f' --mcp-config "{yol}"'
            satir.append(f'for /f "usebackq delims=" %%i in (`""{VENV_PY}" "{SISTEM / "baglayici" / "mcp.py"}" ortam"`) do %%i')
    except Exception:  # noqa: BLE001
        pass
    return arg, satir


# ------------------------------------------------------------------ dikte (yerel konuşma→yazı)
DIKTE_EN_COK = 25_000_000  # bayt (~10 dk opus)


def dikte_durum():
    b = bilesen_m()
    installed = [k for k in ("small", "base", "tiny", "medium", "large-v3-turbo", "large-v3") if b._repo_kurulu(b.WHISPER[k][0])]
    ready = bool(installed and b._paketler().get("faster_whisper"))
    return {"hazir": ready, "model": installed[0] if installed else None,
            "mesaj": "Hazır" if ready else "Konuşma tanıma hazır değil. Ayarlar → Sistem → Konuşma tanıma modelini kurun."}


def dikte_coz(veri: bytes) -> dict:
    """Tarayıcıdan gelen ses kaydını YEREL faster-whisper ile yazıya çevirir. Ses hiçbir yere gönderilmez ve iş bitince silinir."""
    import os
    import shutil
    import tempfile

    if not (2_000 <= len(veri) <= DIKTE_EN_COK):
        raise ValueError("ses kaydı çok kısa ya da çok uzun (en çok ~10 dakika)")
    check = dikte_durum()
    if not check["hazir"]:
        raise ValueError(check["mesaj"])
    tmp = Path(tempfile.mkdtemp(prefix="dikte-", dir=str(ORTAM / "yerel") if (ORTAM / "yerel").is_dir() else None))
    try:
        ses, cikti = tmp / "kayit.webm", tmp / "yazi.json"
        ses.write_bytes(veri)
        cmd = [str(VENV_PY), str(SISTEM / "araclar" / "yazi_cikar.py"), str(ses), "-o", str(cikti), "--dil", "tr", "--model", check["model"], "--cpu", "--local-only"]
        duz = ROOT / "kimlik" / "duzeltme.json"
        if duz.is_file():
            cmd += ["--duzeltme", str(duz)]  # özel adlar (Örnekoğlu…) için bul-değiştir
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=420, creationflags=ses_temizle_m().NW,
                           env={**os.environ, **__import__("yol").kapsama()})
        if r.returncode != 0 or not cikti.is_file():
            raise RuntimeError("yazıya çevrilemedi: " + ((r.stderr or r.stdout).strip().splitlines() or ["bilinmeyen hata"])[-1][:200])
        j = json.loads(cikti.read_text(encoding="utf-8"))
        metin = " ".join(c["metin"] for c in j["cumleler"]).strip()
        kel = j["kelimeler"]
        konusma = (kel[-1]["bitis"] - kel[0]["baslangic"]) if kel else 0
        dur = sum(1 for a, b in zip(kel, kel[1:]) if b["baslangic"] - a["bitis"] > 0.8)
        return {"metin": metin, "sure": j["sure"], "kelime": len(kel), "kelime_dk": round(len(kel) / konusma * 60) if konusma > 2 else None,
                "uzun_duraklama": dur, "dil": j["dil"], "cihaz": j["cihaz"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
