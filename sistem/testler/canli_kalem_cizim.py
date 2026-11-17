"""Kalem çizimi hattı uçtan uca: başsız Chrome (Remotion chrome-headless-shell), Paper.js ve ffmpeg gerekir. Kısa bir video üretir ve yakalama sunucusunun
yol kaçışına karşı korumasını denetler."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
S = [0, 0]
TMP = Path(tempfile.mkdtemp(prefix="yst-kalem-test-"))
env = {**os.environ, "PYTHONUTF8": "1"}


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


try:
    # 1) kısa video: 4 sn x 30 fps, yalnızca ilk 12 kare
    cikti = TMP / "deneme.mp4"
    r = subprocess.run([sys.executable, str(R / "sistem/araclar/kalem_cizim.py"), str(R / "sistem/kit/kalem/ornek/ev-plani.svg"), "-o", str(cikti), "--stil", "karakalem", "--sure", "4", "--kare", "12"],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    ok(r.returncode == 0 and cikti.is_file() and cikti.stat().st_size > 2000, "video üretildi: " + (r.stdout + r.stderr).strip()[-140:])
    if cikti.is_file():
        p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames,width,height", "-of", "json", str(cikti)], capture_output=True, text=True)
        v = json.loads(p.stdout)["streams"][0]
        ok(int(v["nb_read_frames"]) == 12 and v["width"] == 1920 and v["height"] == 1080, f"12 kare, 1920x1080 ({v})")
        # ilk kare dolu: kâğıt rengi değil, ilk darbe 0. karede başlamış olmalı (kareler birbirinden farklı olmalı)
        k0, k11 = TMP / "k0.png", TMP / "k11.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cikti), "-vf", "select=eq(n\\,0)", "-frames:v", "1", str(k0)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cikti), "-vf", "select=eq(n\\,11)", "-frames:v", "1", str(k11)], check=True)
        ok(k0.read_bytes() != k11.read_bytes(), "kareler değişiyor (çizim ilerliyor)")

    # 2) yakalama sunucusu: yalnızca izinli yollar sunulur; ..'li yollar 404
    sahne = TMP / "sahne"
    sahne.mkdir()
    (sahne / "izinli.txt").write_text("selam", encoding="utf-8")
    (sahne / "sayfa.html").write_text("""<!doctype html><meta charset=utf-8><script>
const log = (m) => fetch('/log', {method: 'POST', body: m});
(async () => {
  const dene = async (ad, yol) => { try { const r = await fetch(yol); await log('YOL ' + ad + ' ' + r.status); } catch (e) { await log('YOL ' + ad + ' hata'); } };
  await dene('surucu', '/ortak/surucu.js');
  await dene('paper', '/node_modules/paper/dist/paper-core.js');
  await dene('sahne', '/sahne/izinli.txt');
  await dene('kaçış-ortak', '/ortak/%2e%2e/%2e%2e/%2e%2e/%2e%2e/package.json');
  await dene('kaçış-paper', '/node_modules/paper/%2e%2e/%2e%2e/package.json');
  await dene('kaçış-sahne', '/sahne/%2e%2e/%2e%2e/%2e%2e/%2e%2e/package.json');
  await dene('depo', '/sistem/araclar/kalem_cizim.py');
  await dene('kimlik', '/kimlik/PROFIL.md');
  await fetch('/bitti', {method: 'POST', body: 'tamam'});
})();
</script>""", encoding="utf-8")
    y = subprocess.run([sys.executable, str(R / "sistem/kit/kalem/ortak/yakala.py"), str(sahne / "sayfa.html"), str(TMP / "kareler2")], capture_output=True, text=True, encoding="utf-8", env=env)
    durum = {s.split()[2]: s.split()[3] for s in y.stdout.splitlines() if "YOL " in s}
    ok(durum.get("surucu") == "200" and durum.get("paper") == "200" and durum.get("sahne") == "200", f"izinli yollar sunulur {durum}")
    ok(all(durum.get(k) == "404" for k in ("kaçış-ortak", "kaçış-paper", "kaçış-sahne", "depo", "kimlik")), f"yol kaçışı ve depo dosyaları 404 {durum}")
    # 3) resim -> kalemle çizim -> gerçek resme dönüşüm; son kare gerçek resimle AYNI hizada olmalı
    from PIL import Image, ImageChops, ImageDraw
    im = Image.new("RGB", (480, 270), (225, 225, 225))
    dr = ImageDraw.Draw(im)
    dr.rectangle((60, 50, 260, 220), fill=(40, 60, 120))
    dr.ellipse((300, 70, 420, 190), fill=(180, 50, 50))
    imy = TMP / "resim.png"
    im.save(imy)
    cik2 = TMP / "gecis.mp4"
    r = subprocess.run([sys.executable, str(R / "sistem/araclar/kalem_cizim.py"), str(imy), "-o", str(cik2), "--stil", "karakalem", "--sure", "2", "--gecis", "--bekle", "0.5"],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=400)
    ok(r.returncode == 0 and cik2.is_file(), "resimden geçişli video üretildi: " + (r.stdout + r.stderr).strip()[-120:])
    if cik2.is_file():
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(cik2)], capture_output=True, text=True)
        ok(pr.stdout.strip() != "", "çıktıda kalem sesi (ses akışı) var")
        import numpy as np

        def rms(bas, sure):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(bas), "-t", str(sure), "-i", str(cik2), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768
            return float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
        ok(rms(0.5, 1.0) > 0.004, f"çizim sürerken kalem sesi duyulur (rms {rms(0.5, 1.0):.3f})")
        ok(rms(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(cik2)], capture_output=True, text=True).stdout) - 0.6, 0.4) < 0.002, "çizim bitince (gerçek resim sahnesinde) kalem sesi yok")
        son = TMP / "son.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.1", "-i", str(cik2), "-frames:v", "1", str(son)], check=True)
        beklenen = Image.new("RGB", (1920, 1080), (0, 0, 0))
        beklenen.paste(im.resize((1920, 1080), Image.LANCZOS), (0, 0))
        fark = ImageChops.difference(Image.open(son).convert("RGB").resize((480, 270)), beklenen.resize((480, 270)))
        ort = sum(sum(px) for px in fark.getdata()) / (480 * 270 * 3)
        ok(ort < 6.0, f"son kare gerçek resimle aynı hizada (ortalama fark {ort:.1f}/255)")
        orta = TMP / "orta.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.2", "-i", str(cik2), "-frames:v", "1", str(orta)], check=True)
        farkli = ImageChops.difference(Image.open(orta).convert("RGB").resize((480, 270)), beklenen.resize((480, 270)))
        ok(sum(sum(px) for px in farkli.getdata()) / (480 * 270 * 3) > 8.0, "geçişten önce kare hâlâ çizim (gerçek resimden belirgin farklı)")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
