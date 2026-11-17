"""Kurgu yaması (sistem/kurulum/kurgu_yama.py) ve Kurgu içi eklenti (sistem/yama/kurgu_ek/yst_ek.py): ağ ve gerçek Kurgu gerekmez.
Sahte bir Kurgu klasörüne yama uygulanır: idempotent mi, CRLF korunuyor mu, çapa bulunamazsa hiçbir dosyaya dokunulmuyor mu, kontrol modu doğru mu;
sonra eklentinin seslendirme önbelleği ve sınır denetimleri sahte bir motorla denenir."""
import importlib.util
import os
import shutil
import sys
import tempfile
import wave
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def yukle(ad, yol):
    sp = importlib.util.spec_from_file_location(ad, yol)
    m = importlib.util.module_from_spec(sp)
    sys.modules[ad] = m
    sp.loader.exec_module(m)
    return m


Y = yukle("kurgu_yama_t", R / "sistem" / "kurulum" / "kurgu_yama.py")
tmp = Path(tempfile.mkdtemp(prefix="yst-yama-"))


def sahte_kurgu(ad, crlf=False):
    k = tmp / ad
    (k / "web" / "js").mkdir(parents=True)
    srv = 'import os\nimport agent_notes\nimport ai\n\nclass H:\n    def api(self, path, method, q):\n        if x:\n            pass\n        else:\n            raise HttpError(404, "not found")\n        raise HttpError(405, "method not allowed")\n'
    idx = "<html><head><title>k</title></head><body><div id=\"toasts\"></div></body></html>\n"
    py = 'py-modules = ["server", "guidance_gen"]\n'
    for ad_, s in (("server.py", srv), ("web/index.html", idx), ("pyproject.toml", py)):
        (k / ad_).write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
    return k


try:
    # --- bindirme (sistem/yama/kurgu) pyproject.toml'u Kurgu'nunkini değiştirir: çapa ONDA da tam bir kez olmalı (kurulum sırası: bindirme, sonra eklenti)
    bind = (R / "sistem" / "yama" / "kurgu" / "pyproject.toml").read_text(encoding="utf-8")
    pyek = [e for e in Y.EKLER if e["dosya"] == "pyproject.toml"][0]
    ok(bind.count(pyek["degistir"][0]) == 1, "bindirmedeki pyproject.toml eklenti çapasını tam bir kez içerir")
    # --- uygulama
    k = sahte_kurgu("a")
    on = Y.kontrol(k)
    ok(not on["tamam"] and all(v == "uygulanabilir" for v in on["ekler"].values()), "kontrol: uygulanmamış Kurgu 'uygulanabilir' görünür")
    r = Y.uygula(k)
    ok(len(r["eklenen"]) == 5 and not r["zaten"] and "yst_ek.py" in r["kopyalanan"], "uygula: 5 ek ve eklenti dosyaları kopyalandı")
    srv = (k / "server.py").read_text(encoding="utf-8")
    ok("import yst_ek  # YST-EK" in srv and srv.index("import yst_ek") > srv.index("import agent_notes"), "server.py: import çapanın hemen sonrasına eklendi")
    ok(srv.index("/api/yst/") < srv.index('raise HttpError(404, "not found")'), "server.py: /api/yst/ yönlendirmesi 404'ten ÖNCE")
    ok("yst.css" in (k / "web" / "index.html").read_text(encoding="utf-8") and "yst.js" in (k / "web" / "index.html").read_text(encoding="utf-8"), "index.html: stil ve betik bağlandı")
    ok('"yst_ek"]' in (k / "pyproject.toml").read_text(encoding="utf-8"), "pyproject.toml: modül adı eklendi")
    ok(Y.kontrol(k)["tamam"], "kontrol: uygulanmış Kurgu 'tamam'")
    # --- idempotent
    once = {f: (k / f).read_bytes() for f in ("server.py", "web/index.html", "pyproject.toml")}
    r2 = Y.uygula(k)
    ok(not r2["eklenen"] and len(r2["zaten"]) == 5, "ikinci uygulama: hiçbir şey eklenmedi (idempotent)")
    ok(all((k / f).read_bytes() == b for f, b in once.items()), "ikinci uygulama: dosyalar bayt bayt aynı")
    # --- eklenti dosyası güncellenir (yama yeniden çekilen Kurgu'ya geri gelir)
    (k / "yst_ek.py").write_text("eski", encoding="utf-8")
    Y.uygula(k)
    ok((k / "yst_ek.py").read_bytes() == (R / "sistem" / "yama" / "kurgu_ek" / "yst_ek.py").read_bytes(), "eklenti dosyası her uygulamada güncellenir")
    # --- CRLF korunur
    kc = sahte_kurgu("c", crlf=True)
    Y.uygula(kc)
    ham = (kc / "server.py").read_bytes()
    ok(ham.count(b"\r\n") == ham.count(b"\n") and b"yst_ek" in ham, "CRLF'li Kurgu: satır sonları korunur, ek tek tip")
    ok(Y.uygula(kc)["eklenen"] == [], "CRLF'li Kurgu: ikinci uygulama da idempotent")
    # --- çapa yoksa: hiçbir dosyaya dokunma
    kb = sahte_kurgu("b")
    (kb / "web" / "index.html").write_text("<html><body>başlık yok</body></html>\n", encoding="utf-8")
    ilk = {f: (kb / f).read_bytes() for f in ("server.py", "web/index.html", "pyproject.toml")}
    try:
        Y.uygula(kb)
        ok(False, "çapa yoksa YamaHatasi beklenir")
    except Y.YamaHatasi as e:
        ok("index.html" in str(e) and "hiçbir dosyaya dokunulmadı" in str(e), "çapa yok: anlaşılır hata, hangi dosya belli")
    ok(all((kb / f).read_bytes() == b for f, b in ilk.items()) and not (kb / "yst_ek.py").exists(), "çapa yok: server.py dahil HİÇBİR dosya değişmedi, eklenti kopyalanmadı")
    # --- çapa birden çok yerde
    kd = sahte_kurgu("d")
    (kd / "pyproject.toml").write_text('a = ["guidance_gen"]\nb = ["guidance_gen"]\n', encoding="utf-8")
    try:
        Y.uygula(kd)
        ok(False, "belirsiz çapa YamaHatasi beklenir")
    except Y.YamaHatasi as e:
        ok("birden çok" in str(e), "belirsiz çapa (iki kez geçiyor) reddedilir")
    # --- kuru çalıştırma yazmaz
    ke = sahte_kurgu("e")
    ilk = (ke / "server.py").read_bytes()
    Y.uygula(ke, kuru=True)
    ok((ke / "server.py").read_bytes() == ilk and not (ke / "yst_ek.py").exists(), "--kuru hiçbir şey yazmaz")
    # --- Kurgu olmayan klasör
    try:
        Y.uygula(tmp)
        ok(False, "Kurgu olmayan klasör reddedilmeli")
    except Y.YamaHatasi:
        ok(True, "Kurgu olmayan klasör reddedilir")

    # --- eklenti bozulsa da Kurgu açılır: import try/except içinde, rota yalnızca yüklüyse
    srv_k = (k / "server.py").read_text(encoding="utf-8")
    ok("try:  # YST-EK" in srv_k and "except Exception:  # YST-EK" in srv_k and "yst_ek = None" in srv_k, "server.py: eklenti importu try/except içinde (bozuk eklenti Kurgu'yu durdurmaz)")
    ok("elif yst_ek is not None and path.startswith" in srv_k, "server.py: /api/yst/ rotası yalnızca eklenti yüklüyse var")
    ok(all(Y.ISARET in satir for e in Y.EKLER if "degistir" not in e for satir in e["metin"].splitlines()), "yama: eklenen HER satır işaret taşır (geri alma yarım satır bırakamaz)")
    # --- geri alma: Kurgu'nun düz haline döner, bayt bayt aynı
    kg = sahte_kurgu("g")
    orj = {f: (kg / f).read_bytes() for f in ("server.py", "web/index.html", "pyproject.toml")}
    Y.uygula(kg)
    ga = Y.geri_al(kg)
    ok(len(ga["geri_alinan"]) == 5 and "yst_ek.py" in ga["silinen"], "geri_al: 5 ek geri alındı, eklenti dosyaları silindi")
    ok(all((kg / f).read_bytes() == b for f, b in orj.items()), "geri_al: server.py, index.html, pyproject.toml uygulamadan ÖNCEKİ haliyle bayt bayt aynı")
    ok(not (kg / "yst_ek.py").exists() and not (kg / "web" / "yst.css").exists() and not (kg / "web" / "js" / "yst.js").exists(), "geri_al: eklenti dosyaları kalmadı")
    ok(Y.geri_al(kg)["geri_alinan"] == [], "geri_al: ikinci çağrı zararsız (idempotent)")
    Y.uygula(kg)
    ok(Y.kontrol(kg)["tamam"], "geri_al sonrası yeniden uygulama çalışır")
    kgc = sahte_kurgu("gc", crlf=True)
    orj_c = (kgc / "server.py").read_bytes()
    Y.uygula(kgc)
    Y.geri_al(kgc)
    ok((kgc / "server.py").read_bytes() == orj_c, "geri_al: CRLF'li dosyada da bayt bayt aynı")
    # --- otomatik: asla istisna fırlatmaz
    Y.KAPALI = tmp / "kapali.isaret"
    ok(Y.otomatik(sahte_kurgu("o1"))["durum"] == "tamam", "otomatik: uygun Kurgu'da 'tamam'")
    kx = sahte_kurgu("o2")
    (kx / "web" / "index.html").write_text("<html>başlık yok</html>", encoding="utf-8")
    ro = Y.otomatik(kx)
    ok(ro["durum"] == "uygulanamadi" and "index.html" in ro["neden"], "otomatik: çapa yoksa 'uygulanamadi' + neden (istisna yok)")
    ok(Y.otomatik(tmp / "yok-boyle-klasor")["durum"] == "uygulanamadi", "otomatik: Kurgu klasörü yoksa da istisna fırlatmaz")
    Y.KAPALI.write_text("kapali", encoding="utf-8")
    kk = sahte_kurgu("o3")
    ok(Y.otomatik(kk)["durum"] == "kapali" and not (kk / "yst_ek.py").exists(), "otomatik: kapalı işaret varsa hiçbir şey uygulanmaz")
    Y.KAPALI.unlink()

    # --- eklenti: seslendirme (sahte motor)
    EK = yukle("yst_ek_t", R / "sistem" / "yama" / "kurgu_ek" / "yst_ek.py")

    class Sahte:
        desteklenen = {"hiz": True, "seed": True, "duygu": True, "ses": True, "klon": False}
        atif_gerekir = True
        atif = "Sahte motor CC-BY"
        sayac = 0

        def hazir_mi(self):
            return None

        def uret(self, isler, plan, workdir, sr):
            Sahte.sayac += 1
            yol = os.path.join(workdir, "vo.wav")
            with wave.open(yol, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(b"\x00\x00" * sr * 2)
            return {"vo": yol}

    class SahteModul:
        @staticmethod
        def motorlar():
            return {"sahte": Sahte()}

    EK._tts = lambda: SahteModul
    proje = tmp / "proje"
    proje.mkdir()
    s1 = EK.ses_uret(str(proje), "Merhaba dünya, bu bir deneme.", "sahte", 1.0, "female_1", "sakin")
    ok(s1["path"].startswith("media/tts/merhaba-dunya") and (proje / s1["path"]).is_file() and abs(s1["sure"] - 2.0) < 0.05, "ses: WAV media/tts altına yazıldı, süre ölçüldü")
    s2 = EK.ses_uret(str(proje), "Merhaba dünya, bu bir deneme.", "sahte", 1.0, "female_1", "sakin")
    ok(s2["path"] == s1["path"] and Sahte.sayac == 1, "ses: aynı metin + ayar önbellekten gelir (motor tekrar çalışmaz)")
    EK.ses_uret(str(proje), "Merhaba dünya, bu bir deneme.", "sahte", 1.0, "female_1", "sakin", tohum=5)
    ok(Sahte.sayac == 2, "ses: başka tohum başka alım")
    ok("Sahte motor CC-BY" in (proje / "media" / "tts" / "ATIF.txt").read_text(encoding="utf-8"), "ses: atıf gerektiren motorda ATIF.txt yazıldı")
    for kotu, ne in (("a", "kısa metin"), ("x" * 3001, "uzun metin")):
        try:
            EK.ses_uret(str(proje), kotu, "sahte")
            ok(False, f"ses: {ne} reddedilmeli")
        except EK.Hata:
            ok(True, f"ses: {ne} reddedilir")
    try:
        EK.ses_uret(str(proje), "yeterince uzun metin", "yok")
        ok(False, "ses: bilinmeyen motor reddedilmeli")
    except EK.Hata:
        ok(True, "ses: bilinmeyen motor reddedilir")
    try:
        EK.ses_uret(str(proje), "yeterince uzun metin", "sahte", klon=True)
        ok(False, "ses: klon desteklemeyen motor reddedilmeli")
    except EK.Hata as e:
        ok("klon" in str(e), "ses: klonu desteklemeyen motorda klon isteği anlaşılır hata verir")
    # --- eklenti: stüdyo dışında pasif
    ok(EK.STUDYO is False, "eklenti: stüdyo dışında pasif (STUDYO=False)")
    ok(EK.durum()["gorsel"]["kurulu"] is False, "eklenti: pasifken durum() güvenli döner")
    # --- eklenti: iş yöneticisi tek iş sınırı
    import time
    EK.ISLER.clear()
    a = EK._is_baslat("ses", lambda ilerle: time.sleep(0.4) or {"x": 1})
    try:
        EK._is_baslat("ses", lambda ilerle: {})
        ok(False, "iş: ikinci eşzamanlı iş reddedilmeli")
    except EK.Hata:
        ok(True, "iş: ikinci eşzamanlı iş reddedilir (tek iş sınırı)")
    time.sleep(0.8)
    ok(EK.ISLER[a["id"]]["durum"] == "bitti" and EK.ISLER[a["id"]]["sonuc"] == {"x": 1}, "iş: bitince sonuç saklanır")
    b = EK._is_baslat("ses", lambda ilerle: 1 / 0)
    time.sleep(0.4)
    ok(EK.ISLER[b["id"]]["durum"] == "hata" and "division" in EK.ISLER[b["id"]]["hata"], "iş: hata arayüze iletilir")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{S[0]} başarılı, {S[1]} başarısız")
sys.exit(1 if S[1] else 0)
