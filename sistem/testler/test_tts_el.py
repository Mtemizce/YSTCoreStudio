"""ElevenLabs seslendirme hattı (sahte yerel sunucuyla): model ayardan gelir, hız kırpılır, aday sayısı ücretli motorda 1'e iner, bulut günlüğü yazılır."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = Path(tempfile.mkdtemp(prefix="yst-test-"))
S_ = [0, 0]


def ok(c, m):
    S_[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


mp3 = S / "sahte.mp3"
subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=1.2", str(mp3)], check=True)
veri = mp3.read_bytes()
cagri = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        cagri.append((self.path, json.loads(self.rfile.read(n))))
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)


srv = HTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
sys.path.insert(0, str(R / "sistem/ayar"))
import ayar  # noqa: E402

proje = "zz-tts"
p = R / "projeler" / proje
if p.exists():
    shutil.rmtree(p)
(p / "ses").mkdir(parents=True)
try:
    ayar.kaydet({"baglayicilar": {"elevenlabs": {"etkin": True, "taban_url": f"http://127.0.0.1:{port}", "ses_id": "VOICE-X", "model": "test-model"}}, "izin": {"bulut": True}}, proje)
    plan = {"motor": "elevenlabs", "proje": proje, "satirlar": [{"id": "t", "kuyruk": 0.2, "parcalar": [
        {"metin": "Önce şantiye, sonra hikâye.", "hiz": 1.0, "sonra": 0.2, "duygu": "mutlu"},
        {"metin": "Mekânı, hikâyeye çeviriyoruz.", "hiz": 1.5, "sonra": 0.0}]}]}
    (S / "el_plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1", "ELEVENLABS_API_KEY": "xi-testkey-0123456789abcdef"}
    r = subprocess.run([sys.executable, str(R / ".claude/skills/kurgu-video-studio/scripts/voice_studio.py"), str(S / "el_plan.json"), "-o", str(p / "ses"), "--aday", "5", "--no-fx"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
    ok(r.returncode == 0, "voice_studio çıktı 0: " + (r.stdout + r.stderr).strip()[-160:])
    ok(len(cagri) == 2, f"aday 5 olsa da ücretli motorda parça başına 1 istek gider ({len(cagri)})")
    if len(cagri) == 2:
        ok(cagri[0][1]["model_id"] == "test-model", "model ayardan geldi")
        ok(cagri[1][1]["voice_settings"]["speed"] <= 1.2, "hız 1.2'ye kırpıldı (istenen 1.5)")
    rap = json.loads((p / "ses/rapor.json").read_text(encoding="utf-8"))["t"][0]
    ok(rap["sure"] > 1 and len(rap["parcalar"]) == 2, "rapor: iki parça ve süre")
    gunluk = (p / "bulut_gunlugu.md").read_text(encoding="utf-8")
    ok(len([x for x in gunluk.splitlines() if x.startswith("| 20")]) == 2, "bulut günlüğüne iki satır yazıldı")
finally:
    srv.shutdown()
    shutil.rmtree(p, ignore_errors=True)
    shutil.rmtree(S, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S_))
sys.exit(1 if S_[1] else 0)
