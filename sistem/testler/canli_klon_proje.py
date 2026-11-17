import json, os, shutil, subprocess, sys, tempfile, urllib.request, urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
B = "http://127.0.0.1:8700"
tmp = Path(tempfile.mkdtemp(prefix="klontest2-"))
S = [0, 0]
ORNEK = R / "kimlik" / "ses" / "ornek.wav"
assert not ORNEK.exists()


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def api(yol, govde=None, ham=None):
    veri = ham if ham is not None else json.dumps(govde if govde is not None else {}).encode()
    r = urllib.request.Request(B + yol, data=veri, method="POST", headers={"X-Panel": "1", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=300) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# tarayıcı kaydı gibi: konuşma benzeri 6 sn (ton) → webm/opus
ff = shutil.which("ffmpeg") or "ffmpeg"
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=200:duration=6", "-c:a", "libopus", str(tmp / "k.webm")], check=True)
webm = (tmp / "k.webm").read_bytes()
s, d = api("/api/uret", {"prompt": "Klon deneme projesi iki: kısa video", "platformlar": ["youtube"] if False else [next(iter(json.loads(urllib.request.urlopen(urllib.request.Request(B + "/api/ayar", headers={"X-Panel": "1"})).read())["platformlar"]))],
                         "seslendirme": {"acik": True, "saglayici": "ema"}})
ok(s == 200, f"proje kuruldu {d}")
pr = R / "projeler" / d["proje"]
s, k = api(f"/api/ses/kaydet?proje={d['proje']}&uz=webm", ham=webm)
ok(s == 200 and k["dosya"].endswith(".wav"), f"proje sesi kaydedildi {k.get('dosya')}")
ad = k["dosya"].split("/")[-1]

s, x = api("/api/klon/projeden", {"proje": d["proje"], "dosya": ad, "onay": False})
ok(s >= 400 and "kabul" in json.dumps(x, ensure_ascii=False), "onaysız reddedilir")
s, x = api("/api/klon/projeden", {"proje": d["proje"], "dosya": "../../x.wav", "onay": True})
ok(s >= 400, f"yol kaçışı reddedilir {x}")
s, x = api("/api/klon/projeden", {"proje": d["proje"], "dosya": "kayit-99.wav", "onay": True})
ok(s >= 400 and "yok" in json.dumps(x, ensure_ascii=False), "olmayan kayıt reddedilir")
s, x = api("/api/klon/projeden", {"proje": d["proje"], "dosya": ad, "onay": True})
ok(s == 200 and x.get("ok") and x["sure"] > 3, f"kayıt klon örneği yapıldı {x}")
ok(ORNEK.is_file() and (pr / "klon" / "ornek.wav").is_file(), "genel örnek ve proje kopyası var")
u = json.loads((pr / "uretim.json").read_text(encoding="utf-8"))["seslendirme"]
ok(u.get("klon") and u.get("motor") == "pocket-tr" and u.get("klon_yol") == "klon/ornek.wav", f"uretim.json güncellendi {u}")
ok("KENDİ SESİYLE" in (pr / "brief.md").read_text(encoding="utf-8"), "brief.md'ye talimat eklendi")

api("/api/klon/sil")
shutil.rmtree(pr, ignore_errors=True)
(R / "sistem" / "ortam" / "yerel" / f"sihirbaz_{pr.name}.json").unlink(missing_ok=True)
shutil.rmtree(tmp, ignore_errors=True)
print(f"{S[0]} başarılı, {S[1]} başarısız")
sys.exit(1 if S[1] else 0)
