import json, os, shutil, subprocess, sys, time
S_ = [0, 0]
def ok(c, m):
    S_[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)
from pathlib import Path

R = Path(__file__).resolve().parents[2]
PY = sys.executable
p = R / "projeler" / "zz-ses"
if p.exists(): shutil.rmtree(p)
(p / "ana/ses").mkdir(parents=True)
plan = {"motor": "ema", "satirlar": [
    {"id": "giris", "kuyruk": 0.2, "parcalar": [{"metin": "Burası bir şantiyeydi.", "hiz": 1.0, "sonra": 0.2}, {"metin": "Şimdi teslime hazır.", "hiz": 1.0, "sonra": 0.0}]},
    {"id": "kapanis", "kuyruk": 0.3, "parcalar": [{"metin": "Mekânı, hikâyeye çeviriyoruz.", "hiz": 0.95, "sonra": 0.0}]}]}
(p / "ana/ses/plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
env = {**os.environ, "PYTHONUTF8": "1"}
t = time.time()
r = subprocess.run([PY, str(R / ".claude/skills/kurgu-video-studio/scripts/voice_studio.py"), str(p / "ana/ses/plan.json"), "-o", str(p / "ana/ses"), "--aday", "1"],
                   capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
ok(r.returncode == 0, "ilk üretim")
ilk = {f.name: f.stat().st_mtime for f in (p / "ana/ses").glob("*.wav")}
(p / "degisiklik.json").write_text(json.dumps({"giris": ["Burası bir şantiyeydi, evet gerçekten.", "Şimdi teslime hazır."]}, ensure_ascii=False), encoding="utf-8")
time.sleep(1.1)
r = subprocess.run([PY, str(R / "sistem/araclar/ses_duzenle.py"), "uygula", "zz-ses", "--duzenleme", str(p / "degisiklik.json")], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
ok(r.returncode == 0, "düzenleme çıktı 0: " + (r.stdout.strip()[-200:] or r.stderr.strip()[-200:]))
son = {f.name: f.stat().st_mtime for f in (p / "ana/ses").glob("*.wav")}
yeni_ = sorted(n for n in son if son[n] != ilk.get(n)); dok_ = sorted(n for n in son if son[n] == ilk.get(n))
ok(any(n.startswith("giris") for n in yeni_) and any(n.startswith("kapanis") for n in dok_), f"yalnızca değişen satır yeniden üretildi: {yeni_} / dokunulmayan {dok_}")
ok((p / "ana/ses/plan.json.yedek").is_file() and "evet gerçekten" in (p / "ana/ses/plan.json").read_text(encoding="utf-8"), "yedek alındı, plan güncellendi")
rap = json.loads((p / "ana/ses/rapor.json").read_text(encoding="utf-8")); ok(set(rap) >= {"giris", "kapanis"}, "rapor iki satırı içeriyor")
r = subprocess.run([PY, str(R / "sistem/araclar/ses_duzenle.py"), "uygula", "zz-ses", "--duzenleme", str(p / "degisiklik.json")], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(R))
ok("değişiklik yok" in json.loads(r.stdout)["mesaj"], "aynı metin tekrar gönderilince üretim yapılmaz")
shutil.rmtree(p)

print("SONUÇ: %d tamam, %d hata" % tuple(S_))
sys.exit(1 if S_[1] else 0)
