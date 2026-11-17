import json, os, shutil, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem" / "baglayici"))
import ortak, kesif as K

KUL = R / "sistem" / "ayar" / "kullanici.json"
KUL_YEDEK = KUL.read_bytes()
MODDIR = R / "sistem" / "ortam" / "baglayici" / "modeller"
MOD_YEDEK = {p.name: p.read_bytes() for p in MODDIR.glob("*.json")} if MODDIR.exists() else {}
S = [0, 0]
ISTEK = []


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _j(self, kod, obj):
        b = json.dumps(obj).encode()
        self.send_response(kod); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query); h = self.headers
        ISTEK.append((u.path, dict(q), {k.lower(): v for k, v in h.items() if k.lower() in ("authorization", "x-api-key", "x-goog-api-key", "xi-api-key", "anthropic-version")}))
        yol = u.path
        if yol == "/openai/v1/models":  # OpenAI / genel
            if h.get("Authorization") != "Bearer OA_ANAHTAR_123456":
                return self._j(401, {"error": "kötü anahtar"})
            return self._j(200, {"object": "list", "data": [{"id": i, "object": "model"} for i in ("gpt-yeni-1", "gpt-image-yeni", "tts-yeni", "text-embedding-yeni", "whisper-yeni")]})
        if yol == "/anthropic/v1/models":  # yeni biçim: yalnızca Bearer kabul, x-api-key 401
            if h.get("Authorization") != "Bearer AN_ANAHTAR_123456":
                return self._j(401, {"error": "x-api-key kabul edilmiyor"})
            if "after_id" not in q:
                return self._j(200, {"data": [{"id": "claude-a", "display_name": "Claude A"}, {"id": "claude-b", "display_name": "Claude B"}], "has_more": True, "last_id": "claude-b"})
            return self._j(200, {"data": [{"id": "claude-c", "display_name": "Claude C"}], "has_more": False, "last_id": "claude-c"})
        if yol == "/gemini/v1beta/models":
            if h.get("x-goog-api-key") != "GM_ANAHTAR_123456":
                return self._j(403, {"error": "anahtar"})
            if "pageToken" not in q:
                return self._j(200, {"models": [{"name": "models/gemini-yeni", "displayName": "Gemini Yeni", "supportedGenerationMethods": ["generateContent"]},
                                                  {"name": "models/gemini-yeni-image", "displayName": "Gemini Görsel", "supportedGenerationMethods": ["generateContent"]}], "nextPageToken": "T2"})
            return self._j(200, {"models": [{"name": "models/gemini-embedding-yeni", "displayName": "Emb", "supportedGenerationMethods": ["embedContent"]}]})
        if yol == "/ollama/api/tags":
            return self._j(200, {"models": [{"name": "llama-yerel:8b"}, {"name": "nomic-yerel:latest"}, {"name": "gorsel-yerel:7b"}]})
        if yol == "/lms/api/v1/models":
            return self._j(404, {})
        if yol == "/lms/v1/models":
            return self._j(200, {"data": [{"id": "lm-model-1"}, {"id": "lm-embedding-model"}]})
        if yol == "/el/v1/models":
            if h.get("xi-api-key") != "EL_ANAHTAR_123456":
                return self._j(401, {})
            return self._j(200, [{"model_id": "el-tts-a", "name": "TTS A", "can_do_text_to_speech": True}, {"model_id": "el-diger", "name": "Diğer", "can_do_text_to_speech": False}])
        if yol == "/el/v1/voices":
            return self._j(200, {"voices": [{"voice_id": "v1", "name": "Ses Bir"}, {"voice_id": "v2", "name": "Ses İki"}]})
        if yol == "/bos/models":
            return self._j(200, {"data": []})
        self._j(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        govde = json.loads(self.rfile.read(n) or b"{}")
        ISTEK.append((self.path, govde, {}))
        if self.path == "/ollama/api/show":
            caps = {"llama-yerel:8b": ["completion"], "nomic-yerel:latest": ["embedding"], "gorsel-yerel:7b": ["completion", "vision"]}[govde["model"]]
            return self._j(200, {"capabilities": caps})
        self._j(404, {})


srv = HTTPServer(("127.0.0.1", 0), Sahte)
P = srv.server_address[1]
B = f"http://127.0.0.1:{P}"
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["GEMINI_API_KEY"] = "GM_ANAHTAR_123456"; os.environ["ELEVENLABS_API_KEY"] = "EL_ANAHTAR_123456"
for k, v in {"OA_KEY": "OA_ANAHTAR_123456", "AN_KEY": "AN_ANAHTAR_123456", "GM_KEY": "GM_ANAHTAR_123456", "EL_KEY": "EL_ANAHTAR_123456", "KOTU_KEY": "YANLIS_ANAHTAR_000"}.items():
    os.environ[k] = v


def ayarla(sag, bag):
    KUL.write_text(json.dumps({"ajanlar": {}, "saglayicilar": sag, "baglayicilar": bag}), encoding="utf-8")


try:
    onay = K.onayarlar()
    ok({"openai", "anthropic", "gemini", "openrouter", "ollama", "lmstudio", "genel-openai", "elevenlabs"} <= set(onay), "ön ayarlar: " + ", ".join(onay))
    ok(all("dogrulama" in v and v["kesif"]["yol"] for v in onay.values()), "her ön ayarda kesif yolu ve doğrulama notu var")
    ok(onay["openai"]["taban_url"] == "https://api.openai.com/v1" and onay["ollama"]["taban_url"] == "http://localhost:11434", "adresler resmî belgedekiler")

    ayarla({
        "oa": {"tur": "openai-uyumlu", "ad": "OpenAI (test)", "yetenekler": ["gorsel-uret", "gorsel-duzenle", "tts"], "on_ayar": "openai", "taban_url": B + "/openai/v1", "anahtar_adi": "OA_KEY"},
        "an": {"tur": "baglanti", "ad": "Anthropic (test)", "yetenekler": [], "on_ayar": "anthropic", "taban_url": B + "/anthropic", "anahtar_adi": "AN_KEY"},
        "ol": {"tur": "baglanti", "ad": "Ollama (test)", "yetenekler": [], "on_ayar": "ollama", "taban_url": B + "/ollama", "anahtar_adi": None},
        "lm": {"tur": "baglanti", "ad": "LM Studio (test)", "yetenekler": [], "on_ayar": "lmstudio", "taban_url": B + "/lms", "anahtar_adi": "LM_KEY_YOK"},
        "kotu": {"tur": "openai-uyumlu", "ad": "Yanlış anahtar", "yetenekler": ["gorsel-uret"], "on_ayar": "openai", "taban_url": B + "/openai/v1", "anahtar_adi": "KOTU_KEY"},
        "anahtarsiz": {"tur": "openai-uyumlu", "ad": "Anahtarsız", "yetenekler": ["gorsel-uret"], "on_ayar": "openai", "taban_url": B + "/openai/v1", "anahtar_adi": "OLMAYAN_KEY"},
        "bos": {"tur": "openai-uyumlu", "ad": "Boş liste", "yetenekler": ["gorsel-uret"], "on_ayar": "genel-openai", "taban_url": B + "/bos", "anahtar_adi": "OA_KEY"},
    }, {"gemini": {"etkin": True, "taban_url": B + "/gemini"}, "elevenlabs": {"etkin": True, "taban_url": B + "/el"}})

    r = K.kesfet("oa")
    ids = {m["id"]: m for m in r["modeller"]}
    ok(len(ids) == 5 and ids["gpt-image-yeni"]["yetenekler"] == ["gorsel-uret", "gorsel-duzenle"] and ids["tts-yeni"]["yetenekler"] == ["tts"] and ids["text-embedding-yeni"]["yetenekler"] == ["embedding"]
       and ids["whisper-yeni"]["yetenekler"] == ["stt"] and ids["gpt-yeni-1"]["yetenekler"] == ["llm"], "OpenAI: 5 model listelendi, türler adından sınıflandı")
    ok(all(m["tahmin"] for m in r["modeller"]), "OpenAI'de sınıf 'tahmin' işaretli (serviste yetenek alanı yok)")
    ok(any(i[0] == "/openai/v1/models" and i[2].get("authorization") == "Bearer OA_ANAHTAR_123456" for i in ISTEK), "Bearer başlığıyla GET {taban}/models")
    ISTEK.clear()
    r = K.kesfet("an")
    ok([m["id"] for m in r["modeller"]] == ["claude-a", "claude-b", "claude-c"] and all(m["yetenekler"] == ["llm"] for m in r["modeller"]), "Anthropic: sayfalama (after_id) ile 3 model, hepsi llm")
    ok(r["kimlik"] == "Authorization,anthropic-version", "x-api-key 401 verince Bearer alternatifi denendi ve çalıştı")
    ok(any(i[2].get("anthropic-version") for i in ISTEK), "anthropic-version başlığı gönderildi")
    r = K.kesfet("gemini")
    g = {m["id"]: m["yetenekler"] for m in r["modeller"]}
    ok(g == {"gemini-yeni": ["llm"], "gemini-yeni-image": ["gorsel-uret", "gorsel-duzenle"], "gemini-embedding-yeni": ["embedding"]}, f"Gemini: nextPageToken ile 2 sayfa, 'models/' öneki atıldı, yöntemlerden sınıflandı: {g}")
    ok(all(not m["tahmin"] for m in r["modeller"]), "Gemini sınıfı servisin kendi alanından (tahmin değil)")
    r = K.kesfet("ol")
    o = {m["id"]: m["yetenekler"] for m in r["modeller"]}
    ok(o == {"llama-yerel:8b": ["llm"], "nomic-yerel:latest": ["embedding"], "gorsel-yerel:7b": ["llm", "gorsel-girdi"]}, f"Ollama: /api/tags + /api/show capabilities: {o}")
    r = K.kesfet("lm")
    ok([m["id"] for m in r["modeller"]] == ["lm-model-1", "lm-embedding-model"] and r["modeller"][1]["yetenekler"] == ["embedding"], "LM Studio: yeni uç nokta 404 → /v1/models'a düştü, embedding adından ayrıldı")
    r = K.kesfet("elevenlabs")
    ok([m["id"] for m in r["modeller"] if m["yetenekler"]] == ["el-tts-a"] and [v["id"] for v in r["sesler"]] == ["v1", "v2"], "ElevenLabs: can_do_text_to_speech + ses listesi")
    for sid, beklenen in (("kotu", "401"), ("anahtarsiz", "anahtarını gir"), ("bos", "model listesi döndürmedi")):
        try:
            K.kesfet(sid); ok(False, f"{sid} hata vermeli")
        except (ortak.IzinHatasi, ortak.AgHatasi) as e:
            ok(beklenen in str(e), f"{sid}: anlaşılır hata ({str(e)[:60]})")
    ok("YANLIS_ANAHTAR" not in str(K.onbellek("oa")), "anahtar önbelleğe yazılmadı")

    # ---- seçim doğrulama: elle yazılan/uydurma model reddedilir
    ok(K.model_gecerli("oa", "gorsel-duzenle", "gpt-image-yeni") == (True, ""), "listedeki model kabul")
    ok(not K.model_gecerli("oa", "gorsel-duzenle", "gpt 555")[0] and "listesinde yok" in K.model_gecerli("oa", None, "gpt 555")[1], "'gpt 555' gibi uydurma ad REDDEDİLDİ")
    ok(not K.model_gecerli("oa", None, "gpt-6.1")[0], "'gpt-6.1' (listede olmayan) reddedildi")
    ok(not K.model_gecerli("gemini", "tts", "gemini-yeni")[0], "Gemini'de servisin 'llm' dediği model 'tts' için reddedildi (kesin sınıf)")
    ok(K.model_gecerli("oa", "gorsel-duzenle", "tts-yeni")[0], "tahmin sınıflı modelde sıkı eşleşme zorunlu değil (yanlış tahmin kullanıcıyı kilitlemez)")
    ok(not K.model_gecerli("kotu", None, "x")[0] and "Bağlan" in K.model_gecerli("kotu", None, "x")[1], "liste hiç alınmadıysa 'önce bağlan' denir")
    # model_sec: yeteneğe göre seçilmiş model
    ayarla({"oa": {"tur": "openai-uyumlu", "ad": "OA", "yetenekler": ["gorsel-uret", "tts"], "on_ayar": "openai", "taban_url": B + "/openai/v1", "anahtar_adi": "OA_KEY"}},
           {"oa": {"etkin": True, "modeller": {"gorsel-uret": "gpt-image-yeni", "tts": "tts-yeni"}}})
    ctx = ortak.izin_kontrol_genel("oa", "tts", None, True)
    ctx2 = ortak.izin_kontrol_genel("oa", "gorsel-uret", None, True)
    ok(ctx["model"] == "tts-yeni" and ctx2["model"] == "gpt-image-yeni", "yetenek başına ayrı model seçimi çalışıyor (tts → tts-yeni, görsel → gpt-image-yeni)")
    # yerel ağ adresi
    ok(ortak.yerel_ag_mi("192.168.1.50") and ortak.yerel_ag_mi("localhost") and not ortak.yerel_ag_mi("8.8.8.8") and not ortak.yerel_ag_mi("example.com"), "http yalnızca yerel/özel ağ adresine serbest")
    A = ortak.ayar_modul()
    A.dogrula_manifest("ol-lan", {"tur": "baglanti", "ad": "LAN Ollama", "yetenekler": [], "on_ayar": "ollama", "taban_url": "http://192.168.1.50:11434", "anahtar_adi": None})
    ok(True, "ağdaki Ollama (http://192.168.1.50:11434) manifesti kabul edildi")
    try:
        A.dogrula_manifest("acik", {"tur": "baglanti", "ad": "X", "yetenekler": [], "taban_url": "http://example.com", "anahtar_adi": None}); ok(False, "açık internete http reddedilmeli")
    except ValueError:
        ok(True, "açık internet adresine http reddedildi")
finally:
    KUL.write_bytes(KUL_YEDEK)
    if MODDIR.exists():
        for p in MODDIR.glob("*.json"):
            if p.name not in MOD_YEDEK:
                p.unlink()
        for ad, b in MOD_YEDEK.items():
            (MODDIR / ad).write_bytes(b)
    srv.shutdown()
print("SONUÇ: %d tamam, %d hata" % tuple(S))
