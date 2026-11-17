#!/usr/bin/env python3
"""Arka plan kurulumu: kurulum bitip panel açıldıktan SONRA, kullanıcıyı bekletmeden tamamlanan ağır parçalar.

Kurulum yalnızca paneli açmaya yetecek kadarını yapar (Kurgu, çekirdek Python paketleri, Remotion, ffmpeg, küçük temel dosyalar).
Geri kalan ağır işler bu kuyrukta, panel açıkken ve sırayla yapılır; panel her an ne indiğini, neyin sırada olduğunu ve her parçanın NE İŞE YARADIĞINI gösterir:

  1. temel dosyalar (Real-ESRGAN modeli, DWG aracı, referans belgeleri) ve rclone (bulut disk programı)
  2. PyTorch (işlemci sürümü)           yapay zekâ motoru: seslendirme, foto iyileştirme, ses klonlama, mekân gezisi
  3. yapay zekâ paketleri               EMA, Real-ESRGAN çalıştırıcı, Pocket TTS, derinlik (torch'a bağlı olanlar)
  4. EMA ses modeli · konuşma tanıma modeli · ses klonlama modeli · derinlik modeli (Hugging Face)

İSTEĞE BAĞLI (kendiliğinden inmez): müzik + ses efektleri; NVIDIA için GPU hızlandırma (panel önerir, kullanıcı karar verir).

  python sistem/araclar/arka_indirme.py durum      özet + kuyruk (JSON)
  python sistem/araclar/arka_indirme.py baslat     şimdi başlat (atlama bayrağını da kaldırır)
  python sistem/araclar/arka_indirme.py ses        müzik + ses efektlerini de indir (isteğe bağlı)
  python sistem/araclar/arka_indirme.py atla       çalışanı durdur ve kendiliğinden yeniden denemeyi kapat (baslat ile geri açılır)
  python sistem/araclar/arka_indirme.py calis      (iç kullanım / elle) kuyruğu bu süreçte yürütür

Davranış:
- Panel açılışında ve 10 dk'da bir `otomatik()` çağrılır: eksik varsa ve kullanıcı atlamadıysa arka planda başlatır.
- Sunucu hız sınırı uygularsa (429) o parça ATLANIR, kuyruk bloke olmaz; `YENIDEN_DENE_SN` sonra otomatik yeniden denenir. PyTorch inmediyse ona bağlı paketler denenmez.
- Durum dosyası: sistem/ortam/yerel/arka_indirme.json (yalnızca bu süreç yazar). Atlama bayrağı: sistem/ortam/yerel/arka_indirme.atla (kullanıcı kararı).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(os.environ.get("YST_ARKA_KOK") or Path(__file__).resolve().parents[2])
SISTEM = ROOT / "sistem"
YEREL = SISTEM / "ortam" / "yerel"
DURUM = YEREL / "arka_indirme.json"
ATLA = YEREL / "arka_indirme.atla"
GUNLUK = YEREL / "arka_indirme.log"
SES_ISTEMIYOR = YEREL / "arka_indirme.ses_istemiyor"   # kullanıcı "gerek yok" dedi: öneri bandı gösterilmez (panelden yine indirilebilir)
GPU_ISTEMIYOR = YEREL / "arka_indirme.gpu_istemiyor"   # kullanıcı GPU hızlandırma önerisini kapattı
SES_TURLER = ("sfx", "muzik")                           # isteğe bağlı: kendiliğinden inmez
TEMEL_TURLER = ("model", "arac", "referans")           # kurulumda inemeyenler kendiliğinden tamamlanır
VENV_PY = SISTEM / "ortam" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
NW = 0x08000000 if os.name == "nt" else 0
DETACHED = (0x00000008 | 0x00000200 | 0x08000000) if os.name == "nt" else 0
NABIZ_SN = 120            # bu kadar süredir nabız yoksa süreç ölü sayılır
YENIDEN_DENE_SN = 3600    # sorunlu çalıştırmadan sonra kendiliğinden yeniden deneme aralığı
AD = {"muzik": "müzik", "sfx": "ses efektleri", "model": "model", "arac": "DWG aracı", "referans": "referans belgeleri"}
CPU_INDEKS = "https://download.pytorch.org/whl/cpu"
ML_PAKETLER = ("ema_lightning", "spandrel", "transformers", "pocket_tts_turkish")   # gereksinim-ml.txt: torch'a bağlı paketler

# Kuyruk (sıra = indirme sırası). tur: varlik (varlik.py kayıtları) | pip-torch | pip-ml | hf (Hugging Face deposu). dep: ona bağlı (o inmediyse denenmez).
KUYRUK = (
    {"id": "temel", "tur": "varlik", "ad": "Temel dosyalar", "gb": 0.1,
     "ne": "Real-ESRGAN foto iyileştirme modeli, DWG çizim aracı (LibreDWG) ve ajan referans belgeleri.",
     "gerek": "fotoğraf iyileştirme, DWG çizimlerini içe aktarma"},
    {"id": "rclone", "tur": "rclone", "ad": "rclone (bulut disk programı)", "gb": 0.06,
     "ne": "Google Drive, OneDrive ve Dropbox'taki arşivini (müzik, resim, video, dosya) bilgisayara indirmeden, salt okunur bağlar.",
     "gerek": "bulut disk arşivi"},
    {"id": "pytorch", "tur": "pip-torch", "ad": "PyTorch (yapay zekâ motoru, işlemci sürümü)", "gb": 0.5,
     "ne": "Yapay zekâ modellerinin çalıştığı altyapı. İşlemci sürümü küçüktür ve her şeyi çalıştırır; NVIDIA kartın varsa GPU hızlandırma isteğe bağlı eklenebilir.",
     "gerek": "Türkçe seslendirme, foto iyileştirme, ses klonlama, mekân gezisi"},
    {"id": "paketler", "tur": "pip-ml", "ad": "Yapay zekâ paketleri", "gb": 0.3, "dep": "pytorch",
     "ne": "EMA Lightning (Türkçe seslendirme), Real-ESRGAN çalıştırıcı, Pocket TTS (ses klonlama) ve derinlik modeli için Python paketleri.",
     "gerek": "Türkçe seslendirme, foto iyileştirme, ses klonlama, mekân gezisi"},
    {"id": "model-ema", "tur": "hf", "ad": "Türkçe seslendirme modeli (EMA Lightning)", "gb": 0.45, "repo": "canberkkkkkk/ema-lightning",
     "ne": "Varsayılan Türkçe ses. Hesapsız ve ücretsiz, tamamen bu bilgisayarda çalışır.",
     "gerek": "videoların seslendirmesi"},
    {"id": "model-whisper", "tur": "hf", "ad": "Konuşma tanıma modeli (faster-whisper small)", "gb": 0.5, "repo": "Systran/faster-whisper-small",
     "ne": "Konuşmayı yazıya çevirir: prompt'u mikrofonla söylemek (🎤), altyazı zamanlaması, ham videoda sessizlik/tekrar kesme.",
     "gerek": "🎤 ile dikte, altyazı"},
    {"id": "model-klon", "tur": "hf", "ad": "Ses klonlama modeli (Pocket TTS Turkish)", "gb": 0.5, "repo": "wite-tech/pocket-tts-turkish",
     "ne": "3-10 sn'lik örnek sesinden kendi sesinle seslendirme ve 6 hazır ses (duygu etiketli). CC-BY-4.0: atıf gerekir.",
     "gerek": "sesini klonlama, hazır sesler"},
    {"id": "model-derinlik", "tur": "hf", "ad": "Derinlik modeli (Depth Anything V2 Small)", "gb": 0.1, "repo": "depth-anything/Depth-Anything-V2-Small-hf", "ev": "derinlik",
     "ne": "Tek fotoğraftan derinlik haritası çıkarır: mekân gezisi (parallax) videosunda yakın/uzak ayrımı.",
     "gerek": "mekân gezisi videosu"},
)
SES_KALEM = {"id": "ses", "ad": "Müzik ve ses efektleri (isteğe bağlı)", "gb": 0.13, "opsiyonel": True,
             "ne": "Videolara atmosfer katan atıfsız (CC0 / kamu malı) müzik parçaları ve 300+ ses efekti. Kendiliğinden inmez; istersen indir.",
             "gerek": "videolarda müzik ve ses efekti"}

_MOD: dict = {}


def _mod(ad: str, yol: Path):
    if ad not in _MOD:
        sp = importlib.util.spec_from_file_location(ad, yol)
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _MOD[ad] = m
    return _MOD[ad]


def _varlik():
    return _mod("yst_varlik_ark", SISTEM / "varlik" / "varlik.py")


def _bulut():
    sys.path.insert(0, str(SISTEM / "araclar"))
    return _mod("yst_bulut_ark", SISTEM / "araclar" / "bulut_disk.py")


def _bilesen():
    sys.path.insert(0, str(SISTEM / "araclar"))
    return _mod("yst_bilesen_ark", SISTEM / "araclar" / "bilesen.py")


def _ortam() -> dict:
    sys.path.insert(0, str(SISTEM / "araclar"))
    import yol
    e = dict(os.environ, PYTHONUTF8="1")
    e.update(yol.kapsama())
    return e


# ------------------------------------------------------------------ durum
def _canli_mi(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            kod = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(kod))
            ctypes.windll.kernel32.CloseHandle(h)
            return kod.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _oku() -> dict:
    try:
        return json.loads(DURUM.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _yaz(d: dict) -> None:
    YEREL.mkdir(parents=True, exist_ok=True)
    gecici = DURUM.with_suffix(".tmp")
    gecici.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.replace(gecici, DURUM)


def _site_dizinleri() -> list[Path]:
    v = SISTEM / "ortam" / "venv"
    return list(v.glob("Lib/site-packages")) + list(v.glob("lib/python*/site-packages"))


def paket_var(ad: str) -> bool:
    """Venv'de paket kurulu mu? (içe aktarmadan, dist-info klasör adından: anında)"""
    for kok in _site_dizinleri():
        if any(kok.glob(ad.replace("-", "_") + "-*.dist-info")):
            return True
    return False


def torch_var() -> bool:
    return paket_var("torch")


def paketler_var() -> bool:
    return all(paket_var(p) for p in ML_PAKETLER)


def repo_var(repo: str, ev: str | None) -> bool:
    try:
        if not os.environ.get("HF_HOME") and not os.environ.get("HF_HUB_CACHE"):   # panel/arka süreç dışından (komut satırı) çağrıda da stüdyo önbelleğine bak
            os.environ["HF_HOME"] = _ortam()["HF_HOME"]
        b = _bilesen()
        return bool(b._repo_kurulu(repo, b.DEPTH_EV if ev == "derinlik" else None))
    except Exception:  # noqa: BLE001
        return False


def _varlik_eksik(turler: tuple) -> dict:
    """{tur: adet} eksik varlık (dosya var mı bakılır; sha256 doğrulaması indirme sırasında yapılır)."""
    sonuc: dict = {}
    try:
        c = _varlik().baglan()
        for r in c.execute("SELECT * FROM varlik"):
            if r["tur"] not in turler or r["kaynak_tur"] == "yerel":
                continue   # yerel: başka kaynaktan getirilemez
            hedef = ROOT / r["hedef"]
            yok = not (hedef.is_dir() and any(hedef.iterdir())) if r["kaynak_tur"] in ("zip-url", "git") else not hedef.is_file()
            if yok:
                sonuc[r["tur"]] = sonuc.get(r["tur"], 0) + 1
        c.close()
    except Exception:  # noqa: BLE001
        pass
    return sonuc


def kalem_eksik(k: dict) -> bool:
    """Bu kuyruk kalemi şu an eksik mi?"""
    t = k["tur"]
    if t == "varlik":
        return bool(_varlik_eksik(TEMEL_TURLER))
    if t == "rclone":
        try:
            return not _bulut().rclone()
        except Exception:  # noqa: BLE001
            return True
    if t == "pip-torch":
        return not torch_var()
    if t == "pip-ml":
        return not paketler_var()
    return not repo_var(k["repo"], k.get("ev"))


_EKSIK = {"t": 0.0, "v": None}


def eksikler(taze: bool = False) -> dict:
    """{kalem kimliği ya da varlık türü: adet} eksikler (müzik/ses efekti türleri dâhil: 'muzik', 'sfx'). 20 sn önbellekli."""
    if not taze and _EKSIK["v"] is not None and time.time() - _EKSIK["t"] < 20:
        return _EKSIK["v"]
    sonuc: dict = {}
    for k in KUYRUK:
        if k["tur"] == "varlik":
            sonuc.update(_varlik_eksik(TEMEL_TURLER))
        elif kalem_eksik(k):
            sonuc[k["id"]] = 1
    sonuc.update(_varlik_eksik(SES_TURLER))
    _EKSIK.update(t=time.time(), v=sonuc)
    return sonuc


def ses_ozeti() -> dict:
    """İsteğe bağlı müzik + ses efektleri: kaç dosya eksik, ~kaç MB, kullanıcı 'gerek yok' dedi mi."""
    n = 0
    mb = 0.0
    try:
        c = _varlik().baglan()
        for r in c.execute("SELECT * FROM varlik WHERE tur IN ('sfx','muzik')"):
            if r["kaynak_tur"] == "yerel":
                continue
            hedef = ROOT / r["hedef"]
            yok = not (hedef.is_dir() and any(hedef.iterdir())) if r["kaynak_tur"] in ("zip-url", "git") else not hedef.is_file()
            if yok:
                n += 1
                mb += (r["boyut"] or 0) / 1e6
        c.close()
    except Exception:  # noqa: BLE001
        pass
    if n and mb < 60:
        mb += 68   # sfx-wyzowl (git klasörü) boyutu veritabanında yok: ölçülen ~67 MB
    return {"eksik": n, "boyut_mb": round(mb), "istemiyor": SES_ISTEMIYOR.exists()}


def ses_istemiyor(deger: bool = True) -> dict:
    YEREL.mkdir(parents=True, exist_ok=True)
    if deger:
        SES_ISTEMIYOR.write_text("gerek yok\n", encoding="utf-8")
    else:
        SES_ISTEMIYOR.unlink(missing_ok=True)
    return durum()


def gpu_oneri() -> dict:
    """NVIDIA ekran kartı var ama PyTorch işlemci sürümünde mi? (dist-info klasör adından: paketi içe aktarmadan, anında)"""
    import shutil
    try:
        ts = _bilesen().torch_surum()
        var = bool(shutil.which("nvidia-smi"))
        return {"oner": bool(var and ts and "+cu" not in ts and not GPU_ISTEMIYOR.exists()), "nvidia": var, "torch": ts, "boyut_gb": 2.7}
    except Exception:  # noqa: BLE001
        return {"oner": False, "nvidia": False, "torch": "", "boyut_gb": 2.7}


def gpu_istemiyor() -> dict:
    YEREL.mkdir(parents=True, exist_ok=True)
    GPU_ISTEMIYOR.write_text("gerek yok\n", encoding="utf-8")
    return durum()


def son_ses() -> bool:
    """Son çalıştırma müzik/ses efektlerini de kapsıyor muydu (Şimdi dene aynı kapsamla yeniden dener)."""
    return bool(_oku().get("ses"))


def kuyruk(d: dict, calisiyor: bool, ses: dict) -> list[dict]:
    """Arayüz için kuyruk: her kalemin durumu (hazir | iniyor | sirada | sorun | istege-bagli), ne işe yaradığı ve boyutu."""
    kalemler = d.get("kalemler") or {}
    simdiki = d.get("simdiki") or ""
    cikti = []
    for k in KUYRUK:
        eksik = kalem_eksik(k)
        kayit = kalemler.get(k["id"]) or {}
        if not eksik:
            durum_ = "hazir"
        elif calisiyor and simdiki == k["id"]:
            durum_ = "iniyor"
        elif kayit.get("durum") in ("hata", "atlandi"):   # bu çalıştırmada denendi ve olmadı (kuyruk başka parçayla sürüyor olsa bile)
            durum_ = "sorun"
        else:
            durum_ = "sirada"
        satir = {"id": k["id"], "ad": k["ad"], "ne": k["ne"], "gerek": k["gerek"], "gb": k["gb"], "durum": durum_, "mesaj": kayit.get("mesaj", "") if durum_ == "sorun" else ""}
        if durum_ == "iniyor":
            satir["gecen_sn"] = int(time.time() - float(kayit.get("bas") or time.time()))
            if k["tur"] == "hf":
                try:
                    b = _bilesen()
                    satir["indi_mb"] = round(b._repo_boyut(k["repo"], b.DEPTH_EV if k.get("ev") == "derinlik" else None) / 1e6)
                except Exception:  # noqa: BLE001
                    pass
        cikti.append(satir)
    s = dict(SES_KALEM)
    s["durum"] = "iniyor" if ses.get("iniyor") else ("hazir" if not ses.get("eksik") else "istege-bagli")
    s["gb"] = round(ses.get("boyut_mb", 0) / 1000, 2) or s["gb"]
    s["mesaj"] = ses.get("sorun", "")
    if s["durum"] == "iniyor":
        s["gecen_sn"] = int(time.time() - float((kalemler.get("ses") or {}).get("bas") or time.time()))
    cikti.append(s)
    return cikti


def durum(taze: bool = False) -> dict:
    d = _oku()
    calisiyor = bool(d.get("calisiyor")) and _canli_mi(int(d.get("pid") or 0)) and time.time() - float(d.get("nabiz") or 0) < NABIZ_SN
    atlandi = ATLA.exists()
    ek = {k: v for k, v in eksikler(taze).items() if k not in SES_TURLER}   # kendiliğinden inenler (ses/müzik ayrı: ses_ozeti)
    toplam_eksik = sum(ek.values())
    ses = ses_ozeti()
    ses["iniyor"] = calisiyor and bool(d.get("ses"))
    sonuc0 = d.get("sonuc") or {}
    ses["sorun"] = next((str(v).replace("ATLANDI: ", "").replace("HATA: ", "")[:140] for k, v in sonuc0.items()
                         if k.startswith(("muzik-", "sfx-")) and not str(v).startswith("indirildi")), "")
    sonuc = sonuc0
    sorunlu = {k: v for k, v in sonuc.items() if not str(v).startswith("indirildi")}
    if calisiyor:
        kod = "calisiyor"
    elif toplam_eksik == 0:
        kod = "tamam"
    elif atlandi:
        kod = "atlandi"
    elif sorunlu:
        kod = "sorun"
    else:
        kod = "bekliyor"
    adlar = ", ".join(next((k["ad"] for k in KUYRUK if k["id"] == t), AD.get(t, t)) for t in ek)
    simdiki_ad = next((k["ad"] for k in KUYRUK if k["id"] == d.get("simdiki")), "")
    if kod == "calisiyor":
        ozet = f"{simdiki_ad or 'Dosyalar'} iniyor ({d.get('sira', 0) + 1}/{d.get('toplam', 0)}). Bu sırada paneli kullanmaya devam edebilirsin."
    elif kod == "sorun":
        neden = next((str(v) for v in sorunlu.values()), "")
        neden = neden.replace("ATLANDI: ", "").replace("HATA: ", "")[:140]
        ozet = f"İnemeyen parçalar var: {neden}. Panel kendiliğinden yeniden dener; istersen şimdi dene ya da atla."
    elif kod == "atlandi":
        ozet = f"Arka plan kurulumu atlandı ({adlar}). İstediğinde başlat; ilgili özellik ilk kullanımda zaten kendi dosyasını indirmeyi dener."
    elif kod == "bekliyor":
        ozet = f"Sırada: {adlar}."
    else:
        ozet = "Gerekli her şey hazır."
    return {"gpu": gpu_oneri(), "ses": ses, "kod": kod, "calisiyor": calisiyor, "atlandi": atlandi, "eksik": ek, "eksik_toplam": toplam_eksik, "sira": d.get("sira", 0), "toplam": d.get("toplam", 0),
            "simdiki": d.get("simdiki", ""), "sonuc": sonuc, "bitis": d.get("bitis"), "ozet": ozet, "kuyruk": kuyruk(d, calisiyor, ses),
            "sonraki_deneme_sn": max(0, int(YENIDEN_DENE_SN - (time.time() - float(d.get("bitis") or 0)))) if kod == "sorun" else 0}


# ------------------------------------------------------------------ denetim (panel/komut satırı)
def baslat(zorla: bool = True, ses: bool = False) -> dict:
    """Arka plan kurulumunu ayrı, konsolsuz bir süreçte başlatır. zorla=True: kullanıcının 'atla' kararını kaldırır. ses=True: müzik + ses efektlerini de indirir
    (kullanıcı isteğiyle; kendiliğinden hiç başlatılmaz)."""
    if zorla:
        ATLA.unlink(missing_ok=True)
    if ses:
        SES_ISTEMIYOR.unlink(missing_ok=True)
    d = durum(taze=True)
    if d["calisiyor"]:
        return {"ok": False, "mesaj": "zaten çalışıyor", **d}
    if d["eksik_toplam"] == 0 and not (ses and d["ses"]["eksik"]):
        return {"ok": True, "mesaj": "indirilecek bir şey yok", **d}
    YEREL.mkdir(parents=True, exist_ok=True)
    py = VENV_PY if VENV_PY.exists() else Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    if os.name == "nt" and pyw.exists():
        py = pyw
    log = open(GUNLUK, "a", encoding="utf-8", buffering=1)
    log.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} başladı ===\n")
    ek = {"creationflags": DETACHED} if os.name == "nt" else {"start_new_session": True}
    p = subprocess.Popen([str(py), str(Path(__file__).resolve()), "calis"] + (["ses"] if ses else []), cwd=str(ROOT), env=_ortam(), stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, **ek)
    _yaz({"calisiyor": True, "pid": p.pid, "bas": time.time(), "nabiz": time.time(), "sira": 0, "toplam": 0, "simdiki": "", "sonuc": {}, "kalemler": {}, "ses": bool(ses)})
    return {"ok": True, "mesaj": "başlatıldı", **durum()}


def atla() -> dict:
    """Çalışan indirmeyi durdurur ve kendiliğinden yeniden denemeyi kapatır (kullanıcı kararı; baslat() geri açar)."""
    YEREL.mkdir(parents=True, exist_ok=True)
    ATLA.write_text("kullanıcı atladı\n", encoding="utf-8")
    d = _oku()
    pid = int(d.get("pid") or 0)
    if pid and _canli_mi(pid):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NW, timeout=30)   # /T: pip gibi alt süreçler de
            else:
                os.kill(pid, 15)
        except (OSError, subprocess.SubprocessError):
            pass
    if d:
        d.update(calisiyor=False, bitis=time.time())
        _yaz(d)
    return {"ok": True, **durum(taze=True)}


_OTO = {"bas": False}


def otomatik() -> dict | None:
    """Panel açılışında ve 10 dk'da bir: eksik varsa, kullanıcı atlamadıysa ve son çalıştırmanın üzerinden yeterli süre geçtiyse arka planda başlatır."""
    d = durum(taze=True)
    if d["calisiyor"] or d["atlandi"] or d["eksik_toplam"] == 0:
        return None
    bitis = float(_oku().get("bitis") or 0)
    if d["kod"] == "sorun" and time.time() - bitis < YENIDEN_DENE_SN:
        return None
    return baslat(zorla=False)


def otomatik_dongu(ilk_bekleme: float = 5.0) -> None:
    """Panelin arka plan iş parçacığı: açılıştan kısa süre sonra başlar, sonra her 10 dk bakar (yeniden deneme aralığını otomatik() uygular)."""
    if _OTO["bas"] or os.environ.get("YST_ARKA_YOK"):   # YST_ARKA_YOK: testlerde gerçek klasöre indirme başlatılmasın
        return
    _OTO["bas"] = True

    def is_():
        time.sleep(ilk_bekleme)
        while True:
            try:
                otomatik()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(600)
    threading.Thread(target=is_, daemon=True, name="arka-indirme").start()


# ------------------------------------------------------------------ iş (ayrı süreçte)
def _pip(args: list, zaman: int = 3600) -> str:
    """pip install; başarılıysa '', değilse hata özeti."""
    py = str(VENV_PY if VENV_PY.exists() else sys.executable)
    try:
        r = subprocess.run([py, "-m", "pip", "install", "-q", *map(str, args)], env=_ortam(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=zaman, creationflags=NW)
    except (OSError, subprocess.SubprocessError) as e:
        return f"{type(e).__name__}: {str(e)[:100]}"
    return "" if r.returncode == 0 else (r.stderr or r.stdout or "pip hatası").strip()[-160:]


def _hf(repo: str, ev: str | None) -> str:
    b = _bilesen()
    kod = "import sys;from huggingface_hub import snapshot_download as s;" + (f"s(sys.argv[1], cache_dir=r'{b.DEPTH_EV / 'hub'}')" if ev == "derinlik" else "s(sys.argv[1])")
    try:
        r = subprocess.run([str(VENV_PY if VENV_PY.exists() else sys.executable), "-c", kod, repo], env=_ortam(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600, creationflags=NW)
    except (OSError, subprocess.SubprocessError) as e:
        return f"{type(e).__name__}: {str(e)[:100]}"
    return "" if r.returncode == 0 else (r.stderr or "indirilemedi").strip()[-160:]


def calis(ses: bool = False) -> int:
    bas = time.time()
    durum_ = {"calisiyor": True, "pid": os.getpid(), "bas": bas, "nabiz": bas, "sira": 0, "toplam": 0, "simdiki": "", "sonuc": {}, "kalemler": {}, "ses": ses}
    kilit = threading.Lock()
    dur = threading.Event()

    def yaz():
        with kilit:
            durum_["nabiz"] = time.time()
            _yaz(durum_)

    def nabiz():
        while not dur.wait(20):
            try:
                yaz()
            except OSError:
                pass
    threading.Thread(target=nabiz, daemon=True).start()
    sonuc: dict = {}
    kalemler: dict = durum_["kalemler"]
    try:
        # çalıştırılacaklar: yalnızca eksik olanlar, kuyruk sırasıyla
        yapilacak = [k for k in KUYRUK if kalem_eksik(k)]
        durum_.update(toplam=len(yapilacak) + (1 if ses and ses_ozeti()["eksik"] else 0))
        yaz()
        for sira, k in enumerate(yapilacak):
            durum_.update(sira=sira, simdiki=k["id"], sonuc=dict(sonuc))
            kalemler[k["id"]] = {"durum": "iniyor", "bas": time.time()}
            yaz()
            dep = k.get("dep")
            if dep and str(sonuc.get(dep, "indirildi")).split(":")[0] in ("HATA", "ATLANDI"):
                hata = f"ATLANDI: önce '{dep}' gerekli"
            elif k["tur"] == "varlik":
                v = _varlik()
                c = v.baglan()
                alt = v.indir_calistir(c, None, None, turler=TEMEL_TURLER)
                c.close()
                kotu = next((s for s in alt.values() if not str(s).startswith("indirildi")), "")
                hata = kotu if kotu else ""
                if not kotu:
                    sonuc[k["id"]] = "indirildi"
            elif k["tur"] == "rclone":
                try:
                    _bulut().kur()
                    hata = ""
                except Exception as e:  # noqa: BLE001
                    hata = f"{type(e).__name__}: {str(e)[:120]}"
            elif k["tur"] == "pip-torch":
                hata = _pip(["torch", "torchvision", "--index-url", CPU_INDEKS])
            elif k["tur"] == "pip-ml":
                hata = _pip(["-r", SISTEM / "kurulum" / "gereksinim-ml.txt"])
            else:
                hata = _hf(k["repo"], k.get("ev"))
            if hata:
                sonuc[k["id"]] = hata if hata.startswith(("ATLANDI", "HATA")) else "HATA: " + hata
                kalemler[k["id"]].update(durum="atlandi" if hata.startswith("ATLANDI") else "hata", mesaj=sonuc[k["id"]].split(": ", 1)[-1][:160], bit=time.time())
            else:
                sonuc[k["id"]] = "indirildi"
                kalemler[k["id"]].update(durum="tamam", bit=time.time())
            print(f"{k['id']}: {sonuc[k['id']]}", flush=True)
            _EKSIK["v"] = None
            durum_.update(sonuc=dict(sonuc))
            yaz()
        if ses:   # kullanıcı isteğiyle: müzik + ses efektleri
            durum_.update(sira=len(yapilacak), simdiki="ses", sonuc=dict(sonuc))
            kalemler["ses"] = {"durum": "iniyor", "bas": time.time()}
            yaz()
            v = _varlik()
            c = v.baglan()
            alt = v.indir_calistir(c, None, None, turler=SES_TURLER)
            c.close()
            sonuc.update(alt)
            kalemler["ses"].update(durum="tamam" if all(str(s).startswith("indirildi") for s in alt.values()) else "atlandi", bit=time.time())
    except Exception as e:  # noqa: BLE001
        sonuc["genel"] = f"HATA: {type(e).__name__}: {str(e)[:150]}"
        print(sonuc["genel"], flush=True)
    finally:
        dur.set()
        durum_.update(calisiyor=False, bitis=time.time(), simdiki="", sonuc=sonuc)
        durum_["sira"] = durum_["toplam"]
        yaz()
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure") and sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:] or ["durum"]
    if a[0] == "calis":
        sys.exit(calis("ses" in a[1:]))
    elif a[0] == "baslat":
        print(json.dumps(baslat(), ensure_ascii=False, indent=1))
    elif a[0] == "ses":
        print(json.dumps(baslat(True, ses=True), ensure_ascii=False, indent=1))
    elif a[0] == "atla":
        print(json.dumps(atla(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(durum(taze=True), ensure_ascii=False, indent=1))
