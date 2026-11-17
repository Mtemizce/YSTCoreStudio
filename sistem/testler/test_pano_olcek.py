"""Pano'nun proje sayısıyla ölçeklenmesi (N+1 koruması): ayar çözümleme çağrısı proje sayısıyla artmamalı; proje ayarı genel ayarı yine ezmeli."""
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "sistem/panel"))
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


sp = importlib.util.spec_from_file_location("panelmod", R / "sistem/panel/panel.py")
P = importlib.util.module_from_spec(sp)
sp.loader.exec_module(P)
A = P.ek().ayar()
yapilan = []
try:
    for i in range(25):
        d = R / "projeler" / f"zz-olcek-{i:02d}"
        (d / "kaynak/foto").mkdir(parents=True, exist_ok=True)
        (d / "brief.md").write_text("x", encoding="utf-8")
        (d / "uretim.json").write_text(json.dumps({"platformlar": ["x"]}), encoding="utf-8")
        yapilan.append(d)
    (yapilan[0] / "ayar.json").write_text(json.dumps({"ajanlar": {"senarist": {"model": "haiku", "effort": "low"}}}), encoding="utf-8")
    P.pano()  # ısıt
    sayac = {"coz": 0, "ajan": 0}
    coz0, ajan0 = A.coz, A.ajan

    def coz(*a, **k):
        sayac["coz"] += 1
        return coz0(*a, **k)

    A.coz = coz
    t = time.time()
    r = P.pano()
    sure = time.time() - t
    A.coz = coz0
    ok(sayac["coz"] <= 6, f"25 projede ayar çözümleme çağrısı proje sayısıyla artmıyor ({sayac['coz']} çağrı)")
    ok(sure < 1.5, f"25 projeli pano {sure * 1000:.0f} ms (sınır 1500 ms)")
    p0 = next(p for p in r["projeler"] if p["ad"] == "zz-olcek-00")["ajanlar"]["senarist"]
    p1 = next(p for p in r["projeler"] if p["ad"] == "zz-olcek-01")["ajanlar"]["senarist"]
    ok(p0["model"] == "haiku" and p0["effort"] == "low", "proje ayar.json'u genel ayarı ezer")
    ok(p1["model"] != "haiku", "ayarı olmayan proje genel ayarı kullanır")
    # harcama günlüğü: dosya değişmedikçe yeniden okunmaz
    h1 = P.harcama_ozeti()
    h2 = P.harcama_ozeti()
    ok(h1 is h2, "harcama özeti dosya değişmedikçe önbellekten gelir")
finally:
    for d in yapilan:
        shutil.rmtree(d, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
