import json, os, shutil, subprocess, sys, tempfile, urllib.request, urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

R = Path(__file__).resolve().parents[2]
PY = Path(sys.executable)
FF = shutil.which("ffmpeg") or "ffmpeg"
B = "http://127.0.0.1:8700"
tmp = Path(tempfile.mkdtemp(prefix="klontest-"))
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def api(yol, govde=None, ham=None, yontem=None):
    veri = ham if ham is not None else (json.dumps(govde).encode() if govde is not None else (b"{}" if (yontem or "").upper() == "POST" else None))
    r = urllib.request.Request(B + yol, data=veri, method=yontem or ("POST" if veri is not None else "GET"), headers={"X-Panel": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=300) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


ORNEK = R / "kimlik" / "ses" / "ornek.wav"
assert not ORNEK.exists(), "gerçek klon örneği var; test iptal"

# gerçek konuşma örneği: Pocket TTS hazır sesiyle ~7 sn, sonra tarayıcı gibi webm/opus'a çevir
wav = tmp / "konusma.wav"
kod = (
    "import sys; sys.path.insert(0, r'%s')\n"
    "from tts.pocket import MOTOR\n"
    "r = MOTOR.uret([('a', {'metin': 'Merhaba, ben bugün yeni bir proje için kısa bir tanıtım videosu hazırlıyorum ve bunu kendi sesimle anlatacağım.', 'ses': 'male_1'})], {}, r'%s', 24000)\n"
    "print(r['a'])\n" % (R / "sistem", tmp / "uretim")
)
p = subprocess.run([str(PY), "-I", "-c", kod], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"), cwd=str(R))
yol = (p.stdout.strip().splitlines() or [""])[-1]
ok(p.returncode == 0 and Path(yol).is_file(), "örnek konuşma üretildi: " + (p.stderr[-200:] if p.returncode else yol))
subprocess.run([FF, "-v", "error", "-y", "-i", yol, "-c:a", "libopus", str(tmp / "kayit.webm")], check=True)
webm = (tmp / "kayit.webm").read_bytes()

s, d = api("/api/klon")
ok(s == 200 and d["hazir"] is True and d["ornek"] is False, f"durum: bileşen hazır, örnek yok {d}")

s, d = api("/api/klon/ornek?uz=webm", ham=b"x" * 100)
ok(s >= 400, "çok küçük ses reddedilir")

s, d = api("/api/klon/ornek?uz=webm", ham=webm)
ok(s == 200 and d.get("ok") and 3 < d["sure"] <= 20, f"örnek kaydedildi {d}")
ok(ORNEK.is_file(), "kimlik/ses/ornek.wav oluştu")
s, d = api("/api/klon")
ok(d["ornek"] is True and d["sure"], f"durum: örnek var {d['sure']} sn")

# rıza kapısı artık motorda değil: göreli yolla, klon_riza olmadan üretir
kod2 = (
    "import sys; sys.path.insert(0, r'%s')\n"
    "from tts.pocket import MOTOR\n"
    "r = MOTOR.uret([('b', {'metin': 'Bu cümleyi örnek sesin tınısıyla okuyorum.', 'klon': r'%s'})], {}, r'%s', 24000)\n"
    "print(r['b'])\n" % (R / "sistem", ORNEK, tmp / "klonlu")
)
p = subprocess.run([str(PY), "-I", "-c", kod2], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"), cwd=str(R))
yol2 = (p.stdout.strip().splitlines() or [""])[-1]
ok(p.returncode == 0 and Path(yol2).is_file() and Path(yol2).stat().st_size > 20000, "motor klon_riza istemeden klonlu ses üretti: " + (p.stderr[-250:] if p.returncode else ""))

# üret: onaysız reddedilir, onaylı proje kurulur
s, a = api("/api/ayar")
plat = [next(iter((a.get("platformlar") or {"youtube-shorts": 1}).keys()))]
govde = {"prompt": "Klon testi: kısa bir deneme videosu üret", "platformlar": plat, "seslendirme": {"acik": True, "saglayici": "ema", "klon": True}}
s, d = api("/api/uret", govde)
ok(s >= 400 and "kabul" in json.dumps(d, ensure_ascii=False), f"onaysız klon reddedilir: {d}")
govde["seslendirme"]["klon_onay"] = True
s, d = api("/api/uret", govde)
ok(s == 200 and d.get("proje"), f"onaylı klonlu proje kuruldu {d}")
pr = R / "projeler" / d.get("proje", "yok")
if pr.is_dir():
    u = json.loads((pr / "uretim.json").read_text(encoding="utf-8"))["seslendirme"]
    ok(u.get("klon") and u.get("motor") == "pocket-tr" and u.get("klon_yol") == "klon/ornek.wav" and u.get("klon_onay"), f"uretim.json klon alanları {u}")
    ok((pr / "klon" / "ornek.wav").is_file(), "örnek proje klasörüne kopyalandı")
    brief = (pr / "brief.md").read_text(encoding="utf-8") if (pr / "brief.md").is_file() else ""
    ok("KENDİ SESİ" in brief and "pocket-tr" in brief, "brief.md orkestratöre klon talimatını taşıyor")
    shutil.rmtree(pr, ignore_errors=True)
    (R / "sistem" / "ortam" / "yerel" / f"sihirbaz_{pr.name}.json").unlink(missing_ok=True)

# örneksiz klon reddedilir
api("/api/klon/sil", {}, yontem="POST")
s, d = api("/api/klon")
ok(d["ornek"] is False and not ORNEK.exists(), "silince örnek kalkar")
govde["seslendirme"]["klon_onay"] = True
s, d = api("/api/uret", govde)
ok(s >= 400 and "örneği yok" in json.dumps(d, ensure_ascii=False), f"örneksiz klon reddedilir: {d}")
for k in (R / "projeler").iterdir() if (R / "projeler").is_dir() else []:
    if k.name.startswith("klon-testi"):
        shutil.rmtree(k, ignore_errors=True)

shutil.rmtree(tmp, ignore_errors=True)
print(f"{S[0]} başarılı, {S[1]} başarısız")
sys.exit(1 if S[1] else 0)
