import base64, io, json, os, shutil, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path
from PIL import Image

R = Path(__file__).resolve().parents[2]
S = [0, 0]
KUL = R / "sistem/ayar/kullanici.json"; KY = KUL.read_bytes()


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def foto(w, h):
    b = io.BytesIO(); Image.new("RGB", (w, h), (130, 100, 80)).save(b, "JPEG"); return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


env = dict(os.environ, YST_TARAYICI_YOK="1", YST_ARKA_YOK="1", PYTHONUTF8="1")
PANEL_LOG = Path(tempfile.gettempdir()) / "yst-test-modul-panel.log"
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
if B is None:
    if srv.poll() is None:
        srv.kill()
        srv.wait(timeout=5)
    raise AssertionError("panel başlamadı: " + PANEL_LOG.read_text(errors="replace")[-1500:])


def call(m, u, b=None, hdr=True, raw=None, ek=None):
    h = {"X-Panel": "1"}
    if raw is None:
        h["Content-Type"] = "application/json"
    h.update(ek or {})
    req = urllib.request.Request(B + u, data=raw if raw is not None else (json.dumps(b).encode() if b is not None else None), method=m, headers=h if hdr else {})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


proje = None
try:
    s, r = call("GET", "/api/karakter"); ok(s == 200 and r["karakterler"] == [] and "rıza" in r["riza_metni"].lower() or "izin" in r["riza_metni"].lower(), "karakter listesi boş + rıza metni")
    s, r = call("POST", "/api/karakter/olustur", {"ad": "Test Kişi", "veren": "Ali Veli", "onay": False, "boy_b64": foto(900, 1400), "portre_b64": foto(900, 900)}); ok(s == 400 and "rıza" in r["hata"], "rızasız karakter API'de reddedildi")
    s, r = call("POST", "/api/karakter/olustur", {"ad": "Test Kişi", "veren": "Ali Veli", "onay": True, "boy_b64": foto(900, 1400), "portre_b64": foto(900, 900)}); ok(s == 200 and r["karakter"]["id"] == "test-kisi", "rızalı karakter oluşturuldu")
    s, r = call("GET", "/api/karakter"); ok(r["karakterler"][0]["hazir"], "karakter hazır")
    # B planı: karaktersiz üret reddedilir, karakterle kabul
    govde = {"prompt": "villa tadilatı tanıtım videosu, sakin ve güven veren", "platformlar": ["youtube-yatay"], "seslendirme": {"acik": False}, "gorsel_uret": {"acik": False}, "ad": "zz-bplan-test",
             "b_plani": {"acik": True, "karakter": "yok-boyle", "etiket": True}}
    s, r = call("POST", "/api/uret", govde); ok(s == 400 and "karakter" in r["hata"], "B planı: olmayan karakter reddedildi")
    govde["b_plani"] = {"acik": True, "karakter": "test-kisi", "etiket": True, "uretken": True}
    s, r = call("POST", "/api/uret", govde); ok(s == 400 and "bulut" in r["hata"], "üretken ikiz bulut izni olmadan reddedildi")
    govde["b_plani"]["uretken"] = False
    s, r = call("POST", "/api/uret", govde); ok(s == 200, f"B planlı proje kuruldu: {str(r)[:80]}")
    proje = r.get("proje")
    u = json.loads((R / "projeler" / proje / "uretim.json").read_text(encoding="utf-8"))
    ok(u["b_plani"]["karakter"] == "test-kisi" and u["b_plani"]["etiket"] is True and u["b_plani"]["uretken"] is False, "uretim.json'da b_plani var")
    ok("B PLANI" in (R / "projeler" / proje / "brief.md").read_text(encoding="utf-8"), "brief.md'ye B planı notu düştü")
    s, r = call("POST", "/api/b-plani", {"proje": proje, "karakter": "test-kisi", "etiket": False}); ok(s == 200 and r["b_plani"]["etiket"] is False, "mevcut projeye B planı yazıldı (etiket kapalı)")
    s, r = call("POST", "/api/b-plani", {"proje": proje, "karakter": "yok"}); ok(s == 400, "hazır olmayan karakterle B planı reddedildi")
    # ses kaydı
    wav = Path(tempfile.gettempdir()) / "yst_test_kayit.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=1:c=pink:a=0.04", "-f", "lavfi", "-i", "sine=f=300:d=1.5", "-filter_complex", "[1:a]volume=0.4[s];[0:a][s]concat=n=2:v=0:a=1", str(wav)], check=True)
    s, r = call("POST", f"/api/ses/kaydet?proje={proje}&uz=wav", raw=wav.read_bytes()); ok(s == 200 and r["dosya"] == "kaynak/ses/kayit-01.wav" and (R / "projeler" / proje / r["dosya"]).is_file(), f"ses kaydı temizlenip projeye eklendi: {r.get('once')} → {r.get('sonra')}")
    s, r = call("POST", "/api/ses/kaydet?proje=../x&uz=wav", raw=b"x" * 100); ok(s == 400, "ses kaydında proje adı gezintisi reddedildi")
    s, r = call("POST", "/api/ses/kaydet?proje=" + proje, raw=b"", ek={"Content-Type": "application/octet-stream"}); ok(s == 400, "boş kayıt reddedildi")
    # depolama
    s, r = call("GET", "/api/depolama"); ok(s == 200 and "kurulu" in r, f"depolama durumu (rclone kurulu: {r.get('kurulu')})")
    s, r = call("POST", "/api/depolama/paylas", {"dosya": f"projeler/{proje}/cikti/x.mp4", "onay": False}); ok(s == 400 and "onay" in r["hata"], "paylaşım onaysız reddedildi")
    s, r = call("POST", "/api/depolama/yukle", {"dosya": "kimlik/PROFIL.md", "uzak": "a:b", "onay": True}); ok(s == 400, "kimlik dosyası dışarı gönderilemez")
    s, r = call("POST", "/api/depolama/indir", {"uzak": "-x:y", "proje": proje}); ok(s == 400, "geçersiz uzak yol reddedildi")
    # seri
    s, r = call("POST", "/api/seri/olustur", {"ad": "Test Dizi", "tur": "dizi", "aciklama": "deneme", "karakterler": ["test-kisi"]}); ok(s == 200, "seri oluştu")
    s, r = call("POST", "/api/seri/bolum", {"seri": "test-dizi", "sezon": 1, "ad": "Pilot", "ozet": "tanışma"}); ok(s == 200 and r["bolum"]["proje"] == "test-dizi-s01b01", "bölüm projesi açıldı")
    s, r = call("POST", "/api/seri/ozet", {"seri": "test-dizi", "sezon": 1, "bolum": 1, "ozet": "bitti"}); ok(s == 200, "bölüm özeti yazıldı")
    s, r = call("GET", "/api/seri"); ok(r["seriler"][0]["bolum"] == 1 and "test-kisi" in r["karakterler"], "seri listesi")
    # sistem ayarı hâlâ sağlam
    s, r = call("GET", "/api/ping"); ok(s == 200, "panel ayakta")
finally:
    srv.terminate(); time.sleep(0.5)
    KUL.write_bytes(KY)
    for y in (R / "kimlik/karakterler/test-kisi", R / "kimlik/seriler/test-dizi", R / "projeler/test-dizi-s01b01"):
        shutil.rmtree(y, ignore_errors=True)
    if proje:
        shutil.rmtree(R / "projeler" / proje, ignore_errors=True)
    for y in (R / "kimlik/karakterler", R / "kimlik/seriler"):
        try:
            y.rmdir()
        except OSError:
            pass
    (R / "sistem/ortam/arsiv/bulut_gunlugu.md").unlink(missing_ok=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
