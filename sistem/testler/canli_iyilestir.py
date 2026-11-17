import base64, io, json, os, random, shutil, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "arsiv"))
import arsiv as A
import analiz as Z
import iyilestir as I
import ortak

tmp = Path(tempfile.mkdtemp(prefix="iyi-test-"))
A.DIR = tmp / "db"; A.DB = A.DIR / "arsiv.db"; A.AYAR = A.DIR / "ayar.json"; A.ILERLEME = A.DIR / "ilerleme.json"
ark = tmp / "arsiv"
random.seed(3)
S = [0, 0]
KULLANICI = R / "sistem" / "ayar" / "kullanici.json"
kul_yedek = KULLANICI.read_bytes()


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def sahne(w, h, n=150):
    im = Image.new("RGB", (w, h), (170, 190, 210)); d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = random.randint(0, w), random.randint(0, h)
        d.rectangle([x, y, x + random.randint(15, 260), y + random.randint(15, 180)], fill=tuple(random.randint(30, 230) for _ in range(3)), outline=(0, 0, 0), width=2)
    return im


def kaydet(im, rel, **kw):
    p = ark / rel; p.parent.mkdir(parents=True, exist_ok=True); im.save(p, **kw); return p


# kötü fotoğraflar: küçük çözünürlük (700x500, JPEG), bulanık (1600x1100)
buyuk = sahne(1600, 1100)
kaydet(sahne(1600, 1100).resize((700, 500), Image.LANCZOS), "Proje/2022/kucuk.jpg", quality=70)  # farklı sahne (yinelenen sayılmasın)
kaydet(buyuk.filter(ImageFilter.GaussianBlur(3.5)), "Proje/2022/bulanik.jpg", quality=90)
kaydet(sahne(300, 200, 10), "Proje/2022/minik.jpg")             # <400 px: kurtarılamaz
for i in range(6):
    kaydet(sahne(2200, 1500), f"Proje/2022/iyi{i}.jpg", quality=92)
A.ayarla(str(ark))
A.tara(yazdir=lambda *_: None)
Z.oto()
c = A.baglan()

# ---- 1) modeller listesi
m = I.modeller()
ids = {x["id"]: x for x in m["modeller"]}
ok(set(ids) == {"yerel-realesrgan", "yerel-klasik"}, "varsayılanda yalnızca YEREL modeller var, bulut modeli kendiliğinden gelmez: " + ", ".join(ids))
ok(ids["yerel-klasik"]["kullanilabilir"] and ids["yerel-realesrgan"]["kullanilabilir"], f"yerel modeller hazır ({ids['yerel-realesrgan']['neden']})")
ok(ids["yerel-realesrgan"]["ucretli"] is False, "yerel model ücretsiz işaretli")

# ---- 2) adaylar
ad = I.adaylar()
adlar = [a["ad"] for a in ad]
print("   adaylar:", [(a["ad"], a["puan"], a["neden"]) for a in ad])
ok("kucuk.jpg" in adlar and "bulanik.jpg" in adlar, "düşük puanlılar aday")
ok("minik.jpg" not in adlar, "çok küçük (<400 px) aday değil")
ok(not any(a.startswith("iyi") for a in adlar), "iyi fotoğraflar aday değil")
ida = {a["ad"]: a["id"] for a in ad}

# ---- 3) klasik motor
r = I.iyilestir([ida["kucuk.jpg"], ida["bulanik.jpg"]], "yerel-klasik", 2.0, 0.6)
ok(r["tamam"] == 2 and r["hata"] == 0, f"klasik iyileştirme: {r['tamam']} tamam")
s0 = r["sonuclar"][0]
print("   sonuç:", {k: s0.get(k) for k in ("genislik", "yukseklik", "onceki_keskin", "sonraki_keskin", "onceki_puan", "sonraki_puan", "sn")})
ok(s0["genislik"] == 1400, f"700 px → 1400 px (olcek 2): {s0['genislik']}")
ok(ROOT_OK := (R / s0["cikti_yol"]).is_file(), "çıktı stüdyo klasörü altında (göreli yol kayıtlı): " + s0["cikti_yol"])
ok(not Path(s0["cikti_yol"]).is_absolute() and "Users" not in s0["cikti_yol"], "veritabanına göreli yol yazıldı")
ok((ark / "Proje/2022/kucuk.jpg").stat().st_size > 0 and Image.open(ark / "Proje/2022/kucuk.jpg").size == (700, 500), "ORİJİNAL arşiv dosyası değişmedi")

# ---- 4) Real-ESRGAN (gerçek model)
t = time.time()
r = I.iyilestir([ida["bulanik.jpg"]], "yerel-realesrgan", 2.0, 0.4)
print(f"   real-esrgan {time.time() - t:.1f} sn:", {k: r["sonuclar"][0].get(k) for k in ("genislik", "yukseklik", "onceki_keskin", "sonraki_keskin", "sn", "hata")})
ok(r["tamam"] == 1, f"Real-ESRGAN çalıştı (hata: {r['sonuclar'][0].get('hata')})")
if r["tamam"]:
    ok(r["sonuclar"][0]["sonraki_keskin"] > r["sonuclar"][0]["onceki_keskin"], "ölçülen keskinlik arttı")
par = json.loads(c.execute("SELECT parametre FROM iyilestirme WHERE model='yerel-realesrgan' ORDER BY id DESC LIMIT 1").fetchone()[0])
print("   parametre:", par)

# ---- 5) proje seçiminde iyileştirilmiş sürüm kullanılır
hedef = tmp / "proje_kaynak"
k = A.kopyala([ida["kucuk.jpg"]], str(hedef))
ok(k["iyilestirilmis"] == 1 and (hedef / "foto" / "kucuk_iyi.jpg").is_file(), "projeye iyileştirilmiş sürüm kopyalandı (kucuk_iyi.jpg)")
k2 = A.kopyala([ida["kucuk.jpg"]], str(tmp / "orj"), iyilestirilmisi_kullan=False)
ok((tmp / "orj" / "foto" / "kucuk.jpg").is_file(), "isteyince orijinal kopyalanır")
iy = I.liste([ida["kucuk.jpg"]])[0]
I.kullan(iy["id"], False)
k3 = A.kopyala([ida["kucuk.jpg"]], str(tmp / "orj2"))
ok(k3["iyilestirilmis"] == 0, "'kullan' kapatılınca orijinal gider")
u = Z.uygun(yil="2022", en_az_puan=6.0, limit=100)
print("   uygun:", [(x["ad"], x["puan"], x.get("iyilestirilmis_puan")) for x in u if x["ad"] in ("kucuk.jpg", "bulanik.jpg")])

# ---- 6) bulut: sahte sunucu
sunucu_istekleri = []


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        veri = self.rfile.read(n)
        sunucu_istekleri.append((self.path, self.headers.get("x-goog-api-key") or self.headers.get("Authorization"), len(veri), self.headers.get("Content-Type", "")[:30]))
        b = io.BytesIO(); sahne(900, 700).save(b, "PNG")
        if "generateContent" in self.path:
            cevap = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(b.getvalue()).decode()}}]}}]}
        else:
            cevap = {"data": [{"b64_json": base64.b64encode(b.getvalue()).decode()}]}
        j = json.dumps(cevap).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(j))); self.end_headers(); self.wfile.write(j)


srv = HTTPServer(("127.0.0.1", 0), Sahte)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["GEMINI_API_KEY"] = "test_gemini_anahtar_123456"
os.environ["OPENAI_API_KEY"] = "test_openai_anahtar_123456"
try:
    KULLANICI.write_text(json.dumps({"ajanlar": {}, "baglayicilar": {"gemini": {"etkin": True, "taban_url": f"http://127.0.0.1:{port}"}, "openai-gorsel": {"etkin": True, "taban_url": f"http://127.0.0.1:{port}"}},
                                      "isler": {"gorsel-iyilestirme": {"modeller": {"gemini-iyilestir": {"ad": "Gemini (kullanıcı tanımlı)", "motor": "bulut", "saglayici": "gemini", "model": "gem-model-1", "etkin": True}, "openai-iyilestir": {"ad": "OpenAI (kullanıcı tanımlı)", "motor": "bulut", "saglayici": "openai-gorsel", "model": "oa-model-1", "etkin": True},
                                                                                    "benim-gemini": {"ad": "Benim Gemini modelim", "motor": "bulut", "saglayici": "gemini", "model": "ozel-model-x", "etkin": True}}}}}), encoding="utf-8")
    m = {x["id"]: x for x in I.modeller()["modeller"]}
    ok(m["gemini-iyilestir"]["kullanilabilir"] and m["openai-iyilestir"]["kullanilabilir"], "bağlayıcı etkin + anahtar varken bulut modelleri hazır")
    ok("benim-gemini" in m and m["benim-gemini"]["model"] == "ozel-model-x", "kullanıcının eklediği model listede")
    r = I.iyilestir([ida["kucuk.jpg"]], "gemini-iyilestir", 2.0, 0.5, bulut_onay=False)
    ok(r["hata"] == 1 and "onay" in r["sonuclar"][0]["hata"], "onay yokken buluta GÖNDERİLMEDİ: " + r["sonuclar"][0]["hata"][:70])
    ok(len(sunucu_istekleri) == 0, "sunucuya istek gitmedi")
    r = I.iyilestir([ida["kucuk.jpg"]], "gemini-iyilestir", 2.0, 0.5, bulut_onay=True)
    ok(r["tamam"] == 1, f"gemini (sahte sunucu): {r['sonuclar'][0].get('hata')}")
    ok(sunucu_istekleri and "generateContent" in sunucu_istekleri[-1][0] and sunucu_istekleri[-1][1] == "test_gemini_anahtar_123456", f"istek biçimi: {sunucu_istekleri[-1][:2]}")
    r = I.iyilestir([ida["kucuk.jpg"]], "openai-iyilestir", 2.0, 0.5, bulut_onay=True)
    ok(r["tamam"] == 1, f"openai (sahte sunucu, multipart): {r['sonuclar'][0].get('hata')}")
    ok("images/edits" in sunucu_istekleri[-1][0] and "multipart" in sunucu_istekleri[-1][3], f"openai edits multipart: {sunucu_istekleri[-1]}")
    r = I.iyilestir([ida["kucuk.jpg"]], "benim-gemini", 2.0, 0.5, bulut_onay=True)
    ok(r["tamam"] == 1 and "ozel-model-x" in sunucu_istekleri[-1][0], "kullanıcının model adı isteğe girdi: " + sunucu_istekleri[-1][0])
    log = (R / "sistem" / "ortam" / "arsiv" / "bulut_gunlugu.md").read_text(encoding="utf-8")
    ok("gemini" in log and "test_gemini_anahtar" not in log, "bulut günlüğü yazıldı, anahtar günlükte yok")
    # kapalı bağlayıcı
    KULLANICI.write_text(json.dumps({"ajanlar": {}, "baglayicilar": {"gemini": {"etkin": False}}}), encoding="utf-8")
    try:
        I.iyilestir([ida["kucuk.jpg"]], "gemini-iyilestir", 2.0, 0.5, bulut_onay=True)
        ok(False, "model Ayarlar'da listeye açık değilken çalışmamalı")
    except (ValueError, ortak.IzinHatasi) as e:
        ok(True, "listede kapalı / bağlayıcı kapalıyken çalıştırma reddedildi: " + str(e)[:60])
finally:
    KULLANICI.write_bytes(kul_yedek)
    srv.shutdown()

# ---- 7) hata dayanıklılığı: arşiv dosyası silindi
(ark / "Proje/2022/bulanik.jpg").unlink()
r = I.iyilestir([ida["bulanik.jpg"], ida["kucuk.jpg"]], "yerel-klasik")
ok(r["hata"] == 1 and r["tamam"] == 1, "tek dosya hatası işi durdurmadı")

# temizlik
for d in (R / "sistem" / "ortam" / "arsiv" / "iyilestirilmis",):
    shutil.rmtree(d, ignore_errors=True)
(R / "sistem" / "ortam" / "arsiv" / "bulut_gunlugu.md").unlink(missing_ok=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
shutil.rmtree(tmp, ignore_errors=True)
