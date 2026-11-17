import tempfile
import json, os, subprocess, sys, time
from pathlib import Path
from PIL import Image, ImageDraw

R = Path(__file__).resolve().parents[2]
SC = Path(tempfile.mkdtemp(prefix="yst-test-"))
SC.mkdir(exist_ok=True)
sys.path.insert(0, str(R / "sistem" / "araclar"))
import mekan_gezisi as M
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


def oda(yol, ton):
    """Perspektifli sentetik oda: zemin, arka duvar, yan duvarlar, kapı ve mobilya blokları."""
    W, H = 2000, 1300
    im = Image.new("RGB", (W, H), (200, 195, 185)); d = ImageDraw.Draw(im)
    ax, ay, bx, by = 600, 380, 1400, 880  # arka duvar dikdörtgeni
    d.polygon([(0, 0), (W, 0), (bx, ay), (ax, ay)], fill=(235, 232, 225))   # tavan
    d.polygon([(0, H), (W, H), (bx, by), (ax, by)], fill=(150 + ton, 120, 95))  # zemin
    d.polygon([(0, 0), (ax, ay), (ax, by), (0, H)], fill=(190, 186 + ton // 2, 178))  # sol duvar
    d.polygon([(W, 0), (bx, ay), (bx, by), (W, H)], fill=(205, 200, 190 + ton // 2))  # sağ duvar
    d.rectangle([ax, ay, bx, by], fill=(222, 218, 210))
    d.rectangle([900, 450, 1100, 880], fill=(110, 80, 55), outline=(60, 40, 30), width=6)  # kapı
    d.rectangle([700, 600, 860, 880], fill=(70 + ton, 90, 130))  # uzak dolap
    d.rectangle([300, 850, 760, 1200], fill=(120, 60 + ton, 60), outline=(40, 20, 20), width=8)  # yakın koltuk
    d.rectangle([1350, 800, 1750, 1250], fill=(60, 110 + ton, 80), outline=(20, 40, 30), width=8)  # yakın sehpa
    for i in range(12):
        d.line([(0, H - i * 20), (W, H - i * 20)], fill=(140, 110, 85), width=2)
    im.save(yol, quality=92)


oda(SC / "oda1.jpg", 10); oda(SC / "oda2.jpg", 50)
# kişi (sunucu) görseli
kisi = Image.new("RGB", (600, 800), (50, 60, 90)); ImageDraw.Draw(kisi).ellipse([200, 120, 400, 360], fill=(230, 190, 160)); ImageDraw.Draw(kisi).rectangle([150, 380, 450, 800], fill=(20, 30, 60)); kisi.save(SC / "kisi.png")

t = time.time()
d, kay = M.derinlik(SC / "oda1.jpg", SC / "derinlik.png")
print(f"   derinlik {time.time() - t:.1f} sn, kaynak: {kay}")
ok(kay == "Depth Anything V2 Small" and d.shape == (1300, 2000) and 0.0 <= d.min() and d.max() <= 1.0, f"gerçek derinlik modeli çalıştı: {kay}, {d.shape}")
ds = M.sahte_derinlik(2000, 1300)
ok(ds[1250, 1000] > ds[50, 1000], "yaklaşık derinlik: alt yakın, üst uzak")
# model derinliği mantıklı mı: yakın koltuk (alt-sol) uzak dolaptan (arka) yakın
ok(d[1050, 500] > d[700, 780], f"yakın koltuk ({d[1050,500]:.2f}) uzak dolaptan ({d[700,780]:.2f}) daha yakın görünüyor")
t = time.time()
r = M.klip(SC / "oda1.jpg", SC / "klip_ileri.mp4", 3, 24, (960, 540), "ileri", derinlik_png=SC / "derinlik.png")
print(f"   klip (960x540, 72 kare) {time.time() - t:.1f} sn")
ok(Path(r["dosya"]).stat().st_size > 20000 and r["kare"] == 72, f"ileri klip üretildi ({Path(r['dosya']).stat().st_size // 1024} KB)")
r2 = M.klip(SC / "oda1.jpg", SC / "klip_sol.mp4", 3, 24, (960, 540), "sol", derinlik_png=SC / "derinlik.png")
r3 = M.klip(SC / "oda1.jpg", SC / "klip_sahte.mp4", 2, 24, (540, 960), "ileri", sahte=True)
ok(r3["derinlik"] == "yaklaşık", "model olmadan yaklaşık derinlikle de klip üretiliyor (dikey 540x960)")
for ad in ("klip_ileri", "klip_sol"):
    for ts, ek in ((0.05, "a"), (2.9, "b")):
        subprocess.run([M.ffmpeg(), "-v", "error", "-y", "-ss", str(ts), "-i", str(SC / f"{ad}.mp4"), "-frames:v", "1", str(SC / f"{ad}_{ek}.png")], check=True)
# parallax gerçekten derinliğe göre mi: ilk/son karede yakın ve uzak nesnenin kayması farklı olmalı
from PIL import ImageChops
a, b = Image.open(SC / "klip_sol_a.png").convert("L"), Image.open(SC / "klip_sol_b.png").convert("L")
fark = ImageChops.difference(a, b)
ok(fark.getbbox() is not None and sum(fark.getdata()) / (fark.width * fark.height) > 1.0, "ilk ve son kare birbirinden farklı (kamera hareket etti)")
t = time.time()
g = M.gezi([str(SC / "oda1.jpg"), str(SC / "oda2.jpg")], str(SC / "gezi.mp4"), 2.5, False, None, str(SC / "kisi.png"), "Dijital sunum", sahte=True)
print(f"   gezi {time.time() - t:.1f} sn", g)
ok(g["sure"] > 4.0 and g["sunucu"] and g["etiket"], f"iki fotoğraflı gezi + sunucu penceresi + etiket: {g['sure']} sn")
# sesli
subprocess.run([M.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=3", str(SC / "ses.wav")], check=True)
g2 = M.gezi([str(SC / "oda1.jpg")], str(SC / "gezi_dikey_sesli.mp4"), 2.5, True, str(SC / "ses.wav"), None, None, sahte=True)
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(SC / "gezi_dikey_sesli.mp4")], capture_output=True, text=True).stdout)
tur = {s["codec_type"]: s for s in pr["streams"]}
ok(tur["video"]["width"] == 1080 and tur["video"]["height"] == 1920 and "audio" in tur, f"dikey 1080x1920 + ses akışı: {tur['video']['width']}x{tur['video']['height']}")
subprocess.run([M.ffmpeg(), "-v", "error", "-y", "-ss", "1.5", "-i", str(SC / "gezi.mp4"), "-frames:v", "1", "-vf", "scale=960:-1", str(SC / "gezi_kare.png")], check=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
