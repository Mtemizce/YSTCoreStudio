import tempfile
import json, shutil, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8700"
K = Path(tempfile.mkdtemp(prefix="yst-test-"))
ORNEK = (Path(__file__).resolve().parents[2] / "kimlik/ses/ornek.wav")
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def api(yol, govde=None, ham=None, post=None):
    veri = ham if ham is not None else (json.dumps(govde).encode() if govde is not None else (b"{}" if post else None))
    r = urllib.request.Request(B + yol, data=veri, method="POST" if veri is not None else "GET", headers={"X-Panel": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=300) as x:
            raw = x.read()
            return x.status, (json.loads(raw) if x.headers.get("Content-Type", "").startswith("application/json") else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def webm(ad):
    c = K / (ad + ".webm")
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-y", "-i", str(K / (ad + ".wav")), "-c:a", "libopus", str(c)], check=True)
    return c.read_bytes()


def ornekleri_uret():
    """Örnek sesler depoda tutulmaz: temiz konuşmayı Pocket TTS'in hazır sesiyle üretir, gürültülü sürümü ffmpeg'le türetir."""
    import os
    kok = Path(__file__).resolve().parents[2]
    kod = ("import sys; sys.path.insert(0, %r)\nfrom tts.pocket import MOTOR\n"
           "r = MOTOR.uret([('a', {'metin': 'Merhaba, ben bugün yeni bir proje için kısa bir tanıtım videosu hazırlıyorum ve bunu kendi sesimle anlatacağım. Umarım sonuç güzel olur.', "
           "'ses': 'male_1', 'seed': 3})], {}, %r, 24000)\nprint(r['a'])\n") % (str(kok / "sistem"), str(K / "u"))
    p = subprocess.run([sys.executable, "-I", "-c", kod], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"}, cwd=str(kok))
    if p.returncode != 0:
        raise SystemExit("örnek ses üretilemedi (Pocket TTS kurulu mu?): " + p.stderr[-300:])
    ff = shutil.which("ffmpeg") or "ffmpeg"
    shutil.copy(p.stdout.strip().splitlines()[-1], K / "iyi.wav")
    subprocess.run([ff, "-v", "error", "-y", "-i", str(K / "iyi.wav"), "-f", "lavfi", "-i", "anoisesrc=color=white:amplitude=0.06:sample_rate=24000",
                    "-filter_complex", "[0][1]amix=inputs=2:duration=first:normalize=0", str(K / "gurultulu.wav")], check=True)


def dene_bekle():
    for _ in range(150):
        s, d = api("/api/klon/dene")
        if not d["calisiyor"]:
            return d
        time.sleep(2)
    return {"hata": "zaman aşımı"}


assert not ORNEK.exists(), "kayıtlı gerçek klon örneğin var; test onu silmesin diye durdu (önce yedekle)"
ornekleri_uret()
for ad in ("iyi", "gurultulu"):
    print("=====", ad)
    s, d = api("/api/klon/ornek?uz=webm", ham=webm(ad))
    k = d.get("kalite") or {}
    ok(s == 200 and k.get("genel") in ("iyi", "orta", "zayif") and len(k.get("olcutler", [])) == 5, f"{ad}: ölçütler döndü genel={k.get('genel')}")
    print("     ", " ; ".join(f"{o['ad']}={o['deger']}/{o['seviye']}" for o in k.get("olcutler", [])))
    s, d2 = api("/api/klon")
    ok(d2["kalite"]["genel"] == k.get("genel"), "durumda kalite kalıcı")
    t0 = time.time()
    s, d3 = api("/api/klon/dene", post=True)
    ok(s == 200, "deneme başladı")
    s, d3b = api("/api/klon/dene", post=True)
    ok(s >= 400 and "sürüyor" in json.dumps(d3b, ensure_ascii=False), "ikinci eşzamanlı deneme reddedilir")
    d = dene_bekle()
    ok(d.get("sonuc") and not d.get("hata"), f"deneme bitti ({time.time() - t0:.0f} sn) hata={d.get('hata')}")
    if d.get("sonuc"):
        r = d["sonuc"]
        print(f"      anlaşılırlık %{r['anlasilirlik']} ({r['seviye']}); çözüm: {r['cozum']}")
        s, wav = api("/api/klon/deneme.wav")
        ok(s == 200 and wav[:4] == b"RIFF" and len(wav) > 30000, f"deneme sesi sunuluyor ({len(wav)} bayt)")
        s, d4 = api("/api/klon")
        ok(d4["kalite"].get("dene", {}).get("anlasilirlik") == r["anlasilirlik"], "deneme sonucu kalıcı")

api("/api/klon/sil", post=True)
s, d = api("/api/klon")
ok(d["ornek"] is False and d["kalite"] is None and not ORNEK.with_name("deneme.wav").exists(), "silince ölçüm ve deneme sesi de gider")
s, d = api("/api/klon/dene", post=True)
ok(s >= 400, "örneksiz deneme reddedilir")
print(f"{S[0]} başarılı, {S[1]} başarısız")
sys.exit(1 if S[1] else 0)
