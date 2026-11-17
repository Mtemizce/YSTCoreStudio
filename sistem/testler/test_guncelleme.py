import hashlib, http.server, importlib.util, io, json, os, shutil, sqlite3, subprocess, sys, tempfile, threading, zipfile
from pathlib import Path

R = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="yst_gunc_"))
S = [0, 0]
TOKEN = "github_pat_TESTTOKEN0123456789abcdef"


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


# ---------------------------------------------------------------- sahte GitHub
def zip_olustur() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("YSTCoreStudio/sistem/surum.json", json.dumps({"uygulama": "9.9.9"}))
        z.writestr("YSTCoreStudio/README.md", "yeni readme")
        z.writestr("YSTCoreStudio/sistem/araclar/yeni_dosya.txt", "merhaba")
        z.writestr("YSTCoreStudio/kimlik/PROFIL.md", "SABLON: kullanıcının dosyasını ezmemeli")
        z.writestr("YSTCoreStudio/kimlik/YENI_SABLON.md", "eksik olduğu için eklenmeli")
        z.writestr("YSTCoreStudio/sistem/ayar/kullanici.json", '{"ajanlar": {"x": 1}}')
        z.writestr("YSTCoreStudio/projeler/x/y.txt", "proje dosyasına dokunulmamalı")
        z.writestr("YSTCoreStudio/sistem/ortam/yerel/z.txt", "ortam korunmalı")
        z.writestr("YSTCoreStudio/../kacak.txt", "yol kaçışı")
    return b.getvalue()


ZIPB = zip_olustur()
SHA = hashlib.sha256(ZIPB).hexdigest()
ISTEKLER = []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _yetki(self):
        ISTEKLER.append((self.path, self.headers.get("Authorization")))
        if self.headers.get("Authorization") != "Bearer " + TOKEN:
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"message":"Bad credentials"}'); return False
        return True

    def _json(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/indir/"):  # gerçek GitHub'da varlık adresi başka bir sunucuya yönlenir: yetki başlığı gelmemeli
            ISTEKLER.append((self.path, self.headers.get("Authorization")))
            b = ZIPB if "zip" in self.path and "sha" not in self.path else (SHA + "  YSTCoreStudio-9.9.9.zip\n").encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if not self._yetki():
            return
        p = self.path
        if p == "/repos/o/r/releases/latest":
            self._json({"tag_name": "v9.9.9", "body": "Sürüm notları: yeni özellikler", "assets": [
                {"name": "YSTCoreStudio-9.9.9.zip", "url": f"http://127.0.0.1:{PORT}/asset/zip"},
                {"name": "YSTCoreStudio-9.9.9.zip.sha256", "url": f"http://127.0.0.1:{PORT}/asset/sha"}]})
        elif p.startswith("/asset/"):
            self.send_response(302); self.send_header("Location", f"http://localhost:{PORT}/indir/{p.split('/')[-1]}"); self.end_headers()  # farklı host adı: başlık silinmeli
        elif p.startswith("/repos/o/r/commits/"):
            self._json({"sha": SHA_UZAK[0], "commit": {"message": "yeni commit"}})
        else:
            self.send_response(404); self.end_headers()


SHA_UZAK = ["0" * 40]
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["YST_GUNCELLEME_API"] = f"http://127.0.0.1:{PORT}"


def yukle(kok: Path):
    os.environ["YST_GUNCELLEME_KOK"] = str(kok)
    sp = importlib.util.spec_from_file_location("gunc_t_" + kok.name, R / "sistem/araclar/guncelleme.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


try:
    # ================================================================ ZIP kurulumu
    kok = TMP / "zipkok"
    (kok / "sistem" / "ayar").mkdir(parents=True)
    (kok / "sistem" / "ortam" / "arsiv").mkdir(parents=True)
    (kok / "sistem" / "ortam" / "yerel").mkdir(parents=True)
    (kok / "kimlik").mkdir()
    (kok / "projeler" / "x").mkdir(parents=True)
    (kok / "sistem" / "surum.json").write_text(json.dumps({"uygulama": "0.6.0"}))
    (kok / "README.md").write_text("eski readme")
    (kok / "kimlik" / "PROFIL.md").write_text("KULLANICININ KENDİ PROFİLİ")
    (kok / "sistem" / "ayar" / "kullanici.json").write_text('{"ajanlar": {}, "benim": true}')
    (kok / "projeler" / "x" / "y.txt").write_text("benim projem")
    db = sqlite3.connect(kok / "sistem/ortam/arsiv/arsiv.db"); db.execute("create table t(a)"); db.execute("insert into t values('veri')"); db.commit(); db.close()
    G = yukle(kok)
    ok(G.ayar_oku()["etkin"] is False, "ayar yokken etkin değil")
    for kotu in ("kotu depo", "a/b/c", "../x", ""):
        if kotu == "":
            continue
        try:
            G.ayar_yaz(kotu, TOKEN); ok(False, f"geçersiz depo kabul edildi: {kotu}")
        except ValueError:
            ok(True, f"geçersiz depo reddedildi: {kotu!r}")
    try:
        G.ayar_yaz("o/r", "kısa"); ok(False, "geçersiz jeton kabul edildi")
    except ValueError:
        ok(True, "geçersiz jeton reddedildi")
    a = G.ayar_yaz("o/r", TOKEN)
    ok(a["etkin"] and a["jeton_var"] and "jeton" not in a and TOKEN not in json.dumps(G.durum()), "ayar kaydedildi; jeton arayüze geri verilmiyor")
    ok(oct((kok / "sistem/ortam/baglayici/guncelleme.json").stat().st_mode & 0o777) in ("0o600", "0o666"), "jeton dosyası")
    # yanlış jeton
    G.ayar_yaz("o/r", "github_pat_YANLISYANLISYANLIS12345")
    k = G.kontrol(); ok(not k["var"] and "jeton" in k["hata"], f"yanlış jeton: {k['hata']}")
    G.ayar_yaz("o/r", TOKEN)
    k = G.kontrol(); ok(k["var"] and k["yeni"] == "9.9.9" and "yeni özellikler" in k["notlar"], f"güncelleme var: {k['mevcut']} → {k['yeni']}")
    ok(G.durum()["kontrol"]["var"], "durum dosyasına yazıldı")
    G._is()
    r = json.loads((kok / "sistem/ortam/yerel/guncelleme_rapor.json").read_text(encoding="utf-8"))
    ok(r["ok"] and r["yeni_surum"] == "9.9.9", f"güncelleme tamam: {r.get('onceki')} → {r.get('yeni_surum')} {r.get('hata','')}")
    ok(json.loads((kok / "sistem/surum.json").read_text())["uygulama"] == "9.9.9", "sürüm dosyası güncellendi")
    ok((kok / "README.md").read_text() == "yeni readme" and (kok / "sistem/araclar/yeni_dosya.txt").read_text() == "merhaba", "dosyalar yerleşti")
    ok((kok / "kimlik/PROFIL.md").read_text() == "KULLANICININ KENDİ PROFİLİ", "kimlik/PROFIL.md ezilmedi")
    ok((kok / "kimlik/YENI_SABLON.md").exists(), "kimlikte eksik şablon eklendi")
    ok(json.loads((kok / "sistem/ayar/kullanici.json").read_text()) == {"ajanlar": {}, "benim": True}, "kullanici.json ezilmedi")
    ok((kok / "projeler/x/y.txt").read_text() == "benim projem", "projelere dokunulmadı")
    ok(not (kok / "sistem/ortam/yerel/z.txt").exists(), "sistem/ortam korundu (zip'ten yazılmadı)")
    ok(not (TMP / "kacak.txt").exists() and not (kok.parent / "kacak.txt").exists(), "yol kaçışı (..) engellendi")
    yedek = list((kok / "sistem/ortam/yedek").glob("guncelleme-*"))
    ok(len(yedek) == 1 and (yedek[0] / "arsiv.db").is_file(), "veritabanı yedeği alındı")
    yd = sqlite3.connect(yedek[0] / "arsiv.db"); ok(yd.execute("select a from t").fetchone() == ("veri",), "yedek içeriği doğru"); yd.close()
    ok((yedek[0] / "ayar" / "kullanici.json").is_file() and (yedek[0] / "kimlik" / "PROFIL.md").is_file(), "ayar ve kimlik yedeği")
    # asset indirmede yetki başlığı başka sunucuya gönderilmedi
    indir = [x for x in ISTEKLER if x[0].startswith("/indir/")]
    ok(indir and all(h is None for _, h in indir), "yönlendirilen indirme adresine jeton gönderilmedi")
    k2 = G.kontrol(); ok(not k2["var"], "güncellemeden sonra tekrar kontrol: güncel")
    G._is()
    ok("zaten güncel" in G.durum()["rapor"].get("hata", ""), "güncel iken güncelle: reddedildi")
    # sağlama toplamı uyuşmazlığı
    (kok / "sistem/surum.json").write_text(json.dumps({"uygulama": "0.6.0"}))
    eski = ZIPB
    ZIPB = b"bozuk" + ZIPB
    G._is()
    ok(not G.durum()["rapor"]["ok"] and "sağlama" in G.durum()["rapor"]["hata"], "bozuk paket: sağlama toplamı uyuşmadı, güncelleme iptal")
    ok((kok / "README.md").read_text() == "yeni readme", "iptalde dosyalar değişmedi")
    ZIPB = eski

    # ================================================================ KLON (git)
    ortam = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    g = lambda cwd, *a: subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True, env=ortam)
    bare = TMP / "uzak.git"; g(TMP, "init", "--bare", "-b", "main", str(bare))
    a1 = TMP / "a1"; g(TMP, "clone", str(bare), str(a1))
    (a1 / "sistem").mkdir(); (a1 / "sistem/surum.json").write_text(json.dumps({"uygulama": "1.0.0"})); (a1 / "x.txt").write_text("1")
    g(a1, "add", "-A"); g(a1, "commit", "-m", "ilk"); g(a1, "push", "origin", "HEAD:main")
    klon = TMP / "klon"; g(TMP, "clone", str(bare), str(klon)); g(klon, "checkout", "main")
    (klon / "sistem/ortam/yerel").mkdir(parents=True); (klon / "sistem/ortam/yerel/panel.json").write_text("{}")
    GK = yukle(klon)
    GK.ayar_yaz("o/r", TOKEN)
    SHA_UZAK[0] = g(klon, "rev-parse", "HEAD").stdout.strip()
    k = GK.kontrol(); ok(k["tur"] == "klon" and not k["var"], "klon: yerel = uzak → güncel")
    (a1 / "x.txt").write_text("2"); g(a1, "add", "-A"); g(a1, "commit", "-m", "ikinci"); g(a1, "push", "origin", "HEAD:main")
    SHA_UZAK[0] = g(a1, "rev-parse", "HEAD").stdout.strip()
    k = GK.kontrol(); ok(k["var"] and k["yeni"] == SHA_UZAK[0][:8], f"klon: uzakta yeni commit var ({k['yeni']})")
    (klon / "x.txt").write_text("yerel değişiklik")
    GK._is(); r = GK.durum()["rapor"]
    ok(not r["ok"] and "kaydedilmemiş" in r["hata"] and (klon / "x.txt").read_text() == "yerel değişiklik", "klon: kirli çalışma ağacında güncelleme durdu, değişiklik korundu")
    g(klon, "checkout", "--", "x.txt")
    GK._is(); r = GK.durum()["rapor"]
    ok(r["ok"] and (klon / "x.txt").read_text() == "2", f"klon: git pull uygulandı ({r.get('adimlar')})")
    ok(any("git pull" in x for x in r["adimlar"]), "klon: rapor adımları")
finally:
    srv.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
