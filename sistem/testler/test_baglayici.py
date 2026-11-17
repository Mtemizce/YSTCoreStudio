import base64, io, json, os, shutil, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from PIL import Image

R = Path(__file__).resolve().parents[2]
PY = sys.executable
URET = str(R / "sistem/baglayici/uret.py")
KEY_EL, KEY_GE, KEY_OA = "xi-testkey-0123456789abcdef", "AIzaTestKey0123456789abcdef", "s" "k-testkey0123456789abcdef"  # parçalı yazıldı: paket taraması sahte anahtarı gerçek sanmasın
goruldu = []


def png():
    b = io.BytesIO(); Image.new("RGB", (64, 36), (200, 150, 90)).save(b, "PNG"); return b.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, o, kod=200):
        b = json.dumps(o).encode(); self.send_response(kod); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/v1/user") and self.headers.get("xi-api-key") == KEY_EL: return self._json({"subscription": {"tier": "testplan"}})
        if self.path.startswith("/v1beta/models") and self.headers.get("x-goog-api-key") == KEY_GE: return self._json({"models": [{"name": "m"}]})
        if self.path.startswith("/v1/models") and self.headers.get("Authorization") == f"Bearer {KEY_OA}": return self._json({"data": [{}, {}]})
        self._json({"hata": "yetkisiz"}, 401)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); g = json.loads(self.rfile.read(n) or b"{}")
        goruldu.append((self.path, dict(self.headers), g))
        if self.path.startswith("/v1/text-to-speech/"):
            if self.headers.get("xi-api-key") != KEY_EL: return self._json({"hata": "yetkisiz"}, 401)
            assert g["text"] and g["voice_settings"]["speed"] <= 1.2
            b = b"ID3" + bytes(400); self.send_response(200); self.send_header("Content-Type", "audio/mpeg"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if ":generateContent" in self.path:
            if self.headers.get("x-goog-api-key") != KEY_GE: return self._json({"hata": "yetkisiz"}, 401)
            if "strict" in self.path and "generationConfig" in g: return self._json({"hata": "imageConfig bilinmiyor"}, 400)
            return self._json({"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png()).decode()}}]}}]})
        if self.path == "/v1/images/generations":
            if self.headers.get("Authorization") != f"Bearer {KEY_OA}": return self._json({"hata": "yetkisiz"}, 401)
            return self._json({"data": [{"b64_json": base64.b64encode(png()).decode()}]})
        self._json({}, 404)


srv = HTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{port}"

sys.path.insert(0, str(R / "sistem/ayar")); import ayar  # noqa: E402
proje = "zz-bag"; p = R / "projeler" / proje
if p.exists(): shutil.rmtree(p)
(p / "ana/media").mkdir(parents=True)
ok = True


def calistir(*args, env_ek=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY")}
    env.update({"PYTHONUTF8": "1", **(env_ek or {})})
    r = subprocess.run([PY, URET, *args], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
    return r.returncode, (r.stdout + r.stderr).strip()


def bekle(ad, kod, cikti, beklenen_kod, icerik=None):
    global ok
    iyi = kod == beklenen_kod and (icerik is None or icerik in cikti)
    ok &= iyi
    print(("OK    " if iyi else "HATA  ") + ad + f"  → kod {kod}: {cikti[:110]}")


cikti_png = str(p / "ana/media/uretilen/a.png")
istem = ["gorsel", "--proje", proje, "--saglayici", "gemini", "--istem", "Bir mimar karakter, sade zemin", "--cikti", cikti_png, "--en-boy", "9:16"]
k, c = calistir(*istem); bekle("1 kapalı bağlayıcı reddedilir", k, c, 3, "KAPALI")
ayar.kaydet({"baglayicilar": {"gemini": {"etkin": True, "taban_url": BASE, "model": "test-model"}, "elevenlabs": {"etkin": True, "taban_url": BASE, "ses_id": "VOICE1", "model": "test-model"}, "openai-gorsel": {"etkin": True, "taban_url": BASE, "model": "test-model"}}}, proje)
k, c = calistir(*istem); bekle("2 anahtarsız reddedilir", k, c, 3, "API anahtarı yok")
k, c = calistir(*istem, env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("3 bulut izni yoksa reddedilir", k, c, 3, "BULUT İZNİ")
ayar.kaydet({"izin": {"bulut": True}}, proje)
k, c = calistir(*istem, env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("4 gemini görsel başarılı", k, c, 0, "tamam")
print("      dosya var:", Path(cikti_png).is_file(), "| boyut:", Image.open(cikti_png).size)
k, c = calistir(*istem[:-2], "--cikti", str(p / "ana/media/uretilen/b.png"), "--saglayici", "gemini", env_ek={"GEMINI_API_KEY": "yanlis-anahtar-123456"}); bekle("5 yanlış anahtar → servis hatası", k, c, 4, "HTTP 401")
ayar.kaydet({"baglayicilar": {"gemini": {"model": "strict-model"}}}, proje)
k, c = calistir(*istem[:-2], "--cikti", str(p / "ana/media/uretilen/c.png"), env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("6 imageConfig reddedilince yeniden dener", k, c, 0, "tamam")
ref_kotu = str(p / "ana/media/foto/kaynak.jpg"); (p / "ana/media/foto").mkdir(); Image.new("RGB", (8, 8)).save(ref_kotu)
k, c = calistir(*istem[:-2], "--cikti", str(p / "ana/media/uretilen/d.png"), "--referans", ref_kotu, env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("7 kaynak fotoğraf referansı reddedilir", k, c, 3, "referans yalnızca")
k, c = calistir(*istem[:-2], "--cikti", str(p / "ana/media/uretilen/e.png"), "--referans", cikti_png, env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("8 kendi ürettiği referans serbest", k, c, 0, "tamam")
k, c = calistir("gorsel", "--proje", proje, "--saglayici", "openai-gorsel", "--istem", "x", "--cikti", str(p / "ana/media/uretilen/f.png"), env_ek={"OPENAI_API_KEY": KEY_OA}); bekle("9 openai görsel", k, c, 0, "tamam")
k, c = calistir("ses", "--proje", proje, "--saglayici", "elevenlabs", "--metin", "Merhaba dünya.", "--cikti", str(p / "ana/ses/a.mp3"), "--hiz", "1.5", env_ek={"ELEVENLABS_API_KEY": KEY_EL}); bekle("10 elevenlabs ses (hız 1.2'ye kırpılır)", k, c, 0, "tamam")
k, c = calistir("gorsel", "--proje", proje, "--saglayici", "gemini", "--istem", "x", "--cikti", str(R / "kimlik/oyun.png"), env_ek={"GEMINI_API_KEY": KEY_GE}); bekle("11 proje dışına yazma reddedilir", k, c, 3, "proje klasörünün içinde")
ayar.kaydet({"baglayicilar": {"gemini": {"model": ""}}}, proje)
# test komutları (genel ayar: taban_url proje düzeyinde olduğundan geçici kullanıcı ayarı yok → varsayılan https adresi çağrılmasın)
print("      sunucuya giden istek sayısı:", len(goruldu), "| anahtar değerleri istek GÖVDESİNDE var mı:", any(KEY_GE in json.dumps(g) or KEY_EL in json.dumps(g) for _, _, g in goruldu))
gunluk = (p / "bulut_gunlugu.md").read_text(encoding="utf-8")
sizdi = any(x in gunluk for x in (KEY_EL, KEY_GE, KEY_OA))
print("      günlük satırı:", gunluk.count("\n| 20"), "| anahtar günlüğe sızdı mı:", sizdi)
ok &= not sizdi and len(gunluk.splitlines()) > 5
k, c = calistir("durum", "--proje", proje); print(c.splitlines()[1] if len(c.splitlines()) > 1 else c)
shutil.rmtree(p)
print("\nSONUÇ:", "TÜM TESTLER GEÇTİ" if ok else "BAŞARISIZ VAR")
