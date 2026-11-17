"""Müzik/ses efekti indirmesi takılmasın: hız sınırında hızlı vazgeçme, arka plan yöneticisi, atlanabilir kurulum adımları. Hermetik (yalnızca 127.0.0.1)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
ok = bad = 0


def t(ad, c):
    global ok, bad
    if c:
        ok += 1
    else:
        bad += 1
        print("BAŞARISIZ:", ad)


def yukle(ad, yol):
    sp = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


V = yukle("varlik_t", R / "sistem" / "varlik" / "varlik.py")

# ---------------------------------------------------------------- kimlik (Wikimedia genel kimliğe 429 verir)
t("User-Agent proje adresini içerir", "https://github.com/" in V.UA and "YSTCoreStudio" in V.UA)
t("User-Agent kişisel veri içermez", "@" not in V.UA)
t("User-Agent ASCII (HTTP başlığı latin-1; Türkçe harf indirmeyi çökertir)", V.UA.isascii())

# ---------------------------------------------------------------- yerel sunucu: 429 davranışı
SAYAC = {"/uzun": 0, "/kisa": 0, "/iyi": 0, "/gorunmez": 0}
KISA_ILK = {"gordu": False}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        SAYAC[self.path] = SAYAC.get(self.path, 0) + 1
        if self.path == "/uzun":   # 120 sn bekle diyen sunucu (Wikimedia'nın verdiği)
            self.send_response(429)
            self.send_header("Retry-After", "120")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/kisa" and not KISA_ILK["gordu"]:   # 1 sn bekle diyen sunucu: bir kez beklenip başarılı olmalı
            KISA_ILK["gordu"] = True
            self.send_response(429)
            self.send_header("Retry-After", "1")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            b = b"merhaba"
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
TAKA = f"http://127.0.0.1:{srv.server_address[1]}"
tmp = Path(tempfile.mkdtemp(prefix="yst_ark_"))

V._SON_ISTEK.clear()
V._ENGEL.clear()
bas = time.time()
try:
    V._indir(TAKA + "/uzun", tmp / "a.bin")
    t("uzun Retry-After: vazgeçilir", False)
except V.SunucuEngeli as e:
    t("uzun Retry-After: SunucuEngeli (120 sn BEKLENMEZ)", time.time() - bas < 10 and "hız sınırı" in str(e))
t("uzun Retry-After: tek istek atıldı", SAYAC["/uzun"] == 1)
bas = time.time()
try:
    V._indir(TAKA + "/uzun", tmp / "b.bin")
    t("devre kesici: aynı sunucuya ikinci istek", False)
except V.SunucuEngeli:
    t("devre kesici: aynı sunucuya ikinci istek ANINDA reddedilir, ağa gidilmez", time.time() - bas < 1 and SAYAC["/uzun"] == 1)

V._ENGEL.clear()
V._SON_ISTEK.clear()
bas = time.time()
V._indir(TAKA + "/kisa", tmp / "c.bin")
t("kısa Retry-After: bir kez beklenip indirilir", (tmp / "c.bin").read_bytes() == b"merhaba" and SAYAC["/kisa"] == 2 and time.time() - bas < 10)

V._ENGEL.clear()
V._indir(TAKA + "/iyi", tmp / "d.bin")
t("normal indirme", (tmp / "d.bin").read_bytes() == b"merhaba")
try:
    V._indir(TAKA + "/yok-dosya-404", tmp / "e.bin")
except Exception as e:  # noqa: BLE001
    t("404 hız sınırı sayılmaz (devre kesici açmaz)", isinstance(e, urllib.error.HTTPError) and not V._ENGEL)
srv.shutdown()
V._ENGEL.clear()
# ulaşılamayan sunucu: engel + hızlı vazgeç
bas = time.time()
try:
    V._indir("http://127.0.0.1:9/x", tmp / "f.bin")
    t("ulaşılamayan sunucu", False)
except V.SunucuEngeli:
    t("ulaşılamayan sunucu: SunucuEngeli, hızlı", time.time() - bas < 30)
V._ENGEL.clear()

# ---------------------------------------------------------------- indir_calistir: engel = ATLANDI (hata değil), diğerleri devam eder
import sqlite3  # noqa: E402

db = tmp / "t.db"
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
c.executescript(V.SEMA)
for kimlik, tur in (("m1", "muzik"), ("m2", "muzik"), ("s1", "sfx")):
    c.execute("INSERT INTO varlik VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (kimlik, tur, kimlik, f"x/{kimlik}.ogg", "url", "https://ornek.invalid/" + kimlik, None, None, "CC0", None, None, "2026-01-01"))
c.commit()
V.ROOT = tmp
gercek = V.getir


def sahte(r):
    if r["id"] == "m1":
        raise V.SunucuEngeli("upload.wikimedia.org hız sınırı uyguluyor (HTTP 429, 120 sn istedi)")
    if r["id"] == "s1":
        return "indirildi"
    raise ValueError("beklenmedik")


V.getir = sahte
ilerleme = []
sonuc = V.indir_calistir(c, None, ilerleme.append)
t("engel → ATLANDI", sonuc["m1"].startswith("ATLANDI"))
t("başka varlık yine indirilir", sonuc["s1"] == "indirildi")
t("beklenmedik istisna → HATA (süreç çökmez)", sonuc["m2"].startswith("HATA"))
t("ilerleme bildirimi yapılır", len(ilerleme) >= 3 and ilerleme[-1]["sira"] == ilerleme[-1]["toplam"])
V.getir = gercek

# çıkış kodları: 0 / 3 (atlandı) / 1 (hata)
sonuclar = {"yalniz_atlandi": {"a": "ATLANDI: x"}, "hata": {"a": "HATA: y", "b": "ATLANDI: x"}, "tamam": {"a": "indirildi"}}
kodlar = {}
for ad, sn in sonuclar.items():
    V.indir_calistir = lambda *a, _sn=sn, **k: _sn
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        kodlar[ad] = V.cmd_indir(None, type("A", (), {"tur": None})())
t("çıkış kodu: hepsi tamam = 0", kodlar["tamam"] == 0)
t("çıkış kodu: yalnız atlananlar = 3 (kurulum bunu hata saymaz)", kodlar["yalniz_atlandi"] == 3)
t("çıkış kodu: gerçek hata = 1", kodlar["hata"] == 1)

# ---------------------------------------------------------------- arka plan yöneticisi
A = yukle("arka_t", R / "sistem" / "araclar" / "arka_indirme.py")
y = tmp / "yerel"
y.mkdir()
A.YEREL, A.DURUM, A.ATLA = y, y / "d.json", y / "a.atla"
EKSIK = {"v": {"model": 12}}
A.ses_ozeti = lambda: {"eksik": 0, "boyut_mb": 0, "istemiyor": False}
A.eksikler = lambda taze=False: EKSIK["v"]

d = A.durum()
t("durum: eksik var, süreç yok → bekliyor", d["kod"] == "bekliyor" and d["eksik_toplam"] == 12 and "model" in d["ozet"])
A._yaz({"calisiyor": True, "pid": __import__("os").getpid(), "nabiz": time.time(), "sira": 3, "toplam": 12, "simdiki": "muzik-x", "sonuc": {}})
d = A.durum()
t("durum: canlı süreç + taze nabız → calisiyor", d["kod"] == "calisiyor" and d["sira"] == 3 and "4/12" in d["ozet"])
A._yaz({"calisiyor": True, "pid": __import__("os").getpid(), "nabiz": time.time() - 999, "sira": 3, "toplam": 12, "simdiki": "x", "sonuc": {}})
t("durum: nabız bayat (süreç öldü sayılır) → calisiyor DEĞİL", A.durum()["kod"] != "calisiyor")
A._yaz({"calisiyor": True, "pid": 999999, "nabiz": time.time(), "sira": 0, "toplam": 0, "simdiki": "", "sonuc": {}})
t("durum: olmayan pid → calisiyor DEĞİL", A.durum()["kod"] != "calisiyor")
A._yaz({"calisiyor": False, "pid": 0, "bitis": time.time(), "sonuc": {"muzik-a": "ATLANDI: upload.wikimedia.org hız sınırı uyguluyor"}, "sira": 12, "toplam": 12})
d = A.durum()
t("durum: atlanan var → sorun, nedeni ve kullanıcı seçenekleri söylenir", d["kod"] == "sorun" and "hız sınırı" in d["ozet"] and d["sonraki_deneme_sn"] > 0)

# otomatik: sorunlu çalıştırmadan hemen sonra tekrar denemez, 1 saat sonra dener
basladi = []
A.baslat = lambda zorla=True: basladi.append(zorla) or {"ok": True}
t("otomatik: sorundan hemen sonra yeniden DENEMEZ (sunucuyu yormaz)", A.otomatik() is None and not basladi)
A._yaz({"calisiyor": False, "pid": 0, "bitis": time.time() - A.YENIDEN_DENE_SN - 5, "sonuc": {"muzik-a": "ATLANDI: x"}})
A.otomatik()
t("otomatik: 1 saat sonra yeniden dener (kullanıcı atlamamışsa), atlama bayrağını SİLMEZ", basladi == [False])

# kullanıcı atla → kendiliğinden başlamaz; baslat(zorla) bayrağı kaldırır
gercek_baslat = A.baslat
uzun = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
A._yaz({"calisiyor": True, "pid": uzun.pid, "nabiz": time.time(), "sira": 1, "toplam": 12, "simdiki": "m", "sonuc": {}})
t("çalışan süreç canlı görünür", A.durum()["calisiyor"])
r = A.atla()
try:
    uzun.wait(timeout=15)
    oldu = True
except subprocess.TimeoutExpired:
    oldu = False
    uzun.kill()
t("atla: çalışan indirme sonlandırılır", oldu)
t("atla: bayrak yazılır, durum 'atlandi'", A.ATLA.exists() and r["kod"] == "atlandi" and not r["calisiyor"])
basladi.clear()
t("atlandıktan sonra otomatik BAŞLAMAZ", A.otomatik() is None and not basladi)
A.baslat = gercek_baslat
EKSIK["v"] = {}
t("eksik yoksa → tamam", A.durum()["kod"] == "tamam")

# müzik + ses efektleri İSTEĞE BAĞLI: eksik olsa da kendiliğinden indirme BAŞLATILMAZ (Wikimedia vb. sunuculara gereksiz yük bindirme)
A.ATLA.unlink(missing_ok=True)
A._yaz({"calisiyor": False, "pid": 0, "sonuc": {}})
EKSIK["v"] = {"muzik": 12, "sfx": 3}
A.ses_ozeti = lambda: {"eksik": 15, "boyut_mb": 130, "istemiyor": False}
d = A.durum()
t("yalnızca müzik/ses eksik → kod tamam (zorunlu bir şey yok), öneri ses alanında", d["kod"] == "tamam" and d["ses"]["eksik"] == 15 and d["eksik_toplam"] == 0)
basladi.clear()
A.baslat = lambda zorla=True, ses=False: basladi.append((zorla, ses)) or {"ok": True}
t("otomatik: yalnızca müzik/ses eksikse HİÇ başlatmaz", A.otomatik() is None and not basladi)
src_ark = (R / "sistem" / "araclar" / "arka_indirme.py").read_text(encoding="utf-8")
t("müzik/ses yalnızca ses=True ile istenir", "if ses:" in src_ark and "turler=SES_TURLER" in src_ark and "SES_TURLER" not in src_ark.split("def calis")[1].split("if ses:")[0])
A.baslat = gercek_baslat
A.ses_istemiyor(True)
t("'gerek yok' kararı kaydedilir ve geri alınabilir", A.SES_ISTEMIYOR.exists() and A.ses_istemiyor(False) is not None and not A.SES_ISTEMIYOR.exists())

# ---------------------------------------------------------------- ağır parçalar arka plan kuyruğunda
t("kuyruk sırası: PyTorch → paketler → modeller", [k["id"] for k in A.KUYRUK][:4] == ["temel", "rclone", "pytorch", "paketler"] and [k["id"] for k in A.KUYRUK if k["tur"] == "hf"][0] == "model-ema")
t("her kalemin ne işe yaradığı ve neye gerektiği yazılı", all(k["ne"] and k["gerek"] and k["gb"] > 0 for k in A.KUYRUK) and A.SES_KALEM["ne"])
t("paketler PyTorch'a bağlı (PyTorch inmeden pip kendi torch'unu çekmesin)", next(k for k in A.KUYRUK if k["id"] == "paketler")["dep"] == "pytorch")
gr = (R / "sistem" / "kurulum" / "gereksinim.txt").read_text(encoding="utf-8")
gml = (R / "sistem" / "kurulum" / "gereksinim-ml.txt").read_text(encoding="utf-8")
agir = ("ema-lightning", "spandrel", "transformers", "pocket-tts-turkish")
t("çekirdek gereksinimde torch'a bağlı ağır paket YOK", not any(a in gr.replace("gereksinim-ml.txt", "") .split("#")[0] + "".join(x.split("#")[0] for x in gr.splitlines()) for a in agir))
t("ağır paketler gereksinim-ml.txt'te", all(a in gml for a in agir) and "PyTorch" in gml)
ksrc = (R / "sistem" / "kurulum" / "kurulum.py").read_text(encoding="utf-8")
t("kurulum PyTorch/yapay zekâ paketlerini KURMAZ (arka planda)", "download.pytorch.org" not in ksrc and "gereksinim-ml" not in ksrc)

# kuyruk yürütme (pip/hf taklit): PyTorch inemezse ona bağlı paketler denenmez, modeller yine iner
EKS = {"pytorch", "paketler", "model-ema", "model-whisper"}
A.kalem_eksik = lambda k: k["id"] in EKS
A.ses_ozeti = lambda: {"eksik": 0, "boyut_mb": 0, "istemiyor": False}
cagri = []
A._pip = lambda args, zaman=3600: cagri.append(("pip", str(args[0]))) or ("ağ yok" if args[0] == "torch" else "")
A._hf = lambda repo, ev: cagri.append(("hf", repo)) or ""
A.YEREL, A.DURUM = y, y / "kuyruk.json"
A.calis(False)
st = json.loads(A.DURUM.read_text(encoding="utf-8"))
t("PyTorch inemedi → paketler ATLANDI (pip çağrılmadı)", st["sonuc"]["pytorch"].startswith("HATA") and st["sonuc"]["paketler"].startswith("ATLANDI") and ("pip", "-r") not in cagri)
t("PyTorch inmese de modeller indirilir", st["sonuc"]["model-ema"] == "indirildi" and ("hf", "canberkkkkkk/ema-lightning") in cagri and st["sonuc"]["model-whisper"] == "indirildi")
t("kalem durumları kaydedilir (arayüz için)", st["kalemler"]["pytorch"]["durum"] == "hata" and st["kalemler"]["paketler"]["durum"] == "atlandi" and st["kalemler"]["model-ema"]["durum"] == "tamam")
t("bitince süreç 'çalışıyor' görünmez", st["calisiyor"] is False and st["bitis"])
# arayüz listesi
EKS.clear(); EKS.update({"pytorch", "model-ema"})
A._yaz({"calisiyor": True, "pid": __import__("os").getpid(), "nabiz": time.time(), "simdiki": "pytorch", "kalemler": {"pytorch": {"durum": "iniyor", "bas": time.time() - 75}}})
kq = {x["id"]: x for x in A.kuyruk(A._oku(), True, {"eksik": 3, "boyut_mb": 130})}
t("kuyruk: çalışan 'iniyor' + geçen süre, bekleyen 'sirada', bitenler 'hazir'", kq["pytorch"]["durum"] == "iniyor" and kq["pytorch"]["gecen_sn"] >= 75 and kq["model-ema"]["durum"] == "sirada" and kq["model-whisper"]["durum"] == "hazir")
t("kuyruk: müzik/ses isteğe bağlı olarak listelenir", kq["ses"]["durum"] == "istege-bagli" and kq["ses"]["gb"] > 0)

# ---------------------------------------------------------------- kurulum: yalnızca paneli açmaya yetecek kadarı; ağır/isteğe bağlı her şey arka planda
t("kurulum 7 adım; varlık/model/rclone adımları ve 'atla' mekanizması kurulumda YOK", "toplam = 7" in ksrc and "a_modeller" not in ksrc and "def a_varlik" not in ksrc and "def a_rclone" not in ksrc
  and "atlanabilir" not in ksrc and "ATLA_BAYRAGI" not in ksrc and "adim(8," not in ksrc)
t("kurulum varlik.py'yi çağırmaz (arka plan kuyruğu yapar)", "varlik.py" not in ksrc)
sih = (R / "sistem" / "kurulum" / "sihirbaz.py").read_text(encoding="utf-8")
html = (R / "sistem" / "kurulum" / "sihirbaz.html").read_text(encoding="utf-8")
t("sihirbazda kurulum adımı atlama düğmesi/API'si yok (önkoşullar için 'Şimdilik atla' ayrıdır)", "adim_atla" not in sih and "adim-atla" not in html and "Bu adımı atla" not in html)
t("rclone arka plan kuyruğunda", any(k["id"] == "rclone" for k in A.KUYRUK) and "eksik_hafif_bilesenler" not in (R / "sistem" / "panel" / "panel.py").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- müzik kaynakları: tek sunucuya yüklenme, lisans kaydı
sc = sqlite3.connect(R / "sistem" / "varlik" / "varliklar.db")
muz = list(sc.execute("select id, kaynak, lisans, sha256 from varlik where tur='muzik'"))
ia = [m for m in muz if m[1].startswith("https://archive.org/download/musopen-chopin/")]
wm = [m for m in muz if "wikimedia" in m[1]]
t("müzik: Chopin kayıtları Internet Archive Musopen (CC0) kaynağından", len(ia) == 12 and all("CC0" in m[2] and len(m[3] or "") == 64 for m in ia))
t("müzik: Wikimedia'ya giden istek en aza indi (yalnızca Satie/Debussy/Vivaldi)", len(wm) == 7 and not any("chopin" in m[0] for m in wm))
t("müzik: her kaydın sha256 ve lisansı var", all(len(m[3] or "") == 64 and m[2] for m in muz))
sc.close()

# ---------------------------------------------------------------- panel bağlantısı
ek = (R / "sistem" / "panel" / "ek_api.py").read_text(encoding="utf-8")
pn = (R / "sistem" / "panel" / "panel.py").read_text(encoding="utf-8")
ix = (R / "sistem" / "panel" / "index.html").read_text(encoding="utf-8")
t("panel: arka plan indirme API'si", '"/api/arka-indirme"' in ek and '"/api/arka-indirme/baslat"' in ek and '"/api/arka-indirme/atla"' in ek)
t("panel: açılışta otomatik başlatır", "otomatik_dongu" in pn)
t("panel arayüzü: durum bandı, Şimdi dene ve Atla", "arkaBant" in ix and 'data-arka="atla"' in ix and "Şimdi dene" in ix)

import shutil  # noqa: E402

shutil.rmtree(tmp, ignore_errors=True)
print(f"{ok} başarılı, {bad} başarısız")
