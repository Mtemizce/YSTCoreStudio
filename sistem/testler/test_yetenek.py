import base64, io, json, os, shutil, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "baglayici"))
import ortak, yetenek as Y

KUL = R / "sistem" / "ayar" / "kullanici.json"
KUL_YEDEK = KUL.read_bytes()
HARCAMA = R / "sistem" / "ortam" / "baglayici" / "harcama.jsonl"
HARCAMA_YEDEK = HARCAMA.read_bytes() if HARCAMA.exists() else None
tmp = Path(tempfile.mkdtemp(prefix="yetenek-"))
S = [0, 0]
ISTEKLER = []
SAYAC = {"calisan": 0}


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _j(self, kod, obj):
        b = json.dumps(obj).encode()
        self.send_response(kod); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        veri = self.rfile.read(n)
        try:
            govde = json.loads(veri)
        except ValueError:
            govde = None
        ISTEKLER.append(("POST", self.path, self.headers.get("Authorization"), govde))
        if self.path == "/v1/video":
            return self._j(200, {"id": "job-1"})
        if self.path == "/v1/yok-olan":
            return self._j(500, {"hata": "sunucu bozuk"})
        if self.path == "/v1/video-hatali":
            return self._j(200, {"id": "job-fail"})
        if self.path == "/v1/video-sonsuz":
            return self._j(200, {"id": "job-sonsuz"})
        if self.path == "/v1/video-http":
            return self._j(200, {"id": "job-http"})
        if "generateContent" in self.path:
            b = io.BytesIO()
            from PIL import Image
            Image.new("RGB", (64, 64), (30, 200, 30)).save(b, "PNG")
            return self._j(200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b.getvalue()).decode()}}]}}]})
        if self.path == "/v1/images/generations":
            b = io.BytesIO()
            from PIL import Image
            Image.new("RGB", (64, 64), (200, 30, 30)).save(b, "PNG")
            return self._j(200, {"data": [{"b64_json": base64.b64encode(b.getvalue()).decode()}]})
        self._j(404, {})

    def do_GET(self):
        ISTEKLER.append(("GET", self.path, self.headers.get("Authorization"), None))
        if self.path == "/v1/jobs/job-1":
            SAYAC["calisan"] += 1
            if SAYAC["calisan"] < 3:
                return self._j(200, {"status": "running"})
            return self._j(200, {"status": "completed", "output": {"url": f"http://127.0.0.1:{PORT}/dosyalar/cikti.mp4"}})
        if self.path == "/v1/jobs/job-fail":
            return self._j(200, {"status": "failed", "error": "içerik reddedildi"})
        if self.path == "/v1/jobs/job-sonsuz":
            return self._j(200, {"status": "running"})
        if self.path == "/v1/jobs/job-http":
            return self._j(200, {"status": "completed", "output": {"url": "http://example.com/x.mp4"}})
        if self.path == "/dosyalar/cikti.mp4":
            veri = b"\x00\x00\x00\x18ftypmp42" + b"VIDEO" * 500
            self.send_response(200); self.send_header("Content-Length", str(len(veri))); self.end_headers(); self.wfile.write(veri)
            return
        self._j(404, {})


srv = HTTPServer(("127.0.0.1", 0), Sahte)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["SAHTE_ANAHTAR"] = "ANAHTAR_DEGERI_12345"
os.environ["BASKA_ANAHTAR"] = "ANAHTAR_DEGERI_67890"


def uc(yol, sonuc_yol, extra=None):
    d = {"gonder": {"yol": yol, "govde": {"model": "{model}", "prompt": "{istem}", "image": "{gorsel_url?}", "duration": "{sure?}"}, "sonuc_id": "$.id"},
         "durum": {"yol": sonuc_yol, "durum_alani": "$.status", "biten": ["completed"], "hatali": ["failed"], "bekle": {"aralik": 1, "en_cok": 3}},
         "cikti": {"yol": "$.output.url", "tur": "url"}}
    if extra:
        d.update(extra)
    return d


def manifest(ad, yol, durum_yol, **kw):
    m = {"tur": "http-is", "ad": ad, "yetenekler": ["video-uret"], "taban_url": f"http://127.0.0.1:{PORT}", "anahtar_adi": "SAHTE_ANAHTAR",
         "kimlik": {"baslik": "Authorization", "sablon": "Key {anahtar}"}, "uc": {"video-uret": uc(yol, durum_yol)},
         "maliyet": {"video-uret": {"birim_alani": "sure", "fiyat": 0.1}}}
    m.update(kw)
    return m


def ayarla(saglayicilar, baglayicilar=None, sira=None, butce=None):
    d = {"ajanlar": {}, "saglayicilar": saglayicilar,
         "baglayicilar": {sid: {"etkin": True, "model": "m-1"} for sid in saglayicilar} if baglayicilar is None else baglayicilar}
    if sira:
        d["yetenekler"] = {"video-uret": {"sira": sira}}
    if butce:
        d["butce"] = butce
    KUL.write_text(json.dumps(d), encoding="utf-8")


try:
    # ---- şablon motoru ve yol çözücü
    ok(Y.doldur({"a": "{x}", "b": "{y?}", "c": "p-{x}-s", "d": ["{x}", "{y?}"]}, {"x": 5}) == {"a": 5, "c": "p-5-s", "d": [5]}, "doldur: tek yer tutucu tür korur, {y?} düşer, iç içe")
    try:
        Y.doldur({"a": "{eksik}"}, {}); ok(False, "eksik alan hata vermeli")
    except Y.GirdiHatasi:
        ok(True, "doldur: eksik zorunlu alan GirdiHatasi")
    ok(Y.yol_al({"a": {"b": [{"c": 7}]}}, "$.a.b[0].c") == 7 and Y.yol_al({"a": 1}, "$.x.y") is None, "yol_al ($.a.b[0].c, olmayan yol None)")

    # ---- doğrulama
    A = ortak.ayar_modul()
    for ad, m, beklenen in [
        ("kötü kimlik", manifest("x", "/a", "/b"), None),
        ("yerleşik ad", manifest("x", "/a", "/b"), "ema"),
        ("http adresi", manifest("x", "/a", "/b", taban_url="http://servis.example.com"), "x1"),
        ("küçük harf anahtar adı", manifest("x", "/a", "/b", anahtar_adi="kucuk"), "x2"),
        ("mutlak yol", manifest("x", "https://kotu.example/a", "/b"), "x3"),
        ("yetenek dışı uc", {**manifest("x", "/a", "/b"), "uc": {"gorsel-uret": uc("/a", "/b")}}, "x4"),
        ("başlıkta satır sonu", manifest("x", "/a", "/b", basliklar={"X-A": "a\nb"}), "x5"),
        ("bilinmeyen tür", manifest("x", "/a", "/b", tur="shell"), "x6"),
    ]:
        if beklenen is None:
            continue
        try:
            A.dogrula_manifest(beklenen, m); ok(False, f"reddedilmeli: {ad}")
        except ValueError as e:
            ok(True, f"reddedildi: {ad} ({str(e)[:50]})")
    try:
        A.dogrula_manifest("iyi-bir", manifest("x", "/a", "/b")); ok(True, "geçerli manifest kabul edildi")
    except ValueError as e:
        ok(False, f"geçerli manifest reddedildi: {e}")

    # ---- uçtan uca asenkron servis
    ayarla({"servis-a": manifest("Servis A", "/v1/video", "/v1/jobs/{id}")})
    kat = ortak.katalog()["saglayicilar"]["servis-a"]
    ok(kat["ozel"] and kat["tur"] == ["video-uret"] and kat["anahtar"] == "SAHTE_ANAHTAR", "kullanıcı tanımlı sağlayıcı kataloğa birleşti")
    b = ortak.baglayici_durumu("servis-a")
    ok(b["etkin"] and b["anahtar_var"] and not b["yerel"], "bağlayıcı durumu (etkin, anahtar var, bulut)")
    try:
        Y.cagir("video-uret", {"istem": "villa gezisi"}, tmp / "v1"); ok(False, "onaysız bulut çağrısı reddedilmeli")
    except ortak.IzinHatasi as e:
        ok("onay" in str(e), "proje yok + onay yok → reddedildi: " + str(e)[:60])
    ok(not ISTEKLER, "onaysız çağrıda servise İSTEK GİTMEDİ")
    t0 = time.time()
    r = Y.cagir("video-uret", {"istem": "villa gezisi", "sure": 5}, tmp / "v1", onay=True)
    ok(Path(r["dosya"]).is_file() and Path(r["dosya"]).suffix == ".mp4" and r["bayt"] > 2000, f"asenkron iş tamam ({time.time() - t0:.1f} sn): {Path(r['dosya']).name}, {r['bayt']} bayt")
    gonder = next(i for i in ISTEKLER if i[1] == "/v1/video")
    ok(gonder[2] == "Key ANAHTAR_DEGERI_12345", "kimlik başlığı şablonu doğru ('Key {anahtar}')")
    ok(gonder[3] == {"model": "m-1", "prompt": "villa gezisi", "duration": 5}, f"gövde şablonu: isteğe bağlı alan düştü, sayı türü korundu: {gonder[3]}")
    ok(sum(1 for i in ISTEKLER if i[1] == "/v1/jobs/job-1") == 3, "durum sorgusu: 2 kez 'running', 3. 'completed'")
    ok(abs(r["maliyet"] - 0.5) < 1e-9 and abs(Y.bugun_harcama() - 0.5) < 1e-9, f"maliyet tahmini 0,5 ve harcama defterine yazıldı ({Y.bugun_harcama()})")
    log = (R / "sistem" / "ortam" / "arsiv" / "bulut_gunlugu.md")
    ok(log.exists() and "servis-a" in log.read_text(encoding="utf-8") and "ANAHTAR_DEGERI" not in log.read_text(encoding="utf-8"), "bulut günlüğü yazıldı, anahtar yok")

    # ---- başarısız iş, zaman aşımı, güvensiz çıktı adresi
    ayarla({"hatali": manifest("Hatalı", "/v1/video-hatali", "/v1/jobs/{id}", uc={"video-uret": uc("/v1/video-hatali", "/v1/jobs/{id}")})})
    try:
        Y.cagir("video-uret", {"istem": "x"}, tmp / "v2", onay=True, yedek=False); ok(False, "başarısız iş hata vermeli")
    except ortak.AgHatasi as e:
        ok("içerik reddedildi" in str(e), "servisin hata nedeni aktarıldı: " + str(e)[:60])
    ayarla({"sonsuz": manifest("Sonsuz", "/v1/video-sonsuz", "/v1/jobs/{id}", uc={"video-uret": uc("/v1/video-sonsuz", "/v1/jobs/{id}")})})
    t0 = time.time()
    try:
        Y.cagir("video-uret", {"istem": "x"}, tmp / "v3", onay=True, yedek=False); ok(False, "zaman aşımı olmalı")
    except ortak.AgHatasi as e:
        ok("zaman aşımı" in str(e) and time.time() - t0 < 15, f"zaman aşımı ({time.time() - t0:.1f} sn)")
    ayarla({"httpc": manifest("HttpÇıktı", "/v1/video-http", "/v1/jobs/{id}", uc={"video-uret": uc("/v1/video-http", "/v1/jobs/{id}")})})
    try:
        Y.cagir("video-uret", {"istem": "x"}, tmp / "v4", onay=True, yedek=False); ok(False, "http çıktı adresi reddedilmeli")
    except ortak.AgHatasi as e:
        ok("https" in str(e), "https olmayan çıktı adresi indirilmedi: " + str(e)[:50])

    # ---- yedek zinciri
    ISTEKLER.clear(); SAYAC["calisan"] = 0
    ayarla({"bozuk": manifest("Bozuk", "/v1/yok-olan", "/v1/jobs/{id}", uc={"video-uret": uc("/v1/yok-olan", "/v1/jobs/{id}")}),
            "saglam": manifest("Sağlam", "/v1/video", "/v1/jobs/{id}", anahtar_adi="BASKA_ANAHTAR")}, sira=["bozuk", "saglam"])
    r = Y.cagir("video-uret", {"istem": "zincir", "sure": 1}, tmp / "v5", onay=True)
    ok(r["saglayici"] == "saglam" and r["denenen"][0] == {"saglayici": "bozuk", "durum": "hata", "neden": r["denenen"][0]["neden"]}, f"1. sağlayıcı bozuk, 2.'ye geçildi: {[d['durum'] for d in r['denenen']]}")
    try:
        Y.cagir("video-uret", {"istem": "z"}, tmp / "v6", onay=True, tercih="bozuk", yedek=False); ok(False, "yedek=False hata vermeli")
    except ortak.AgHatasi:
        ok(True, "yedek kapalıysa hata yukarı çıkar")
    # etkin olmayan / anahtarı olmayan atlanır
    ayarla({"kapali": manifest("Kapalı", "/v1/video", "/v1/jobs/{id}"), "anahtarsiz": manifest("Anahtarsız", "/v1/video", "/v1/jobs/{id}", anahtar_adi="OLMAYAN_ANAHTAR")},
           baglayicilar={"anahtarsiz": {"etkin": True}}, sira=["kapali", "anahtarsiz"])
    try:
        Y.cagir("video-uret", {"istem": "z"}, tmp / "v7", onay=True); ok(False, "hazır sağlayıcı yok")
    except ortak.IzinHatasi as e:
        ok("anahtar" in str(e).lower() or "KAPALI" in str(e), "kapalı/anahtarsız sağlayıcılar atlandı, anlaşılır hata: " + str(e)[:70])

    # ---- bütçe
    ayarla({"servis-a": manifest("Servis A", "/v1/video", "/v1/jobs/{id}")}, butce={"mod": "cap", "gun_tavan": 0.6, "onay_esigi": 0.3})
    harcama0 = Y.bugun_harcama()
    try:
        Y.cagir("video-uret", {"istem": "pahalı", "sure": 20}, tmp / "v8", onay=True); ok(False, "tavan aşılmalı")
    except Y.ButceHatasi as e:
        ok("tavan" in str(e), "günlük tavan aşılınca durdu: " + str(e)[:70])
    ok(Y.bugun_harcama() == harcama0, "reddedilen çağrı harcama yazmadı")
    ayarla({"servis-a": manifest("Servis A", "/v1/video", "/v1/jobs/{id}")}, butce={"mod": "cap", "gun_tavan": 100, "onay_esigi": 0.3})
    try:
        Y.butce_kapisi(0.4, False); ok(False, "eşik aşımı onay istemeli")
    except Y.ButceHatasi as e:
        ok("onay" in str(e), "onay eşiği aşılınca onay istedi")
    ok(Y.butce_kapisi(0.4, True) is None, "onayla geçti")
    ok("bilinmiyor" in (Y.butce_kapisi(None, True) or ""), "maliyet tanımsızsa uyarı verir (sessizce geçmez)")

    # ---- mock
    ayarla({"sahte": {"tur": "mock", "ad": "Sahte test", "yetenekler": ["gorsel-uret", "video-uret", "tts"]}})
    r = Y.cagir("gorsel-uret", {"istem": "oda"}, tmp / "m1")
    ok(Path(r["dosya"]).suffix == ".png" and r["maliyet"] is None, "mock görsel (onaysız, anahtarsız, ağsız)")
    r = Y.cagir("video-uret", {"istem": "oda"}, tmp / "m2")
    ok(Path(r["dosya"]).suffix == ".mp4" and Path(r["dosya"]).stat().st_size > 1000, "mock video (ffmpeg testsrc)")

    # ---- openai-uyumlu
    ayarla({"oa": {"tur": "openai-uyumlu", "ad": "OA uyumlu", "yetenekler": ["gorsel-uret"], "taban_url": f"http://127.0.0.1:{PORT}", "anahtar_adi": "SAHTE_ANAHTAR"}},
           baglayicilar={"oa": {"etkin": True, "model": "yerel-model-1"}})
    ISTEKLER.clear()
    r = Y.cagir("gorsel-uret", {"istem": "kırmızı"}, tmp / "o1", onay=True)
    ok(Path(r["dosya"]).is_file() and ISTEKLER[0][3]["model"] == "yerel-model-1" and ISTEKLER[0][2] == "Bearer ANAHTAR_DEGERI_12345", "openai-uyumlu: model sizin yazdığınız, Bearer anahtar")
    ayarla({"oa": {"tur": "openai-uyumlu", "ad": "OA", "yetenekler": ["gorsel-uret"], "taban_url": f"http://127.0.0.1:{PORT}", "anahtar_adi": "SAHTE_ANAHTAR"}},
           baglayicilar={"oa": {"etkin": True}})
    try:
        Y.cagir("gorsel-uret", {"istem": "k"}, tmp / "o2", onay=True, yedek=False); ok(False, "model yoksa çalışmamalı")
    except ortak.IzinHatasi as e:
        ok("model adı gerekli" in str(e), "VARSAYILAN MODEL YOK: model boşsa çalışmıyor")

    # ---- yerleşik kod bağdaştırıcısı da aynı yetenek arayüzünden
    os.environ["GEMINI_API_KEY"] = "GEMINI_TEST_ANAHTARI_1"
    ayarla({}, baglayicilar={"gemini": {"etkin": True, "taban_url": f"http://127.0.0.1:{PORT}", "model": "g-model-1"}})
    ISTEKLER.clear()
    r = Y.cagir("gorsel-uret", {"istem": "yeşil oda"}, tmp / "g1", tercih="gemini", onay=True)
    ok(Path(r["dosya"]).is_file() and "g-model-1:generateContent" in ISTEKLER[0][1], "yerleşik gemini bağdaştırıcısı yetenek arayüzünden çalıştı (model kullanıcıdan)")
    ayarla({}, baglayicilar={"gemini": {"etkin": True, "taban_url": f"http://127.0.0.1:{PORT}"}})
    try:
        Y.cagir("gorsel-uret", {"istem": "x"}, tmp / "g2", tercih="gemini", onay=True, yedek=False); ok(False, "modelsiz gemini çalışmamalı")
    except ortak.IzinHatasi as e:
        ok("model adı gerekli" in str(e), "yerleşik bağdaştırıcıda da varsayılan model yok")
    # ---- kod bağdaştırıcılarında da varsayılan model yok
    import importlib.util
    for ad in ("gemini", "openai_gorsel", "elevenlabs"):
        kaynak = (R / "sistem/baglayici/saglayici" / f"{ad}.py").read_text(encoding="utf-8")
        ok(not any(x in kaynak for x in ("gemini-2.5", "gpt-image-1", "eleven_multilingual_v2")), f"{ad}: kodda varsayılan model adı kalmadı")
    # ---- liste
    ayarla({"sahte": {"tur": "mock", "ad": "Sahte test", "yetenekler": ["gorsel-uret"]}})
    ok(any(s["id"] == "sahte" and s["hazir"] for s in Y.liste()["gorsel-uret"]["saglayicilar"]), "liste(): yetenek → hazır sağlayıcılar")
finally:
    KUL.write_bytes(KUL_YEDEK)
    if HARCAMA_YEDEK is None:
        HARCAMA.unlink(missing_ok=True)
    else:
        HARCAMA.write_bytes(HARCAMA_YEDEK)
    (R / "sistem" / "ortam" / "arsiv" / "bulut_gunlugu.md").unlink(missing_ok=True)
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
