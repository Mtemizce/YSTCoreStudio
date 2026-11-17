import tempfile
import io, json, os, shutil, sqlite3, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageDraw
import random

R = Path(__file__).resolve().parents[2]
SC = Path(tempfile.mkdtemp(prefix="yst-test-"))
FD = SC / "fakedrive"
S = [0, 0]
KUL = R / "sistem/ayar/kullanici.json"; KY = KUL.read_bytes()
DB = R / "sistem/ortam/arsiv/arsiv.db"; DBY = DB.read_bytes() if DB.exists() else None
ONB = R / "sistem/ortam/arsiv/onbellek"
CONF = R / "sistem/ortam/yerel/rclone.conf"


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


# sahte rclone (depoda: sistem/testler/sahte_rclone.py) + işletim sistemine uygun çağırıcı
FD.mkdir(parents=True, exist_ok=True)
shutil.copy(R / "sistem/testler/sahte_rclone.py", FD / "rclone.py")
if os.name == "nt":
    (FD / "rclone.cmd").write_text("\n".join(["@echo off", f'"{sys.executable}" "%~dp0rclone.py" %*', ""]))
else:
    (FD / "rclone").write_text("\n".join(["#!/bin/sh", f'exec "{sys.executable}" "$(dirname "$0")/rclone.py" "$@"', ""]))
    (FD / "rclone").chmod(0o755)
# sahte Drive içeriği
shutil.rmtree(FD / "drive", ignore_errors=True)
for f in ("state.json", "indirilen.log", "reddet"):
    (FD / f).unlink(missing_ok=True)
random.seed(3)
for yil, proje, n in (("2022", "Villa A", 4), ("2022", "Ofis B", 2), ("2023", "Villa C", 3)):
    d = FD / "drive" / yil / proje
    d.mkdir(parents=True)
    for i in range(n):
        im = Image.new("RGB", (1600, 1100), (random.randint(40, 200),) * 3)
        dr = ImageDraw.Draw(im)
        for _ in range(60):
            x, y = random.randint(0, 1500), random.randint(0, 1000)
            dr.rectangle([x, y, x + random.randint(20, 200), y + random.randint(20, 150)], fill=tuple(random.randint(0, 255) for _ in range(3)))
        im.save(d / f"IMG_{i}.jpg", quality=90)
(FD / "drive" / "2022" / "notlar.bak").write_text("x")
(FD / "drive" / "2022" / "Villa A" / "$RECYCLE").mkdir()

os.environ["YST_RCLONE"] = str(FD / ("rclone.cmd" if os.name == "nt" else "rclone"))  # bu süreç de sahtesini kullansın
env = dict(os.environ, YST_TARAYICI_YOK="1", YST_ARKA_YOK="1", PYTHONUTF8="1", PATH=str(FD) + os.pathsep + os.environ["PATH"],
           YST_RCLONE=str(FD / ("rclone.cmd" if os.name == "nt" else "rclone")))  # kurulumun gerçek rclone'u varsa sahte kullanılsın
PANEL_LOG = SC / "panel.log"
(R / "sistem/ortam/yerel").mkdir(parents=True, exist_ok=True)
(R / "sistem/ortam/yerel/panel.json").unlink(missing_ok=True)  # önceki testten kalan eski port bilgisini okumayalım
srv = subprocess.Popen([sys.executable, str(R / "sistem/panel/panel.py"), "--tarayici-yok"], cwd=str(R), env=env, stdout=open(PANEL_LOG, "w"), stderr=subprocess.STDOUT)
B = None
for _ in range(120):  # yavaş makinelerde (macOS runner) ilk açılış uzun sürebilir
    time.sleep(0.5)
    pj = R / "sistem/ortam/yerel/panel.json"
    if pj.exists():
        try:
            B = "http://127.0.0.1:%d" % json.loads(pj.read_text())["port"]
            urllib.request.urlopen(B + "/api/ping", timeout=2).read()
            break
        except Exception:
            B = None
if not B:
    print("panel başlamadı:", PANEL_LOG.read_text(errors="replace")[-1500:])
    srv.kill()
    sys.exit(1)


def call(m, u, b=None):
    req = urllib.request.Request(B + u, data=json.dumps(b).encode() if b is not None else None, method=m, headers={"X-Panel": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


try:
    s, d = call("GET", "/api/bulutdisk"); ok(s == 200 and d["kurulu"] and d["uzaklar"] == [], f"rclone bulundu, hesap yok ({d.get('yol','')[-30:]})")
    s, r = call("POST", "/api/bulutdisk/baglan", {"ad": "../x", "tur": "drive"}); ok(s == 400, "geçersiz hesap adı reddedildi")
    s, r = call("POST", "/api/bulutdisk/baglan", {"ad": "gdrive", "tur": "ftp"}); ok(s == 400, "geçersiz tür reddedildi")
    s, r = call("POST", "/api/bulutdisk/baglan", {"ad": "gdrive", "tur": "drive"}); ok(s == 200 and r["ok"], "hesap bağlama başladı")
    time.sleep(0.6)
    s, d = call("GET", "/api/bulutdisk"); ok(d["baglan"]["durum"] == "bekliyor" and "127.0.0.1:53682" in (d["baglan"]["url"] or ""), f"izin bekleniyor, bağlantı yakalandı: {d['baglan']['url']}")
    for _ in range(20):
        time.sleep(0.5)
        s, d = call("GET", "/api/bulutdisk")
        if d["baglan"]["durum"] != "bekliyor":
            break
    ok(d["baglan"]["durum"] == "tamam" and d["uzaklar"] and d["uzaklar"][0]["ad"] == "gdrive" and d["uzaklar"][0]["tur"] == "drive", "hesap bağlandı (gdrive: drive)")
    # reddedilen izin
    (FD / "reddet").write_text("1")
    call("POST", "/api/bulutdisk/baglan", {"ad": "kotu", "tur": "dropbox"})
    for _ in range(20):
        time.sleep(0.5)
        s, d = call("GET", "/api/bulutdisk")
        if d["baglan"]["durum"] != "bekliyor":
            break
    ok(d["baglan"]["durum"] == "hata" and not any(u["ad"] == "kotu" for u in d["uzaklar"]), "izin verilmezse hata, hesap eklenmez")
    (FD / "reddet").unlink()
    s, r = call("POST", "/api/bulutdisk/klasorler", {"uzak": "gdrive:"}); ok(r["klasorler"] == ["2022", "2023"], f"kök klasörler: {r}")
    s, r = call("POST", "/api/bulutdisk/klasorler", {"uzak": "gdrive:2022"}); ok(sorted(r["klasorler"]) == ["Ofis B", "Villa A"], "alt klasörler")
    s, r = call("POST", "/api/bulutdisk/klasorler", {"uzak": "gdrive:../.."}); ok(s == 400, "klasör gezintisi (..) reddedildi")
    s, r = call("POST", "/api/bulutdisk/klasorler", {"uzak": "-x:y"}); ok(s == 400, "seçenek gibi yol reddedildi")
    s, r = call("POST", "/api/arsiv/ayarla-uzak", {"uzak": "yok:klasor", "ad": "x"}); ok(s == 400, "bağlı olmayan hesap arşiv olamaz")
    s, r = call("POST", "/api/arsiv/ayarla-uzak", {"uzak": "gdrive:2022", "ad": "drive-test", "gorunen_ad": "Drive 2022"}); ok(s == 200 and r["ayar"]["bagli"], f"bulut arşiv eklendi: {r}")
    kid = r["ayar"]["id"]
    s, d = call("GET", "/api/arsiv/durum")
    a = [x for x in d["arsivler"] if x["id"] == kid][0]
    ok(a["bagli"] and a["adaptor"] == "rclone" and a["uzak"] == "gdrive:2022" and "bulut" in a["tur_bilgi"]["ad"], "arşiv listesinde bulut disk olarak görünüyor")
    # tarama: yalnızca liste
    s, r = call("POST", "/api/arsiv/tara", {"derin": False, "analiz": False, "kok": kid})
    for _ in range(60):
        time.sleep(0.5)
        s, d = call("GET", "/api/arsiv/durum")
        if not d.get("calisiyor"):
            break
    c = sqlite3.connect(DB)
    n = c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0]
    yollar = [x[0] for x in c.execute("SELECT yol FROM dosya WHERE kok_id=? ORDER BY yol", (kid,))]
    ok(n == 6 and all(y.startswith(("Villa A/", "Ofis B/")) for y in yollar), f"tarama 6 fotoğraf buldu (tanınmayan uzantı ve $RECYCLE atlandı): {n}")
    ok(not (FD / "indirilen.log").exists(), "tarama hiçbir dosya indirmedi")
    yil = c.execute("SELECT DISTINCT yil FROM dosya WHERE kok_id=?", (kid,)).fetchall()
    ok(yil == [(2022,)], f"yıl çözüldü: {yil}")
    # önizleme: indirir + önbellekler
    did = c.execute("SELECT id FROM dosya WHERE kok_id=? AND yol='Villa A/IMG_0.jpg'", (kid,)).fetchone()[0]
    with urllib.request.urlopen(urllib.request.Request(B + f"/api/arsiv/onizleme?id={did}", headers={"X-Panel": "1"}), timeout=60) as r:
        data = r.read()
    ok(data[:2] == b"\xff\xd8", "önizleme JPEG döndü (dosya önbelleğe indi)")
    ok((ONB / "drive-test" / "Villa A" / "IMG_0.jpg").is_file(), "önbellekte dosya var")
    # analiz
    s, r = call("POST", "/api/arsiv/analiz", {"kok": kid})
    for _ in range(80):
        time.sleep(0.5)
        s, d = call("GET", "/api/arsiv/durum")
        if not d.get("calisiyor"):
            break
    c = sqlite3.connect(DB)
    na = c.execute("SELECT COUNT(*), SUM(keskinlik IS NOT NULL) FROM analiz WHERE kok_id=?", (kid,)).fetchone()
    ok(na[0] == 6 and na[1] == 6, f"6 fotoğraf analiz edildi (keskinlik ölçüldü): {na}")
    ok(len((FD / "indirilen.log").read_text().split()) >= 6, "analiz dosyaları tek tek indirdi")
    # kopyalama
    os.environ["PATH"] = env["PATH"]
    sys.path.insert(0, str(R / "sistem/arsiv"))
    sys.path.insert(0, str(R / "sistem/araclar"))
    import importlib.util
    sp = importlib.util.spec_from_file_location("ars_t", R / "sistem/arsiv/arsiv.py"); A = importlib.util.module_from_spec(sp); sp.loader.exec_module(A)
    hedef = SC / "kopya_hedef"; shutil.rmtree(hedef, ignore_errors=True)
    ids = [x[0] for x in c.execute("SELECT id FROM dosya WHERE kok_id=? ORDER BY id LIMIT 2", (kid,))]
    k = A.kopyala(ids, str(hedef))
    ok(k["kopyalanan"] == 2 and len(list(hedef.rglob("*.jpg"))) == 2, f"projeye kopyalandı: {k['kopyalanan']} {k['atlanan'][:2]}")
    # ikinci tarama: değişmemiş
    s, r = call("POST", "/api/arsiv/tara", {"derin": False, "analiz": False, "kok": kid})
    for _ in range(60):
        time.sleep(0.5)
        s, d = call("GET", "/api/arsiv/durum")
        if not d.get("calisiyor"):
            break
    ok(d["ilerleme"]["ayni"] == 6 and d["ilerleme"]["yeni"] == 0, f"ikinci tarama: değişmemiş {d['ilerleme'].get('ayni')}")
    # Drive'dan silinen dosya dizinden çıkar
    (FD / "drive" / "2022" / "Ofis B" / "IMG_1.jpg").unlink()
    s, r = call("POST", "/api/arsiv/tara", {"derin": False, "analiz": False, "kok": kid})
    for _ in range(60):
        time.sleep(0.5)
        s, d = call("GET", "/api/arsiv/durum")
        if not d.get("calisiyor"):
            break
    c = sqlite3.connect(DB)
    ok(c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0] == 5, "Drive'dan silinen dosya dizinden çıktı")
    # önbellek boşalt
    s, r = call("POST", "/api/bulutdisk/onbellek-bosalt", {}); ok(s == 200 and not ONB.exists(), f"önbellek boşaldı ({r.get('bosalan_mb')} MB)")
    # hesap kaldırılınca arşiv bağlı değil görünür, kayıtlar silinmez
    s, r = call("POST", "/api/bulutdisk/sil", {"ad": "gdrive"})
    time.sleep(3.5)
    s, d = call("GET", "/api/arsiv/durum")
    a = [x for x in d["arsivler"] if x["id"] == kid][0]
    c = sqlite3.connect(DB)
    ok(not a["bagli"] and "bağlı değil" in a["not"] and c.execute("SELECT COUNT(*) FROM dosya WHERE kok_id=?", (kid,)).fetchone()[0] == 5, f"hesap kalkınca arşiv 'bağlı değil', kayıtlar duruyor: {a['not'][:60]}")
    # profil dışa aktarma jetonları taşır
    CONF.parent.mkdir(parents=True, exist_ok=True); CONF.write_text("[gdrive]\ntype = drive\ntoken = {\"access_token\":\"SIR\"}\n")
    sp = importlib.util.spec_from_file_location("profil_t", R / "sistem/araclar/profil.py"); P = importlib.util.module_from_spec(sp); sp.loader.exec_module(P)
    ic = P.__dict__
    print("profil modülü yüklendi:", [k for k in dir(P) if "disa" in k.lower() or "export" in k.lower()][:5])
finally:
    srv.terminate()
    try:
        srv.wait(timeout=10)
    except subprocess.TimeoutExpired:
        srv.kill()
    for nesne in list(globals().values()):  # açık kalan sqlite bağlantıları Windows'ta dosyayı kilitler
        if isinstance(nesne, sqlite3.Connection):
            try:
                nesne.close()
            except sqlite3.Error:
                pass
    import gc
    gc.collect()  # başka modüllerde referansı kalmamış bağlantılar kapansın
    time.sleep(0.5)
    KUL.write_bytes(KY)
    if DBY is not None:
        DB.write_bytes(DBY)
    else:
        for _ in range(20):  # Windows'ta kapanış gecikebilir: dosya serbest kalana dek dene
            try:
                DB.unlink(missing_ok=True)
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.5)
        else:
            print("UYARI: test veritabanı silinemedi (açık bağlantı); elle sil:", DB)
    shutil.rmtree(ONB, ignore_errors=True)
    shutil.rmtree(SC / "kopya_hedef", ignore_errors=True)
    CONF.unlink(missing_ok=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
