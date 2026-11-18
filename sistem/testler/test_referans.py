"""referans skill'i (kaynak: leodavincs/kalem, MIT): sahne bulma ve istem sayfası. Sentetik videoyla; ffmpeg gerekir, ağ gerekmez."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
BETIK = R / ".claude/skills/referans/scripts"
S = [0, 0]
TMP = Path(tempfile.mkdtemp(prefix="yst-referans-"))
FF = shutil.which("ffmpeg") or "ffmpeg"


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


try:
    # üç sert kesimli video: kırmızı 3 sn, mavi 3 sn, yeşil 3 sn (her biri farklı doku için testsrc'li)
    parcalar = []
    for i, renk in enumerate(("red", "blue", "green")):
        p = TMP / f"p{i}.mp4"
        subprocess.run([FF, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={renk}:s=320x240:r=10:d=3", "-pix_fmt", "yuv420p", str(p)], check=True)
        parcalar.append(p)
    (TMP / "liste.txt").write_text("".join(f"file '{p.name}'\n" for p in parcalar), encoding="utf-8")
    video = TMP / "deneme video.mp4"  # boşluklu ad: yol işleme sağlam mı
    subprocess.run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "liste.txt", "-c", "copy", video.name],
                   cwd=TMP, check=True)

    cikti = TMP / "cikti"
    r = subprocess.run([sys.executable, str(BETIK / "sahne_bul.py"), str(video), "--cikti", str(cikti)], capture_output=True, text=True, encoding="utf-8")
    ok(r.returncode == 0, "sahne_bul çalıştı: " + (r.stdout + r.stderr).strip()[-120:])
    sj = json.loads((cikti / "sahneler.json").read_text(encoding="utf-8"))
    ok(len(sj["sahneler"]) == 3, f"üç sert kesim → üç sahne ({len(sj['sahneler'])})")
    ok(all(len(s["kareler"]) == 3 and all((cikti / k).is_file() for k in s["kareler"]) for s in sj["sahneler"]), "her sahne için üç kare dosyası var")
    ok(all(s["sure"] <= 8 for s in sj["sahneler"]) and abs(sj["toplam_sure"] - 9) < 0.5, "süreler 8 sn sınırında, toplam ~9 sn")

    # varsayılan çıktı konumu referanslar/<ad>/ (projeler/ değil: panel proje sanmasın)
    ayri = subprocess.run([sys.executable, str(BETIK / "sahne_bul.py"), str(video), "--en-uzun", "2"], capture_output=True, text=True, encoding="utf-8")
    varsayilan = R / "referanslar" / "deneme video"
    ok(ayri.returncode == 0 and (varsayilan / "sahneler.json").is_file() and not (R / "projeler" / "referans-deneme video").exists(), "varsayılan çıktı referanslar/<ad>/ altına yazılır")
    sj2 = json.loads((varsayilan / "sahneler.json").read_text(encoding="utf-8"))
    ok(len(sj2["sahneler"]) >= 5, f"--en-uzun 2: uzun sahneler bölünür ({len(sj2['sahneler'])})")

    # olmayan video
    yok = subprocess.run([sys.executable, str(BETIK / "sahne_bul.py"), str(TMP / "yok.mp4")], capture_output=True, text=True, encoding="utf-8")
    ok(yok.returncode != 0, "olmayan video açık hatayla reddedilir")

    # istem sayfası: kaçış (XSS) ve eksik sahne uyarısı
    ist = {"video": "x.mp4", "ozet": "<b>özet</b>", "stil": "film grain",
           "sahneler": [{"no": 1, "sure": 3.0, "aciklama": "<script>alert(1)</script>", "kamera": "wide", "istem": "A red room </pre><script>x()</script>"},
                        {"no": 2, "sure": 3.0, "istem": "A blue room"}]}
    (cikti / "istemler.json").write_text(json.dumps(ist, ensure_ascii=False), encoding="utf-8")
    h = subprocess.run([sys.executable, str(BETIK / "html_yap.py"), str(cikti)], capture_output=True, text=True, encoding="utf-8")
    ok(h.returncode == 0 and "UYARI: istemi olmayan sahneler: [3]" in h.stdout, "sayfa üretildi ve istemsiz sahne uyarısı verildi: " + h.stdout.strip()[:90])
    sayfa = (cikti / "istemler.html").read_text(encoding="utf-8")
    ok("<script>alert(1)</script>" not in sayfa and "<script>x()</script>" not in sayfa and "&lt;script&gt;" in sayfa, "istemlerdeki HTML/script kaçışlanır")
    ok("Hepsini kopyala" in sayfa and sayfa.count('<section class="kart">') == 2, "kopyala düğmesi ve iki sahne kartı")
    md = (cikti / "istemler.md").read_text(encoding="utf-8")
    ok("## Sahne 1" in md and "A blue room" in md, "istemler.md yazıldı")
    # sayı olmayan sahne no/süre HTML'e ham girmez
    ist["sahneler"][0]["no"] = "1<img src=x>"
    (cikti / "istemler.json").write_text(json.dumps(ist, ensure_ascii=False), encoding="utf-8")
    kot = subprocess.run([sys.executable, str(BETIK / "html_yap.py"), str(cikti)], capture_output=True, text=True, encoding="utf-8")
    ok(kot.returncode != 0, "sayı olmayan sahne numarası reddedilir")
finally:
    shutil.rmtree(R / "referanslar" / "deneme video", ignore_errors=True)
    shutil.rmtree(TMP, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
