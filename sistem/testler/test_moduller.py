import io, json, os, shutil, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from PIL import Image

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "araclar"))
sys.path.insert(0, str(R / "sistem" / "baglayici"))
import karakter as K, ses_temizle as ST, depolama as D, seri as SE

S = [0, 0]
tmp = Path(tempfile.mkdtemp(prefix="mod-"))


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def foto(w, h, renk=(120, 90, 70)):
    b = io.BytesIO(); Image.new("RGB", (w, h), renk).save(b, "JPEG"); return b.getvalue()


try:
    # ---------------- karakter
    for yol in (R / "kimlik/karakterler/test-kisi", R / "kimlik/seriler/test-dizi"):
        shutil.rmtree(yol, ignore_errors=True)
    for ad, kw, beklenen in [("rızasız", dict(veren="Ali Veli", onay=False), "rıza"), ("isimsiz", dict(veren="", onay=True), "soyad")]:
        try:
            K.olustur("Test Kişi", kw["veren"], kw["onay"], foto(800, 1200), foto(800, 800)); ok(False, f"{ad} reddedilmeli")
        except ValueError as e:
            ok(beklenen in str(e).lower(), f"{ad} karakter oluşmadı: {str(e)[:50]}")
    ok(not (R / "kimlik/karakterler/test-kisi").exists(), "reddedilen karakter diske hiçbir şey bırakmadı")
    try:
        K.olustur("Test Kişi", "Ali Veli", True, b"bozuk", foto(800, 800)); ok(False, "bozuk görüntü reddedilmeli")
    except ValueError as e:
        ok("görüntü" in str(e), "bozuk fotoğraf reddedildi")
    try:
        K.olustur("Test Kişi", "Ali Veli", True, foto(200, 300), foto(800, 800)); ok(False, "küçük foto reddedilmeli")
    except ValueError as e:
        ok("küçük" in str(e), "çok küçük fotoğraf reddedildi")
    ok(not (R / "kimlik/karakterler/test-kisi").exists(), "hatalı oluşturma yarım klasör bırakmadı")
    k = K.olustur("Test Kişi", "Ali Veli", True, foto(900, 1400), foto(900, 900))
    ok(k["id"] == "test-kisi" and k["riza"]["veren"] == "Ali Veli" and k["riza"]["kendi_benzerligi"], "rızalı karakter oluştu")
    ok(K.hazir("test-kisi") == (True, []) and K.liste()[0]["hazir"], "karakter hazır (rıza + iki fotoğraf)")
    ok(K.yollar("test-kisi")["boy"].endswith("boy.jpg"), "yollar()")
    try:
        K.olustur("Test Kişi", "Ali Veli", True, foto(900, 1400), foto(900, 900)); ok(False, "aynı ad reddedilmeli")
    except ValueError:
        ok(True, "aynı adlı ikinci karakter reddedildi")

    # ---------------- ses temizleme
    g = tmp / "kayit.wav"
    # gürültü + sessizlik + konuşma benzeri ton + sessizlik
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=1.5:c=pink:a=0.05", "-f", "lavfi", "-i", "sine=f=300:d=2", "-f", "lavfi", "-i", "anoisesrc=d=2:c=pink:a=0.05",
                    "-filter_complex", "[1:a]volume=0.4[s];[0:a][s][2:a]concat=n=3:v=0:a=1", str(g)], check=True)
    r = ST.temizle(str(g), str(tmp / "temiz.wav"))
    print("   ", r["once"], "→", r["sonra"], r["adimlar"])
    ok(Path(r["dosya"]).is_file() and r["sonra"]["sure"] < r["once"]["sure"], f"baştaki/sondaki boşluklar kırpıldı: {r['once']['sure']} → {r['sonra']['sure']} sn")
    ok(r["sonra"]["tepe_db"] is not None and r["sonra"]["tepe_db"] <= -0.5, f"tepe sınırlandı ({r['sonra']['tepe_db']} dB)")
    ok("loudnorm" in r["adimlar"] and "afftdn" in r["adimlar"] and "silenceremove" in r["adimlar"], "zincir: gürültü azaltma + kırpma + seviye")
    r2 = ST.bayttan(g.read_bytes(), str(tmp / "temiz2.wav"), ".wav", kirpma=False)
    ok(Path(r2["dosya"]).is_file() and abs(r2["sonra"]["sure"] - r2["once"]["sure"]) < 0.3, "kırpma kapatılınca süre korunuyor")

    # ---------------- depolama: sahte rclone + sahte storage.to
    sahte = tmp / "bin"; sahte.mkdir()
    py = sys.executable
    (sahte / "rclone_sahte.py").write_text('''import json, os, shutil, sys
a = sys.argv[1:]
if a[0] == "version": print("rclone v9.9.9-sahte")
elif a[0] == "listremotes": print("surucum:"); print("dropbox:")
elif a[0] == "lsjson": print(json.dumps([{"Path": "2023/a.jpg", "Size": 1234, "ModTime": "2023-01-01T00:00:00Z"}]))
elif a[0] == "copy":
    os.makedirs(a[2], exist_ok=True); open(os.path.join(a[2], "uzaktan.jpg"), "wb").write(b"X" * 100)
elif a[0] == "copyto": print("kopyalandi", a[1], a[2])
''', encoding="utf-8")
    if os.name == "nt":
        cagirici = sahte / "rclone.cmd"
        cagirici.write_text("\n".join(["@echo off", f'"{py}" "{sahte / "rclone_sahte.py"}" %*', ""]), encoding="utf-8")
    else:
        cagirici = sahte / "rclone"
        cagirici.write_text("\n".join(["#!/bin/sh", f'exec "{py}" "{sahte / "rclone_sahte.py"}" "$@"', ""]), encoding="utf-8")
        cagirici.chmod(0o755)
    os.environ["PATH"] = str(sahte) + os.pathsep + os.environ["PATH"]
    os.environ["YST_RCLONE"] = str(cagirici)  # kurulumun getirdiği gerçek rclone varsa o değil, sahtesi kullanılsın
    d = D.durum()
    ok(d["kurulu"] and d["uzaklar"] == ["surucum:", "dropbox:"], f"rclone algılandı, uzaklar: {d['uzaklar']}")
    ok(D.liste("surucum:Arsiv")[0]["yol"] == "2023/a.jpg", "uzak liste (lsjson)")
    for kotu in ("-rf:x", "bosluk yok", "a:b\nc", "--config=/x:y"):
        try:
            D._uzak(kotu); ok(False, f"reddedilmeli: {kotu!r}")
        except ValueError:
            ok(True, f"uzak yol deseni reddetti: {kotu!r}")
    (R / "projeler" / "zz-mod-test" / "kaynak").mkdir(parents=True, exist_ok=True)
    (R / "projeler" / "zz-mod-test" / "cikti").mkdir(parents=True, exist_ok=True)
    r = D.indir("surucum:Arsiv/2023", "zz-mod-test")
    ok(r["dosya"] == 1 and r["hedef"] == "projeler/zz-mod-test/kaynak/uzak", f"uzaktan projeye kopyalandı: {r}")
    try:
        D.indir("surucum:x", "../kacak"); ok(False, "proje adı gezintisi reddedilmeli")
    except ValueError:
        ok(True, "proje adı yol gezintisi reddedildi")
    video = R / "projeler" / "zz-mod-test" / "cikti" / "final.mp4"; video.write_bytes(b"VIDEO" * 2000)
    try:
        D.yukle(str(video), "surucum:Cikti", False); ok(False, "onaysız yükleme reddedilmeli")
    except ValueError as e:
        ok("onay" in str(e), "uzak depoya yazma onay istedi")
    ok("final.mp4" == D.yukle(str(video), "surucum:Cikti", True)["dosya"], "onayla yüklendi")
    for kotu in (R / "kimlik" / "PROFIL.md", R / "sistem" / "ortam" / "baglayici" / "anahtar.json", R / "projeler" / "zz-mod-test" / "kaynak" / "uzak" / "uzaktan.jpg"):
        try:
            D._cikti_dosyasi(str(kotu)); ok(False, f"gönderilemez olmalı: {kotu.name}")
        except ValueError:
            ok(True, f"dışarı gönderilemez: {kotu.name}")

    alinan = {}

    class Sahte(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_POST(self):
            n = int(self.headers["Content-Length"]); veri = self.rfile.read(n)
            alinan.update({"ct": self.headers["Content-Type"], "n": n, "icerik_var": b"VIDEOVIDEO" in veri, "ad": b'filename="final.mp4"' in veri})
            b = json.dumps({"success": True, "url": "https://storage.to/s/abc123", "raw_url": "https://storage.to/raw/abc123"}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    srv = HTTPServer(("127.0.0.1", 0), Sahte); threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        D.paylas(str(video), False); ok(False, "onaysız paylaşım reddedilmeli")
    except ValueError:
        ok(True, "storage.to paylaşımı açık onay istedi (onaysız dosya çıkmadı)")
    r = D.paylas(str(video), True, f"http://127.0.0.1:{srv.server_address[1]}/api/sharex/upload")
    ok(r["baglanti"] == "https://storage.to/s/abc123" and alinan["icerik_var"] and alinan["ad"] and "multipart" in alinan["ct"], f"multipart akışı yüklendi, bağlantı alındı: {r['baglanti']}")
    ok(alinan["n"] > 10000, f"gövde dosyayı kapsıyor ({alinan['n']} bayt, bellek yerine akış)")
    srv.shutdown()
    log = (R / "sistem/ortam/arsiv/bulut_gunlugu.md").read_text(encoding="utf-8") if (R / "sistem/ortam/arsiv/bulut_gunlugu.md").exists() else ""
    ok("storage.to" in log and "rclone" in log, "dış gönderimler bulut günlüğüne yazıldı")

    # ---------------- seri
    s = SE.olustur("Test Dizi", "dizi", "Bir mimarın ofis günlükleri", ["test-kisi"], "sakin, sıcak")
    ok(s["id"] == "test-dizi" and s["karakterler"] == ["test-kisi"], "seri oluştu")
    try:
        SE.olustur("Başka", "dizi", "", ["yok-boyle"]); ok(False, "olmayan karakter reddedilmeli")
    except ValueError:
        ok(True, "olmayan karakterli seri reddedildi")
    try:
        SE.olustur("Test Dizi", "film"); ok(False, "geçersiz tür reddedilmeli")
    except ValueError:
        ok(True, "geçersiz tür reddedildi")
    b1 = SE.bolum_ekle("test-dizi", 1, "Pilot", "Tanışma")
    ok(b1["proje"] == "test-dizi-s01b01" and (R / "projeler/test-dizi-s01b01/brief.md").is_file(), f"bölüm projesi açıldı: {b1['proje']}")
    u = json.loads((R / "projeler/test-dizi-s01b01/uretim.json").read_text(encoding="utf-8"))
    ok(all(u["seri"].get(k) == v for k, v in {"id": "test-dizi", "sezon": 1, "bolum": 1, "bolum_adi": "Pilot"}.items()) and u["seri"]["ad"], "uretim.json'a seri bilgisi yazıldı (dizi adı, sezon, bölüm, bölüm adı)")
    SE.ozet_yaz("test-dizi", 1, 1, "Ofis açıldı, ilk müşteri geldi.")
    b2 = SE.bolum_ekle("test-dizi", 1, "İlk iş", "Villa tadilatı")
    bag = (R / "projeler/test-dizi-s01b02/seri_baglami.md").read_text(encoding="utf-8")
    ok("S01B01 Pilot: Ofis açıldı, ilk müşteri geldi." in bag and "Test Kişi" in bag and "sakin, sıcak" in bag, "2. bölüm bağlamı: önceki bölüm özeti + karakter + stil")
    ok(SE.liste()[0]["bolum"] == 2, "liste: 2 bölüm")
finally:
    for yol in (R / "kimlik/karakterler/test-kisi", R / "kimlik/seriler/test-dizi", R / "projeler/zz-mod-test", R / "projeler/test-dizi-s01b01", R / "projeler/test-dizi-s01b02"):
        shutil.rmtree(yol, ignore_errors=True)
    (R / "sistem/ortam/arsiv/bulut_gunlugu.md").unlink(missing_ok=True)
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
