"""Stüdyo paneli: projeler, yeni proje sihirbazı, arşiv, kimlik ve zevk testi, Kurgu editörü ve Claude başlatma.

Başlat.cmd bunu çalıştırır. Yalnızca 127.0.0.1'e bağlanır; hesap/bulut yok. Standart kütüphane (+ PIL: arşiv önizlemesi).
Güvenlik: Host başlığı yerel olmalı (DNS-rebinding), POST'lar özel başlık ister (CSRF), proje adları temizlenir,
kullanıcı metni asla komut satırına konmaz (brief.md'ye yazılır; Claude'a sabit bir komut gider). Arşive yalnızca OKUNUR.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
SISTEM = ROOT / "sistem"
ORTAM = SISTEM / "ortam"
PROJELER = ROOT / "projeler"
KIMLIK = ROOT / "kimlik"
VENV_PY = ORTAM / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not VENV_PY.exists():  # kurulumsuz çalışma (geliştirme/CI): panelin kendi yorumlayıcısı
    VENV_PY = Path(sys.executable)
KURGU =ORTAM / "venv" / ("Scripts/kurgu.exe" if os.name == "nt" else "bin/kurgu")
# kurulumun getirdiği ffmpeg/ffprobe/rclone sistemde yoksa da bulunsun (panel ve başlattığı bütün süreçler PATH'i devralır)
sys.path.insert(0, str(SISTEM / "araclar"))
import yol as _yol  # noqa: E402

_yol.hazirla()
# kurgu.exe başlatıcısı kurulum yerinin mutlak yolunu içerir; klasör taşınınca bozulabilir. Python üzerinden çağırmak yerden bağımsızdır.
KURGU_CMD = [str(VENV_PY), "-c", "import sys, kurgu_cli; sys.argv[0] = 'kurgu'; sys.exit(kurgu_cli.main())"]
PANEL_DOSYA = ORTAM / "yerel" / "panel.json"
SUNUCU: dict = {}
AD_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
FORMATLAR = ("ana", "reels", "tiktok", "shorts")
UZANTI = {
    "foto": (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"),
    "video": (".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"),
    "ses": (".mp3", ".wav", ".m4a", ".flac", ".ogg"),
    "belge": (".dwg", ".svg", ".pdf", ".docx", ".xlsx", ".doc", ".xls", ".dxf", ".pptx", ".txt", ".md", ".srt", ".csv"),
}
editorler: dict[str, tuple[subprocess.Popen, int]] = {}
EDITOR_EN_COK = 3  # aynı anda açık Kurgu editörü sayısı (her biri ayrı bir süreç ve bellek)
kilit = threading.Lock()
tarama = {"thread": None, "dur": False}
_MOD: dict = {}

# Zevk testi: aynı mesaj iki üslupta; kullanıcı beğeneni seçer (sıfat beyanından çok daha güvenilir).
ZEVK_CUMLE = [
    {"olcer": "ritim", "A": "Burası bir şantiyeydi. Şimdi teslime hazır bir salon.", "B": "Önce kaba inşaat, ardından ince işçilik; bugün aile salonu olarak teslim ediliyor."},
    {"olcer": "mizah", "A": "Duvarlar konuşamıyor. Biz konuşturuyoruz.", "B": "Her mekânın bir hikâyesi vardır; biz o hikâyeyi görünür kılıyoruz."},
    {"olcer": "hitap", "A": "Evini düşün: sabah ışığı nereye vursun?", "B": "Yaşam alanınız için ışığı birlikte planlayalım."},
    {"olcer": "somut-duygu", "A": "Kapı kolları İtalyan, mutfak sıfırdan çizildi, tavan yüksekliği 3,10 metre.", "B": "İçeri girince önce bir sessizlik oluyor. Sonra herkes gülümsüyor."},
    {"olcer": "iddia", "A": "İşimizi sessizce konuşturuyoruz.", "B": "İstanbul'un en iyi iç mekân işlerinden birini yapıyoruz."},
    {"olcer": "aciliş", "A": "Kaç ay sürdü, biliyor musunuz?", "B": "Altı ayda, ruhsattan teslime."},
    {"olcer": "cagri", "A": "Projen için yaz.", "B": "Bir sonraki hikâye senin mekânın olabilir; konuşalım."},
    {"olcer": "yapi", "A": "Önce. Sonra. Bugün.", "B": "Bu proje, ilk keşiften anahtar teslimine kadar aşamalı olarak ilerledi."},
]


def surum_bilgisi() -> dict:
    try:
        return json.loads((SISTEM / "surum.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def modul(ad: str, rel: str):
    """sistem/ altındaki bir betiği modül olarak yükle (arsiv, kimlik_olc)."""
    if ad not in _MOD:
        spec = importlib.util.spec_from_file_location(ad, SISTEM / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _MOD[ad] = m
    return _MOD[ad]


def arsiv():
    return modul("arsiv", "arsiv/arsiv.py")


def ek():
    return modul("ek_api", "panel/ek_api.py")


def analiz():
    return modul("analiz", "arsiv/analiz.py")


def ortam() -> dict:
    e = dict(os.environ)
    e.update(_yol.kapsama())   # tek klasör kuralı: indirmeler ve önbellekler stüdyo klasörüne
    return e


def bos_port(baslangic: int) -> int:
    for p in range(baslangic, baslangic + 60):
        with socket.socket() as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError("boş port yok")


def proje_yolu(ad: str) -> Path:
    if not AD_RE.match(ad or ""):
        raise ValueError("geçersiz proje adı")
    p = (PROJELER / ad).resolve()
    if p.parent != PROJELER.resolve():
        raise ValueError("geçersiz proje yolu")
    return p


def kategori(ad: str):
    e = os.path.splitext(ad)[1].lower()
    return next((k for k, ekler in UZANTI.items() if e in ekler), None)


def projeleri_listele() -> list[dict]:
    out = []
    if not PROJELER.is_dir():
        return out
    for d in sorted(PROJELER.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or not AD_RE.match(d.name):
            continue
        kaynak = {}
        kd = d / "kaynak"
        if kd.is_dir():
            for k in UZANTI:
                if (kd / k).is_dir():
                    kaynak[k] = sum(1 for f in (kd / k).iterdir() if f.is_file())
        formatlar = [f for f in FORMATLAR if (d / f / "project.json").is_file()]
        cikti = sorted(p.name for p in (d / "cikti").glob("*") if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".png", ".jpg", ".md")) \
            if (d / "cikti").is_dir() else []
        out.append({"ad": d.name, "formatlar": formatlar, "kaynak": kaynak, "cikti": cikti,
                    "brief": (d / "brief.md").is_file(), "gunluk": (d / "calisma_gunlugu.md").is_file(),
                    "degisti": time.strftime("%Y-%m-%d %H:%M", time.localtime(d.stat().st_mtime))})
    return out


_BOYUT: dict = {}
CALISAN_ASAMA = ("hazirlaniyor", "planlama", "uretiliyor", "final-render", "platform-surumleri")
BEKLEYEN_ASAMA = ("plan-onayi-bekliyor", "taslak-hazir", "onaylandi", "engel")
ASAMA_YUZDE = {"hazirlaniyor": 5, "planlama": 18, "plan-onayi-bekliyor": 28, "uretiliyor": 52, "taslak-hazir": 70, "onaylandi": 80, "final-render": 88, "platform-surumleri": 95, "teslim": 100, "engel": 0}


def klasor_boyut(p: Path, ttl: float = 120.0) -> int:
    t = _BOYUT.get(str(p))
    if t and time.time() - t[0] < ttl:
        return t[1]
    n = 0
    for kok, _dirs, files in os.walk(p):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(kok, f))
            except OSError:
                pass
    _BOYUT[str(p)] = (time.time(), n)
    return n


def kimlik_ozet() -> dict:
    try:
        return ek().modul("yst_kimlik_sablon", "araclar/kimlik_sablon.py").durum()
    except Exception:  # noqa: BLE001
        return {"dolu": True}


_HARC: dict = {}


def harcama_ozeti() -> dict:
    """harcama.jsonl her çağrıda baştan okunup çözülüyordu (dosya her ücretli çağrıyla büyür, pano 4 sn'de bir sorar). Dosya değişmedikçe ve gün aynıyken önbellekten döner."""
    yol = ORTAM / "baglayici" / "harcama.jsonl"
    try:
        st = yol.stat()
        anahtar = (st.st_mtime_ns, st.st_size, time.strftime("%Y-%m-%d"))
    except OSError:
        anahtar = ("yok", 0, time.strftime("%Y-%m-%d"))  # dosya henüz yok: bu da önbelleğe alınır
    if _HARC.get("anahtar") == anahtar:
        return _HARC["deger"]
    harcama = {"bugun": 0.0, "toplam": 0.0, "saglayici": {}, "proje": {}, "cagri": 0}
    bugun = time.strftime("%Y-%m-%d")
    try:
        for s in yol.read_text(encoding="utf-8").splitlines():
            try:
                h = json.loads(s)
                t = float(h.get("tutar") or 0)
            except (ValueError, AttributeError):
                continue  # bozuk bir satır tüm özeti düşürmesin
            harcama["toplam"] += t
            harcama["cagri"] += 1
            harcama["saglayici"][h.get("saglayici", "?")] = harcama["saglayici"].get(h.get("saglayici", "?"), 0) + t
            if h.get("proje"):
                harcama["proje"][h["proje"]] = harcama["proje"].get(h["proje"], 0) + t
            if str(h.get("zaman", ""))[:10] == bugun:
                harcama["bugun"] += t
    except OSError:
        pass
    harcama = {**harcama, "bugun": round(harcama["bugun"], 3), "toplam": round(harcama["toplam"], 3)}
    _HARC.update(anahtar=anahtar, deger=harcama)
    return harcama


def pano() -> dict:
    """Pano (ana sayfa): projeler (üretilen / üretilmekte / bekleyen), istatistikler, harcama, bağlı modeller, arşiv ve güncelleme durumu."""
    E = ek()
    A = E.ayar()
    cz = A.coz()
    simdi = time.time()
    projeler = []
    ork = A.orkestrator_ortami()  # bir kez: ajan başına yeniden çözülmesin
    for p in projeleri_listele():
        d = E.durum().oku(p["ad"])
        asama = d.get("asama", "hazirlaniyor")
        try:
            u = json.loads((PROJELER / p["ad"] / "uretim.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            u = {}
        ajanlar = {}
        try:
            # proje kendi ayar.json'unu taşımıyorsa genel çözülmüş ayar aynen geçerlidir (N proje × M ajan kez dosya okuma yok)
            cz_p = A.coz(p["ad"]) if (PROJELER / p["ad"] / "ayar.json").is_file() else cz
            for ad in cz_p["ajanlar"]:
                a = A.ajan(ad, p["ad"], cz_p, ork)
                ajanlar[ad] = {"ortam": a["etkin_ortam"], "model": a["model"] or "varsayılan", "effort": a.get("effort")}
        except (KeyError, ValueError):
            pass
        try:
            gun = time.mktime(time.strptime(d.get("guncelleme") or "", "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            gun = (PROJELER / p["ad"]).stat().st_mtime
        mp4 = [f for f in p["cikti"] if f.lower().endswith(".mp4")]
        grup = "calisan" if asama in CALISAN_ASAMA and simdi - gun < 6 * 3600 else ("biten" if asama == "teslim" or (mp4 and asama in ("teslim", "platform-surumleri")) else "bekleyen")
        projeler.append({"ad": p["ad"], "asama": asama, "etiket": d.get("etiket") or asama, "not": d.get("not", ""), "guncelleme": d.get("guncelleme"), "yuzde": ASAMA_YUZDE.get(asama, 0),
                         "grup": grup, "boyut_mb": round(klasor_boyut(PROJELER / p["ad"]) / 1e6, 1), "mp4": mp4, "formatlar": p["formatlar"], "seri": u.get("seri"),
                         "platformlar": u.get("platformlar") or [], "b_plani": bool(u.get("b_plani")), "ajanlar": ajanlar, "degisti": p["degisti"], "kaynak": p["kaynak"]})
    harcama = {**harcama_ozeti(), "tavan": (cz.get("butce") or {}).get("gun_tavan", 5)}
    try:
        bag = E.baglayicilar(None)["saglayicilar"]
    except Exception:  # noqa: BLE001
        bag = []
    rid, _prof = calisma_ortami()
    orto = [o for o in E.modul("yst_ajan_cagir", "araclar/ajan_cagir.py").ortam_listesi()]
    try:
        a = arsiv_durum()
        arsiv_ozet = {"ayarli": bool(a.get("ayarli")), "bagli": bool(a.get("bagli")), "toplam": a.get("toplam", 0), "arsivler": len(a.get("arsivler") or [])}
    except Exception:  # noqa: BLE001
        arsiv_ozet = {"ayarli": False, "bagli": False, "toplam": 0, "arsivler": 0}
    try:
        g = E.modul("yst_guncelleme", "araclar/guncelleme.py").durum()
        gun_ozet = {"etkin": g["etkin"], "var": bool((g.get("kontrol") or {}).get("var")), "yeni": (g.get("kontrol") or {}).get("yeni"), "son_kontrol": (g.get("kontrol") or {}).get("son_kontrol"),
                    "hata": (g.get("kontrol") or {}).get("hata", "")}
    except Exception:  # noqa: BLE001
        gun_ozet = {"etkin": False, "var": False}
    sayim = {g: sum(1 for p in projeler if p["grup"] == g) for g in ("calisan", "bekleyen", "biten")}
    return {"projeler": projeler, "sayim": sayim, "toplam_boyut_mb": round(sum(p["boyut_mb"] for p in projeler), 1), "harcama": harcama,
            "saglayicilar": [{"id": s["id"], "ad": s.get("ad", s["id"]), "etkin": bool(s.get("etkin")), "hazir": bool(s.get("hazir", s.get("etkin"))), "yerel": bool(s.get("yerel"))} for s in bag],
            "orkestrator": {"id": rid, "ad": next((o["ad"] for o in orto if o["id"] == rid), rid)}, "ortamlar": orto, "arsiv": arsiv_ozet, "guncelleme": gun_ozet, "kimlik": kimlik_ozet(),
            "surum": E.modul("yst_guncelleme", "araclar/guncelleme.py").surum(), "kurulum": (ORTAM / "yerel" / "kurulum.ok").exists()}


EKLENTI: dict = {"durum": "bilinmiyor", "neden": ""}   # Kurgu'ya uygulanan stüdyo eklentisinin durumu (kurgu_yama.py); Kurgu eklenti olmadan da çalışır


def kurgu_yama():
    return modul("yst_kurgu_yama", "kurulum/kurgu_yama.py")


def eklenti_hazirla() -> dict:
    """Kurgu açılmadan önce eklentiyi (yeniden) uygulamayı dener. HİÇBİR durumda istisna fırlatmaz: yama tutmazsa Kurgu düz haliyle açılır."""
    global EKLENTI
    try:
        r = kurgu_yama().otomatik(ROOT / "kurgu")
        EKLENTI = {"durum": r["durum"], "neden": (r.get("neden") or "")[:600]}
    except Exception as e:  # noqa: BLE001
        EKLENTI = {"durum": "uygulanamadi", "neden": f"denetlenemedi: {e}"[:600]}
    return EKLENTI


def eklenti_yoklama(port: int) -> None:
    """Çalışan Kurgu eklentiyi gerçekten yüklemiş mi? (/api/yst/durum yanıtı). Yüklememişse nedeni durum bilgisine yazılır."""
    if EKLENTI.get("durum") != "tamam":
        return
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/yst/durum", timeout=4).read(1)
    except urllib.error.HTTPError as e:
        EKLENTI.update(durum="yuklenemedi", neden=f"Kurgu eklenti rotasına yanıt vermedi (HTTP {e.code}): eklenti Kurgu'nun bu sürümüyle yüklenemedi.")
    except Exception:  # noqa: BLE001
        pass   # ağ hatası: durumu bozma


def eklenti_islem(islem: str) -> dict:
    """Panelden: 'yeniden' (tekrar uygula), 'kaldir' (düz Kurgu), 'ac' (eklentiyi aç). Açık Kurgu süreçleri yeni duruma göre yeniden başlatılır."""
    km = kurgu_yama()
    if islem == "kaldir":
        km.geri_al(ROOT / "kurgu")
        km.KAPALI.parent.mkdir(parents=True, exist_ok=True)
        km.KAPALI.write_text("kapatıldı\n", encoding="utf-8")
    elif islem == "ac":
        km.KAPALI.unlink(missing_ok=True)
    elif islem != "yeniden":
        raise ValueError("geçersiz işlem")
    with kilit:
        for pr0, _p in editorler.values():
            try:
                pr0.terminate()
            except OSError:
                pass
        editorler.clear()
    return eklenti_hazirla()


def kurgu_ac(proje: str, fmt: str) -> dict:
    if fmt not in FORMATLAR:
        raise ValueError("geçersiz biçim")
    d = proje_yolu(proje) / fmt
    if not (d / "project.json").is_file():
        raise ValueError(f"{proje}/{fmt} projesi yok")
    anahtar = f"{proje}/{fmt}"
    with kilit:
        if anahtar in editorler and editorler[anahtar][0].poll() is None:
            editorler[anahtar] = editorler.pop(anahtar)  # en son kullanılan sona
            return {"url": f"http://127.0.0.1:{editorler[anahtar][1]}", "eklenti": dict(EKLENTI)}
        for k in [k for k, (pr0, _p) in editorler.items() if pr0.poll() is not None]:
            editorler.pop(k, None)  # kapanmış kayıtları temizle
        while len(editorler) >= EDITOR_EN_COK:  # her proje/biçim için bir Python sunucusu kalıyordu: en eski açılanı kapat
            eski = next(iter(editorler))
            pr0, _p = editorler.pop(eski)
            try:
                pr0.terminate()
            except OSError:
                pass
        eklenti_hazirla()
        port = bos_port(8765)
        if not VENV_PY.exists():
            raise RuntimeError("Kurgu kurulu değil: Başlat.cmd kurulumu tamamlamalı")
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000) if os.name == "nt" else 0
        gomulu = {"KURGU_EMBED_ORIGIN": "http://127.0.0.1:%d" % SUNUCU["srv"].server_address[1]} if SUNUCU.get("srv") else {}
        pr = subprocess.Popen([str(VENV_PY), str(SISTEM / "araclar" / "kurgu_gomulu.py"), str(d), "--port", str(port), "--no-open"], cwd=str(ROOT),
                              env={**ortam(), "KURGU_MODE": "edit", **gomulu},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        editorler[anahtar] = (pr, port)
    for _ in range(60):  # sunucu ayağa kalksın
        time.sleep(0.25)
        with socket.socket() as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
    eklenti_yoklama(port)
    return {"url": f"http://127.0.0.1:{port}", "eklenti": dict(EKLENTI)}


def calisma_ortami() -> tuple[str, dict]:
    """Seçili orkestratör çalışma ortamı (Ayarlar → Orkestratör). Varsayılan: claude-code."""
    d = json.loads((SISTEM / "baglayici" / "calisma_ortamlari.json").read_text(encoding="utf-8"))
    rid = (ek().ayar().coz().get("orkestrator") or {}).get("calisma_ortami", "claude-code")
    return rid, d.get(rid) or d["claude-code"]


def baska_ortam_istemi(proje: str | None, gorev: str | None) -> str:
    """Claude dışı ortamlar için SABİT istem (slash komut yok): komut dosyalarını okuyup uygular. Kullanıcı metni girmez."""
    tabani = "Önce .claude/CLAUDE.md dosyasını oku. "
    if gorev == "b-plani":
        return tabani + f"Sonra .claude/commands/b-plani.md dosyasındaki akışı projeler/{proje} için uygula."
    if gorev == "profil":
        return tabani + "Sonra .claude/commands/profil.md dosyasındaki akışı uygula."
    if gorev == "final":
        return tabani + f"Sonra .claude/commands/final.md dosyasındaki akışı projeler/{proje} için uygula."
    if gorev == "seri":
        return tabani + f"Sonra .claude/commands/seri.md dosyasındaki akışı projeler/{proje} için uygula (seri bağlamı projeler/{proje}/seri_baglami.md)."
    return (tabani + f"Sonra .claude/commands/video.md dosyasındaki akışı projeler/{proje} için uygula (istek projeler/{proje}/brief.md ve uretim.json içinde, kaynaklar projeler/{proje}/kaynak/). "
            "Alt ajan tanımları .claude/agents/*.md dosyalarındadır; ortamında alt ajan yoksa o rollerin görevlerini sırayla kendin yap.")


def claude_baslat(proje: str | None = None, gorev: str | None = None) -> dict:
    """Seçili orkestratörü (varsayılan Claude Code) yeni pencerede açar. Komut SABİTTİR: /video <proje> ya da /profil (kullanıcı metni komuta girmez)."""
    yerel = ORTAM / "yerel"
    yerel.mkdir(parents=True, exist_ok=True)
    rid, prof = calisma_ortami()
    mcp_arg, ek_satir = ek().claude_ek(proje, gorev)
    if gorev == "profil":
        komut, ad = f'claude{mcp_arg} "/profil"', "kimlik"
    elif gorev == "b-plani":
        d = proje_yolu(proje or "")
        if not (d / "uretim.json").is_file() or "b_plani" not in json.loads((d / "uretim.json").read_text(encoding="utf-8")):
            raise ValueError("önce B planını ayarla (karakter seç)")
        komut = f'claude{mcp_arg} "/b-plani projeler/{proje}"'
        ad = f"{proje}-bplani"
    elif gorev == "seri":
        d = proje_yolu(proje or "")
        if not (d / "seri_baglami.md").is_file():
            raise ValueError("bu proje bir dizi bölümü değil (seri_baglami.md yok): Seriler sayfasından bölüm aç")
        komut = f'claude{mcp_arg} "/seri projeler/{proje}"'
        ad = f"{proje}-seri"
    elif gorev == "final":
        d = proje_yolu(proje or "")
        if not (d / "onay.json").is_file():
            raise ValueError("önce Onaylıyorum de (onay.json yok)")
        komut = f'claude{mcp_arg} "/final projeler/{proje}"'
        ad = f"{proje}-final"
    else:
        d = proje_yolu(proje or "")
        if not (d / "brief.md").is_file():
            raise ValueError("proje bulunamadı")
        komut = f'claude{mcp_arg} "/video projeler/{proje} (istek projeler/{proje}/brief.md ve uretim.json içinde, kaynaklar projeler/{proje}/kaynak/)"'
        ad = proje
    if rid != "claude-code":  # deneysel çalışma ortamı: aynı yönergeleri markdown dosyalarından okuyan sabit istem
        import shutil
        if not shutil.which(prof["komut"]):
            raise ValueError(f"{prof['ad']} kurulu değil ({prof['komut']} komutu bulunamadı). Ayarlar → Orkestratör'den Claude Code'a dön ya da CLI'ı kur.")
        istem = baska_ortam_istemi(proje, gorev)
        arg = f'"{istem}"' if prof.get("istem") == "konum" else f'{prof["istem"]} "{istem}"'
        komut, mcp_arg, ek_satir = f'{prof["komut"]} {arg}', "", []
        ad = f"{ad}-{rid}"
    if os.name != "nt":
        return _terminalde_ac(ad, komut, ek_satir)
    betik = yerel / f"claude_{ad}.cmd"
    betik.write_text("\r\n".join([
        "@echo off", "chcp 65001 >nul", f'cd /d "{ROOT}"',
        *[f'set "{k}={v}"' for k, v in _yol.kapsama().items()],
        f'set "PATH={ORTAM / "venv" / "Scripts"};%PATH%{(";" + ";".join(_yol.klasorler())) if _yol.klasorler() else ""}"',
        *ek_satir, komut, ""]), encoding="utf-8")
    subprocess.Popen(["cmd", "/c", "start", f"Claude - {ad}", "cmd", "/k", str(betik)], cwd=str(ROOT))
    return {"ok": True}


def _terminalde_ac(ad: str, komut: str, ek_satir: list) -> dict:
    """Linux/macOS: ortamı kuran bir kabuk betiği yazar, uygun bir terminal penceresinde açar."""
    import shlex
    import shutil
    betik = ORTAM / "yerel" / f"claude_{ad}.sh"
    betik.write_text("\n".join([
        "#!/bin/bash", f"cd {shlex.quote(str(ROOT))}", *[f"export {k}={shlex.quote(v)}" for k, v in _yol.kapsama().items()],
        f"export PATH={shlex.quote(str(ORTAM / 'venv' / 'bin'))}:$PATH" + "".join(":" + shlex.quote(d) for d in _yol.klasorler()), f"export YST_KOK={shlex.quote(str(ROOT))}", komut, "echo; read -r -p 'Kapatmak için Enter...' _", ""]), encoding="utf-8")
    betik.chmod(0o755)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Terminal", str(betik)])
        return {"ok": True}
    for t in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xfce4-terminal", "-e"], ["kitty"], ["alacritty", "-e"], ["xterm", "-e"]):
        if shutil.which(t[0]):
            subprocess.Popen(t + ["bash", str(betik)], cwd=str(ROOT))
            return {"ok": True}
    raise ValueError(f"Terminal bulunamadı. Elle çalıştır:  bash {betik}")


def klasor_ac(yol: Path) -> None:
    if os.name == "nt":
        os.startfile(str(yol))  # noqa: S606 (Windows gezgini)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(yol)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------ arşiv
def arsiv_durum() -> dict:
    A = arsiv()
    d = A.durum()
    try:
        d["ilerleme"] = json.loads(A.ILERLEME.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d["ilerleme"] = None
    d["calisiyor"] = bool(tarama["thread"] and tarama["thread"].is_alive())
    try:
        d["analiz"] = analiz().ozet(1)["turler"] if d.get("toplam") else None
    except Exception:  # noqa: BLE001
        d["analiz"] = None
    return d


def arsiv_tara_baslat(derin: bool, analizle: bool = True, kok_id: int | None = None) -> dict:
    A = arsiv()
    if tarama["thread"] and tarama["thread"].is_alive():
        return {"ok": False, "mesaj": "tarama zaten çalışıyor"}
    tarama["dur"] = False

    def is_():
        try:
            A.tara(derin=derin, durdur=lambda: tarama["dur"], yazdir=lambda *a, **k: None, kok_id=kok_id)
            if analizle and not tarama["dur"]:  # tarama bitince kullanılabilirlik analizi kendiliğinden başlar
                analiz().oto(durdur=lambda: tarama["dur"], yazdir=lambda *a, **k: None, kok_id=kok_id)
        except Exception as e:  # noqa: BLE001
            A.ilerleme_yaz({"durum": f"hata: {e}"})

    tarama["thread"] = threading.Thread(target=is_, daemon=True)
    tarama["thread"].start()
    return {"ok": True}


def arsiv_analiz_baslat(proje: str | None, yil: str | None, kok_id: int | None = None) -> dict:
    if not arsiv().durum()["bagli"]:
        raise ValueError("arşiv bağlı değil: harici diski tak ya da Ayarlar → Konumlar'dan yolunu göster")
    if tarama["thread"] and tarama["thread"].is_alive():
        return {"ok": False, "mesaj": "tarama/analiz zaten çalışıyor"}
    tarama["dur"] = False

    def is_():
        try:
            analiz().oto(proje=proje or None, yil=yil or None, durdur=lambda: tarama["dur"], yazdir=lambda *a, **k: None, kok_id=kok_id)
        except Exception as e:  # noqa: BLE001
            arsiv().ilerleme_yaz({"durum": f"hata: {e}"})

    tarama["thread"] = threading.Thread(target=is_, daemon=True)
    tarama["thread"].start()
    return {"ok": True}


def _asamaya_yay(sat: list[dict], n: int) -> list[dict]:
    """Aşamalar (öncesi/yapım/sonrası…) arasında dönüşümlü, her aşamada en yüksek puanlıdan seç: hikâye için dengeli malzeme."""
    gr: dict[str, list] = {}
    for r in sat:
        gr.setdefault(r.get("asama") or "?", []).append(r)
    out = []
    while len(out) < n and any(gr.values()):
        for k in list(gr):
            if gr[k] and len(out) < n:
                out.append(gr[k].pop(0))
    return out


def arsiv_sec(secim: dict, hedef: Path) -> dict:
    """Seçilen proje klasörlerinden dengeli bir örnek (tarihe yayılmış) alıp kaynak/ altına KOPYALAR; arşive yalnızca okunur."""
    A = arsiv()
    f = secim.get("filtre") or {}
    gruplar = [g for g in secim.get("gruplar", []) if isinstance(g, str)][:40]
    en_cok = max(10, min(int(secim.get("en_cok", 60)), 400))
    per = max(8, en_cok // max(len(gruplar), 1))
    turler = f.get("tur") or None
    kok = int(f["kok"]) if f.get("kok") else None
    idler: list[int] = []
    for g in gruplar:
        sat = A.ara(f.get("yil"), turler, f.get("kelime"), None, 5000, klasor_on="" if g == "(kök)" else g, kok_id=kok)
        klasor_on = "" if g == "(kök)" else g
        uygun_foto = analiz().uygun(f.get("yil"), f.get("kelime"), None, "foto", klasor_on, 6.0, 5000, False, kok) if (not turler or "foto" in turler) else []
        foto = [r for r in sat if r["tur"] == "foto"]
        if len(uygun_foto) >= min(per, 5):  # analiz edilmiş ve kullanılabilir olanlar varsa onlardan, aşamalara yayarak seç
            foto = _asamaya_yay(uygun_foto, per)
        video = [r for r in sat if r["tur"] == "video"]
        belge = [r for r in sat if r["tur"] == "belge"]
        ses = [r for r in sat if r["tur"] == "ses"]

        def yay(liste, n):
            if len(liste) <= n:
                return liste
            adim = len(liste) / n
            return [liste[int(i * adim)] for i in range(n)]

        idler += [r["id"] for r in yay(foto, per)] + [r["id"] for r in yay(video, min(3, per))] + [r["id"] for r in yay(belge, 6)] + [r["id"] for r in yay(ses, 2)]
    idler = list(dict.fromkeys(idler))
    sonuc = A.kopyala(idler, str(hedef))
    try:
        analiz().kopya_listesi(idler, str(hedef))  # her dosyanın analizi proje içinde kaynak/arsiv_analiz.json olarak durur
    except Exception:  # noqa: BLE001
        pass
    (hedef / "arsiv_secim.json").write_text(json.dumps({"gruplar": gruplar, "filtre": f, "kopyalanan": sonuc["ayrinti"], "atlanan": sonuc["atlanan"]},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    return {"kopyalanan": sonuc["kopyalanan"], "atlanan": len(sonuc["atlanan"]), "toplam_mb": sonuc["toplam_mb"]}


# ------------------------------------------------------------------ zevk ve müzik
def muzik_listesi() -> list[dict]:
    db = SISTEM / "varlik" / "varliklar.db"
    if not db.exists():
        return []
    c = sqlite3.connect(db)
    out = []
    for kimlik, ad, hedef, notlar in c.execute("SELECT id, ad, hedef, notlar FROM varlik WHERE tur='muzik' ORDER BY id"):
        his = re.search(r"His: (.*?)\.?$", notlar or "")
        out.append({"id": kimlik, "ad": ad, "his": his.group(1) if his else "", "var": (ROOT / hedef).is_file()})
    return out


def muzik_dosya(kimlik: str) -> Path | None:
    db = SISTEM / "varlik" / "varliklar.db"
    c = sqlite3.connect(db)
    try:
        r = c.execute("SELECT hedef FROM varlik WHERE id=? AND tur='muzik'", (kimlik,)).fetchone()
    finally:
        c.close()  # her müzik isteğinde bağlantı açık kalıyordu
    if not r:
        return None
    p = (ROOT / r[0]).resolve()
    return p if p.is_file() and (ROOT / "sistem" / "kit" / "muzik").resolve() in p.parents else None


def zevk_yaz(g: dict) -> dict:
    muzik = {k: v for k, v in (g.get("muzik") or {}).items() if v in ("sever", "olur", "olmaz")}
    cumle = []
    for s in g.get("cumle") or []:
        try:
            i = int(s.get("soru"))
            sec = s.get("secim")
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(ZEVK_CUMLE) and sec in ("A", "B", "ikisi-de-degil"):
            cumle.append({"soru": i, "secim": sec, "not": str(s.get("not") or "")[:300]})
    ad = {m["id"]: m["ad"] for m in muzik_listesi()}
    satir = ["# Zevk testi sonucu (OTOMATİK: panel → Kimlik → Zevk testi; yeniden yapılabilir)", "",
             f"Tarih: {time.strftime('%Y-%m-%d')}. Bu dosya **seçimlerden** çıkar: beyandan daha güvenilirdir. Senarist ve ses yönetmeni bunu ölçüt alır.", "",
             "## Cümle üslubu (aynı mesaj iki üslupta; hangisi 'ben'?)"]
    for c in cumle:
        q = ZEVK_CUMLE[c["soru"]]
        secilen = q.get(c["secim"]) if c["secim"] in ("A", "B") else None
        reddedilen = q["B" if c["secim"] == "A" else "A"] if c["secim"] in ("A", "B") else None
        if secilen:
            satir.append(f"- **{q['olcer']}**: seçilen → \"{secilen}\" · reddedilen → \"{reddedilen}\"" + (f" · not: {c['not']}" if c["not"] else ""))
        else:
            satir.append(f"- **{q['olcer']}**: ikisi de değil" + (f" · kendi cümlem: {c['not']}" if c["not"] else ""))
    satir += ["", "## Müzik (his → sever / olur / olmaz)"]
    for k, v in muzik.items():
        satir.append(f"- {v}: {ad.get(k, k)}")
    satir += ["", "## Kural", "Seçilen üslupları örnek al, reddedilenlerin kalıbını kullanma. Müzikte 'sever' olanlardan seç, 'olmaz' olanları kullanma."]
    KIMLIK.mkdir(exist_ok=True)
    (KIMLIK / "zevk.md").write_text("\n".join(satir) + "\n", encoding="utf-8")
    (KIMLIK / "zevk.json").write_text(json.dumps({"muzik": muzik, "cumle": cumle}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "cumle": len(cumle), "muzik": len(muzik)}


SIHIRBAZ_ALANLAR = {"seslendirme", "muzik", "muzik_his", "altyazi", "ton", "sure", "hitap", "cagri", "iletisim_goster", "mutlaka", "asla", "notlar", "platformlar", "arsiv_ozet", "gorsel_uret", "gorsel_tarif", "marka_ozet", "arsivden_bul", "bulut_izni"}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "YSTPanel"

    def log_message(self, *a):  # sessiz
        pass

    # --- yardımcılar
    def _host_ok(self) -> bool:
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost")

    def _json(self, obj, kod=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(b)

    def _bayt(self, b: bytes, tur: str, html: bool = False):
        self.send_response(200)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(b)))
        # arayüz dosyası önbelleğe alınmaz: güncellemeden sonra eski arayüz 5 dk kalıyordu
        self.send_header("Cache-Control", "no-store" if html else "max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        if html:
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")  # panel başka bir sayfada çerçevelenemez (clickjacking)
            # "no-referrer" Kurgu editörünü bozar: iframe isteğinde panelin adresini Referer olarak bekler (kurgu_gomulu.py). Yalnızca kaynak (origin) gider.
            self.send_header("Referrer-Policy", "strict-origin")
        self.end_headers()
        self.wfile.write(b)

    def _govde_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 20_000_000:
            raise ValueError("istek gövdesi çok büyük")
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    # --- GET
    def do_GET(self):
        if not self._host_ok():
            return self._json({"hata": "yasak"}, 403)
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._bayt((Path(__file__).parent / "index.html").read_bytes(), "text/html; charset=utf-8", html=True)
            if u.path == "/api/ping":
                return self._json({"app": "YSTPanel", "kok": str(ROOT), "pid": os.getpid(), "surum": surum_bilgisi().get("uygulama")})
            if u.path == "/api/profil/indir":
                p = ek().yedek_dosya(q.get("ad", ""))
                b = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
                return
            if u.path == "/api/pano":
                return self._json(pano())
            if u.path == "/api/projeler":
                return self._json({"projeler": projeleri_listele(), "kurulum": (ORTAM / "yerel" / "kurulum.ok").exists()})
            if u.path == "/api/kimlik":
                m = modul("kimlik_olc", "araclar/kimlik_olc.py")
                metin = (KIMLIK / "PROFIL.md").read_text(encoding="utf-8") if (KIMLIK / "PROFIL.md").exists() else ""
                r = m.olc(metin)
                r["katmanlar"] = m.katmanlar()
                r.pop("alanlar", None)
                return self._json(r)
            if u.path == "/api/arsiv/durum":
                return self._json(arsiv_durum())
            if u.path == "/api/arsiv/ses":   # arşivdeki müziği tarayıcıda dinlemek için (yalnızca dizindeki ses dosyaları, salt okunur)
                A = arsiv()
                c = A.baglan()
                r = c.execute("SELECT kok_id, yol, tur, cevrimdisi, boyut FROM dosya WHERE id=?", (int(q.get("id", "0") or 0),)).fetchone()
                if not r or r["tur"] != "ses" or r["cevrimdisi"] or (r["boyut"] or 0) > 150_000_000:
                    return self._json({"hata": "yok"}, 404)
                p = A.mutlak(c, r["kok_id"], r["yol"])
                if not p or not p.is_file():
                    return self._json({"hata": "dosya arşivde bulunamadı (arşiv bağlı mı?)"}, 404)
                mt = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".m4a": "audio/mp4", ".aac": "audio/aac"}
                return self._bayt(p.read_bytes(), mt.get(p.suffix.lower(), "application/octet-stream"))
            if u.path == "/api/arsiv/onizleme":
                b = arsiv().onizleme(int(q.get("id", "0")))
                return self._bayt(b, "image/jpeg") if b else self._json({"hata": "yok"}, 404)
            if u.path == "/api/arsiv/iyilestirme/onizleme":
                b = ek().iyilestir_m().onizleme(int(q.get("id", "0")), 420)
                return self._bayt(b, "image/jpeg") if b else self._json({"hata": "yok"}, 404)
            if u.path == "/api/marka/dosya":   # kit logosu önizlemesi: yalnızca kit klasöründeki logo dosyaları
                m = ek().marka()
                kd = m.kit_klasoru(q.get("kit", ""))
                dosya = os.path.basename(q.get("dosya", ""))
                if not dosya.lower().endswith(m.LOGO_UZ) or not (kd / dosya).is_file():
                    return self._json({"hata": "yok"}, 404)
                tur = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp"}.get(Path(dosya).suffix.lower(), "image/jpeg")
                return self._bayt((kd / dosya).read_bytes(), tur)
            if u.path == "/api/gorsel/dosya":
                try:
                    p = ek().gorsel_k().yol(q.get("id", ""))
                except ValueError:
                    return self._json({"hata": "yok"}, 404)
                if q.get("k"):   # küçük önizleme (ızgara için): 480 px JPEG, önbellekli
                    kd = ek().KAPAK_DIZIN.parent / "gorsel_kucuk"
                    kd.mkdir(parents=True, exist_ok=True)
                    kp = kd / f"{p.stem}-{int(p.stat().st_mtime)}.jpg"
                    if not kp.is_file():
                        from PIL import Image
                        im = Image.open(p).convert("RGB")
                        im.thumbnail((480, 480))
                        im.save(kp, quality=82)
                    return self._bayt(kp.read_bytes(), "image/jpeg")
                return self._bayt(p.read_bytes(), "image/png")
            if u.path == "/api/kapak":
                try:
                    p = ek().kapak(q.get("proje", ""))
                except ValueError:
                    return self._json({"hata": "geçersiz proje"}, 400)
                if not p:
                    return self._json({"hata": "kapak yok"}, 404)
                return self._bayt(p.read_bytes(), "image/jpeg")
            if u.path == "/api/ara-sahne/onizleme":
                p = ek().ara_sahne_onizleme(q.get("id", ""))
                if not p:
                    return self._json({"hata": "yok"}, 404)
                return self._bayt(p.read_bytes(), "image/jpeg")
            if u.path == "/api/klon/deneme.wav":
                p = ek().KLON_DENEME
                if not p.is_file():
                    return self._json({"hata": "yok"}, 404)
                b = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
                return
            if u.path == "/api/zevk/sorular":
                return self._json({"cumle": ZEVK_CUMLE, "muzik": muzik_listesi()})
            if u.path.startswith("/muzik/"):
                p = muzik_dosya(unquote(u.path[7:]))
                if not p:
                    return self._json({"hata": "yok"}, 404)
                tur = {".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mpeg", ".flac": "audio/flac", ".wav": "audio/wav"}.get(p.suffix.lower(), "application/octet-stream")
                return self._bayt(p.read_bytes(), tur)
            r = ek().get(u.path, q)
            if r is not None:
                return self._json(r)
            return self._json({"hata": "yok"}, 404)
        except (ValueError, RuntimeError) as e:
            return self._json({"hata": str(e)}, 400)

    # --- POST
    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Panel") != "1":
            return self._json({"hata": "yasak"}, 403)
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/yukle":
                return self._yukle(q)
            if u.path == "/api/marka/logo":
                return self._logo(q)
            if u.path == "/api/dikte":
                return self._dikte()
            if u.path == "/api/profil/yukle":
                return self._profil_yukle()
            if u.path == "/api/klon/ornek":
                n = int(self.headers.get("Content-Length") or 0)
                if n < 2_000 or n > 60_000_000:
                    raise ValueError("ses kaydı çok kısa ya da çok büyük")
                uz = "." + re.sub(r"[^a-z0-9]", "", (q.get("uz") or "webm").lower())[:4]
                return self._json(ek().klon_ornek_kaydet(self.rfile.read(n), uz))
            if u.path == "/api/ses/kaydet":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 60_000_000:
                    raise ValueError("ses kaydı boş ya da çok büyük (en çok 60 MB)")
                uz = "." + re.sub(r"[^a-z0-9]", "", (q.get("uz") or "webm").lower())[:4]
                return self._json(ek().ses_kaydet(q.get("proje", ""), self.rfile.read(n), uz))
            b = self._govde_json()
            if u.path == "/api/kapat":
                self._json({"ok": True})
                threading.Thread(target=lambda: (time.sleep(0.3), SUNUCU["srv"].shutdown()), daemon=True).start()
                return
            if u.path == "/api/proje":
                return self._proje(b)
            if u.path == "/api/hazirla":
                ad = proje_yolu(b.get("proje", "")).name
                r = subprocess.run([str(VENV_PY), str(SISTEM / "araclar" / "yeni_proje.py"), ad, "--hazirla"], cwd=str(ROOT),
                                   env=ortam(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
                return self._json({"ok": r.returncode == 0, "cikti": (r.stdout + r.stderr)[-3000:]})
            if u.path == "/api/kurgu":
                return self._json(kurgu_ac(b.get("proje", ""), b.get("format", "ana")))
            if u.path == "/api/kurgu/eklenti":
                return self._json(eklenti_islem(str(b.get("islem") or "yeniden")))
            if u.path == "/api/claude":
                return self._json(claude_baslat(b.get("proje"), b.get("gorev")))
            if u.path == "/api/klasor":
                alt = b.get("alt", "")
                if b.get("kok") == "kimlik":
                    klasor_ac(KIMLIK)
                    return self._json({"ok": True})
                d = proje_yolu(b.get("proje", ""))
                if alt not in ("", "kaynak", "cikti", "hazir") + FORMATLAR:
                    raise ValueError("geçersiz klasör")
                klasor_ac(d / alt if alt else d)
                return self._json({"ok": True})
            if u.path == "/api/saglik":
                r = subprocess.run([str(VENV_PY), str(SISTEM / "araclar" / "saglik.py")], cwd=str(ROOT), env=ortam(),
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
                return self._json({"ok": r.returncode == 0, "cikti": (r.stdout + r.stderr)[-6000:]})
            if u.path == "/api/arsiv/ayarla":
                return self._json({"ok": True, "ayar": arsiv().ayarla(str(b.get("yol", "")).strip().strip('"'), str(b.get("ad") or "arsiv").strip() or "arsiv", bool(b.get("zorla")))})
            if u.path == "/api/arsiv/ayarla-uzak":
                return self._json({"ok": True, "ayar": arsiv().ayarla_uzak(str(b.get("uzak", "")).strip(), str(b.get("ad") or "bulut").strip() or "bulut", str(b.get("gorunen_ad") or "").strip() or None)})
            if u.path == "/api/arsiv/tara":
                return self._json(arsiv_tara_baslat(bool(b.get("derin")), b.get("analiz", True) is not False, int(b["kok"]) if b.get("kok") else None))
            if u.path == "/api/arsiv/analiz":
                return self._json(arsiv_analiz_baslat(str(b.get("proje") or "").strip() or None, str(b.get("yil") or "").strip() or None, int(b["kok"]) if b.get("kok") else None))
            if u.path == "/api/arsiv/durdur":
                tarama["dur"] = True
                return self._json({"ok": True})
            if u.path == "/api/arsiv/ara":
                tur = ",".join(t for t in (b.get("tur") or []) if t in UZANTI) or None
                yil = None
                if b.get("yil0"):
                    yil = f"{int(b['yil0'])}-{int(b.get('yil1') or b['yil0'])}"
                kok = int(b["kok"]) if b.get("kok") else None
                g = arsiv().projeler(max(1, min(int(b.get("derinlik") or 1), 4)), yil, tur, (b.get("kelime") or "").strip() or None, 120, kok)
                try:
                    sayim = analiz().proje_say([x["proje"] for x in g], yil, kok)
                    for x in g:
                        x["analiz"] = sayim.get(x["proje"])
                except Exception:  # noqa: BLE001
                    pass
                return self._json({"gruplar": g})
            if u.path == "/api/zevk":
                return self._json(zevk_yaz(b))
            if u.path == "/api/uret":
                return self._uret(b)
            r = ek().post(u.path, q, b)
            if r is not None:
                return self._json(r)
            return self._json({"hata": "yok"}, 404)
        except (ValueError, RuntimeError) as e:
            return self._json({"hata": str(e)}, 400)
        except Exception as e:  # beklenmeyen hata paneli düşürmesin
            return self._json({"hata": f"{type(e).__name__}: {e}"}, 500)

    def _proje(self, b: dict):
        ad = re.sub(r"[^a-z0-9]+", "-", str(b.get("ad", "")).translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower()).strip("-")[:60]
        if not AD_RE.match(ad):
            raise ValueError("proje adı gerekli")
        fmts = [f for f in b.get("formatlar", ["ana"]) if f in FORMATLAR] or ["ana"]
        yerel = ORTAM / "yerel"
        yerel.mkdir(parents=True, exist_ok=True)
        cmd = [str(VENV_PY), str(SISTEM / "araclar" / "yeni_proje.py"), ad, "--tarif", str(b.get("tarif", ""))[:4000], "--format", *fmts]
        siz = {k: str(v)[:1500] for k, v in (b.get("sihirbaz") or {}).items() if k in SIHIRBAZ_ALANLAR and v not in (None, "", [])}
        if siz:
            sj = yerel / f"sihirbaz_{ad}.json"
            sj.write_text(json.dumps(siz, ensure_ascii=False), encoding="utf-8")
            cmd += ["--sihirbaz", str(sj)]
        r = subprocess.run(cmd, cwd=str(ROOT), env=ortam(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr)[-800:])
        arsiv_ozet = None
        if b.get("arsiv") and (b["arsiv"].get("gruplar")):
            arsiv_ozet = arsiv_sec(b["arsiv"], PROJELER / ad / "kaynak")
        return self._json({"ok": True, "proje": ad, "arsiv": arsiv_ozet})

    def _profil_yukle(self):
        """İçe aktarılacak profil dosyasını (JSON ya da ek zip) sistem/ortam/yedek/ içine alır."""
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 400_000_000:
            raise ValueError("dosya boş ya da çok büyük (en çok 400 MB)")
        ad = re.sub(r"[^A-Za-z0-9._-]", "_", Path(unquote(self.headers.get("X-Dosya-Adi") or "profil.json")).name)[:80] or "profil.json"
        if not ad.lower().endswith((".json", ".zip")):
            raise ValueError("yalnızca .json (ve .ekler.zip) kabul edilir")
        yedek = ORTAM / "yedek"
        yedek.mkdir(parents=True, exist_ok=True)
        hedef = yedek / ad
        kalan = n
        with open(hedef, "wb") as f:
            while kalan > 0:
                blok = self.rfile.read(min(1 << 20, kalan))
                if not blok:
                    break
                f.write(blok)
                kalan -= len(blok)
        if ad.lower().endswith(".zip"):
            return self._json({"ok": True, "ad": ad, "ek": True})
        return self._json(ek().profil_yuklendi(ad))

    def _dikte(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > ek().DIKTE_EN_COK:
            raise ValueError("ses kaydı çok uzun (en çok ~10 dakika)")
        return self._json(ek().dikte_coz(self.rfile.read(n)))

    def _logo(self, q: dict):
        kit = q.get("kit", "")
        ad = os.path.basename(unquote(q.get("ad", "")).replace("\\", "/"))
        n = int(self.headers.get("Content-Length") or 0)
        if n > 5_000_000:
            raise ValueError("logo 5 MB'tan küçük olmalı")
        veri = self.rfile.read(n)
        if q.get("id") or q.get("tur"):   # adlandırılmış logo (ana, simge, yatay, koyu/açık zemin…)
            return self._json({"ok": True, "logo": ek().marka().logo_ekle(kit, q.get("id", ""), ad, veri, unquote(q.get("etiket", "")), q.get("tur", "diger"))})
        return self._json({"ok": True, "logo": ek().marka().logo_kaydet(kit, ad, veri)})

    def _uret(self, b: dict):
        """Panelin 'Üret' düğmesi: projeyi, ayarını, marka kitini ve üretim isteğini kurar. Üretimi Claude (orkestratör) devralır."""
        e = ek()
        h = e.uret_hazirla(b)
        ad = h["ad"]
        yerel = ORTAM / "yerel"
        yerel.mkdir(parents=True, exist_ok=True)
        sj = yerel / f"sihirbaz_{ad}.json"
        sj.write_text(json.dumps({k: v for k, v in h["sihirbaz"].items() if k in SIHIRBAZ_ALANLAR and v}, ensure_ascii=False), encoding="utf-8")
        cmd = [str(VENV_PY), str(SISTEM / "araclar" / "yeni_proje.py"), ad, "--tarif", h["prompt"], "--format", *h["formatlar"], "--sihirbaz", str(sj)]
        r = subprocess.run(cmd, cwd=str(ROOT), env=ortam(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr)[-800:])
        pk = PROJELER / ad
        e.ayar().kaydet(h["ayar_yama"], ad)
        e.marka().uygula(ad, h["marka"]["kit"], {k: v for k, v in h["marka"].items() if k != "kit"})
        (pk / "uretim.json").write_text(json.dumps(h["uretim"], ensure_ascii=False, indent=2), encoding="utf-8")
        if (h["uretim"].get("seslendirme") or {}).get("klon"):
            e.klon_projeye(ad)  # kayıtlı örnek ses projenin klon/ornek.wav dosyası olur
        e.durum().yaz(ad, "hazirlaniyor", "proje kuruldu; Claude devralınca planlama başlar")
        arsiv_ozet = None
        if b.get("arsiv") and b["arsiv"].get("gruplar"):
            arsiv_ozet = arsiv_sec(b["arsiv"], pk / "kaynak")
        return self._json({"ok": True, "proje": ad, "formatlar": h["formatlar"], "arsiv": arsiv_ozet})

    def _yukle(self, q: dict):
        d = proje_yolu(q.get("proje", ""))
        ad = os.path.basename(unquote(q.get("ad", "")).replace("\\", "/"))
        kat = kategori(ad)
        if not ad or not kat:
            raise ValueError(f"desteklenmeyen dosya türü: {ad}")
        if not d.is_dir():
            raise ValueError("önce projeyi oluştur")
        n = int(self.headers.get("Content-Length") or 0)
        hedef_klasor = d / "kaynak" / kat
        hedef_klasor.mkdir(parents=True, exist_ok=True)
        hedef = hedef_klasor / ad
        if hedef.exists():  # aynı ad varsa ezme: numara ekle
            i = 2
            while (hedef_klasor / f"{hedef.stem}_{i}{hedef.suffix}").exists():
                i += 1
            hedef = hedef_klasor / f"{hedef.stem}_{i}{hedef.suffix}"
        kalan = n
        with open(hedef, "wb") as f:
            while kalan > 0:
                blok = self.rfile.read(min(1 << 20, kalan))
                if not blok:
                    break
                f.write(blok)
                kalan -= len(blok)
        return self._json({"ok": True, "dosya": f"kaynak/{kat}/{hedef.name}", "boyut": n - kalan})


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    PROJELER.mkdir(exist_ok=True)
    port = bos_port(8700)
    # Windows'ta SO_REUSEADDR başka bir dinleyicinin portuna da bağlanmaya izin verir: kapalı. Linux/macOS'ta ise güvenlidir (yalnızca TIME_WAIT'teki eski bağlantılara izin verir) ve
    # GEREKLİDİR: kapalıyken panel kapatılıp hemen yeniden açılınca ~1 dk "Address already in use" ile açılamıyordu.
    ThreadingHTTPServer.allow_reuse_address = os.name != "nt"
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    SUNUCU["srv"] = srv
    url = f"http://127.0.0.1:{port}"
    PANEL_DOSYA.parent.mkdir(parents=True, exist_ok=True)
    PANEL_DOSYA.write_text(json.dumps({"port": port, "pid": os.getpid(), "kok": str(ROOT), "baslangic": time.strftime("%Y-%m-%d %H:%M:%S")}), encoding="utf-8")
    print(f"Stüdyo paneli: {url}   (kapatmak için: Başlat.cmd durdur ya da panelde Kapat)", flush=True)
    if "--tarayici-yok" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        ek().modul("yst_kimlik_sablon", "araclar/kimlik_sablon.py").kur()  # eksik kimlik dosyaları nötr şablondan (var olana dokunmaz)
    except Exception:  # noqa: BLE001
        pass
    try:
        ek().modul("yst_guncelleme", "araclar/guncelleme.py").saatlik_baslat()  # GitHub'da güncelleme var mı: saatte bir (ayar girilmişse)
    except Exception:  # noqa: BLE001
        pass
    try:   # müzik, ses efektleri, yardımcı modeller: kurulumda değil, panel açıkken arka planda iner (hız sınırında vazgeçer, saatte bir yeniden dener)
        ek().modul("yst_arka_indirme", "araclar/arka_indirme.py").otomatik_dongu()
    except Exception:  # noqa: BLE001
        pass
    # donanım bilgisi (işlemci adı, ekran kartı) ilk istekte ~1,5 sn sürer: panel açılırken arka planda ısıt, Ayarlar → Sistem anında açılsın
    threading.Thread(target=lambda: ek().donanim_m().sistem(), daemon=True, name="donanim-isit").start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        tarama["dur"] = True
        try:
            PANEL_DOSYA.unlink()
        except OSError:
            pass
        for pr, _p in editorler.values():
            if pr.poll() is None:
                pr.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
