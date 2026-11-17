"""Dikte (mikrofon → yerel Whisper → metin) uçtan uca: gerçek EMA sesiyle bir cümle üretilir, tarayıcı kaydı gibi webm'e çevrilir, panele gönderilir.
Çalışan panel (127.0.0.1:8700), EMA modeli ve Whisper small ister."""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
B = "http://127.0.0.1:8700"
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def sozcukler(m):
    return re.findall(r"[a-zçğıöşü0-9]+", m.replace("İ", "i").replace("I", "ı").lower())


tmp = Path(tempfile.mkdtemp(prefix="dikte-test-"))
(tmp / "ses").mkdir()
CUMLE = "Yirmi yirmi iki ile yirmi yirmi dört arası villa projeleri için öncesi, sonrası ve yapım aşamalarıyla ilgili kırk saniyelik bir video üret."
(tmp / "ses/plan.json").write_text(json.dumps({"motor": "ema", "satirlar": [{"id": "d", "kuyruk": 0.2, "parcalar": [{"metin": CUMLE, "hiz": 1.0, "sonra": 0.0}]}]}, ensure_ascii=False), encoding="utf-8")
try:
    r = subprocess.run([sys.executable, str(R / ".claude/skills/kurgu-video-studio/scripts/voice_studio.py"), str(tmp / "ses/plan.json"), "-o", str(tmp / "ses"), "--aday", "1"],
                       capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, cwd=str(R))
    wav = tmp / "ses/d_take1.wav"
    ok(r.returncode == 0 and wav.is_file(), "test sesi üretildi (EMA)")
    webm = tmp / "kayit.webm"
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ac", "1", "-c:a", "libopus", "-b:a", "32k", str(webm)], check=True)
    req = urllib.request.Request(B + "/api/dikte", data=webm.read_bytes(), method="POST", headers={"X-Panel": "1"})
    j = json.loads(urllib.request.urlopen(req, timeout=400).read())
    benzerlik = difflib.SequenceMatcher(None, sozcukler(CUMLE), sozcukler(j["metin"])).ratio()
    # sayılar rakamla yazılabilir ("2022"): sözcük benzerliği bu yüzden %100 olmaz, ama yüksek olmalı
    ok(benzerlik > 0.6 and j["kelime"] > 8, f"dikte metni özgün cümleye benziyor (%{benzerlik * 100:.0f}): {j['metin'][:90]}")
    ok(j["sure"] > 3 and j["dil"] == "tr", "süre ve dil alanları")
    try:
        urllib.request.urlopen(urllib.request.Request(B + "/api/dikte", data=b"abc", method="POST", headers={"X-Panel": "1"}))
        ok(False, "çok küçük kayıt reddedilmeli")
    except urllib.error.HTTPError as e:
        ok(e.code == 400, "çok küçük kayıt 400 ile reddedilir")
    try:
        urllib.request.urlopen(urllib.request.Request(B + "/api/dikte", data=webm.read_bytes(), method="POST"))
        ok(False, "başlıksız istek reddedilmeli")
    except urllib.error.HTTPError as e:
        ok(e.code == 403, "X-Panel başlığı olmayan istek 403 alır")
    time.sleep(0.3)
    yerel = R / "sistem/ortam/yerel"
    ok(not list(yerel.glob("dikte-*")), "geçici ses dosyaları işlem sonrası silinir")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
