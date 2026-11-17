"""Görsel kütüphanesi (sistem/araclar/gorsel_kutuphane.py): üretim akışı, kalite ölçütü, onay/ret/silme, yeniden üretim, projeye ekleme. Model gerekmez (sahte üretici)."""
import importlib.util
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ["YST_GORSEL_SAHTE"] = "1"
R = Path(__file__).resolve().parents[2]
S = [0, 0]


def ok(c, m):
    S[0 if c else 1] += 1
    print(("OK   " if c else "FAIL ") + m)


sp = importlib.util.spec_from_file_location("gk_t", R / "sistem/araclar/gorsel_kutuphane.py")
G = importlib.util.module_from_spec(sp)
sys.modules["gk_t"] = G
sp.loader.exec_module(G)
tmp = Path(tempfile.mkdtemp(prefix="yst-gorsel-"))
G.KOK, G.TASLAK, G.ONAYLI, G.INDEKS = tmp / "g", tmp / "g" / "taslak", tmp / "g" / "onayli", tmp / "g" / "index.json"
proje = R / "projeler" / "zz-gorsel"
try:
    ids = [s["id"] for s in G.STILLER]
    ok(len(ids) == len(set(ids)) and sum(1 for s in G.STILLER if s["grup"] == "anime") >= 6 and all(s["ek"] and len(s["renk"]) == 2 for s in G.STILLER), f"stil ön ayarları: {len(ids)} stil, en az 6 anime")
    ok("anime style" in G.istem_olustur("bir kız", "anime-aksiyon") and G.istem_olustur("bir kız", None) == "bir kız", "stil, istemin sonuna eklenir")
    for kotu, ne in ((("ab", None), "kısa"), (("x" * 1600, None), "uzun"), (("bir kız", "yok-stil"), "stil")):
        try:
            G.istem_olustur(*kotu)
            ok(False, f"reddedilmeliydi: {ne}")
        except ValueError:
            ok(True, f"geçersiz istem/stil reddedilir ({ne})")

    o = G.uret_tek("kırmızı bir kapı", "sinematik", 1000, 600, 7)
    p = G.yol(o["id"])
    from PIL import Image
    ok(p.parent == G.TASLAK and Image.open(p).size == (960, 576) and o["durum"] == "taslak", "üretim taslak olarak yazılır; boyut 64'ün katına yuvarlanır (1000x600 → 960x576)")
    o2 = G.uret_tek("kırmızı bir kapı", "sinematik", 1000, 600, 7)
    ok(G.yol(o2["id"]).read_bytes() == p.read_bytes() and o2["id"] != o["id"], "aynı tohum aynı görseli verir, kimlik farklıdır")

    düz = tmp / "duz.png"
    Image.new("RGB", (400, 300), (120, 120, 120)).save(düz)
    kz = G.kalite_olc(düz)
    ok(kz["durum"] == "zayif" and any("düz" in x for x in kz["ipucu"]), "kalite: düz resim 'zayıf', ipucu verir (engellemez)")
    import random
    r = random.Random(1)
    g = Image.new("RGB", (400, 300))
    g.putdata([(r.randint(0, 255),) * 3 for _ in range(400 * 300)])
    ok(G.kalite_olc(tmp / "yok.png") if False else G.kalite_olc((g.save(tmp / "gurultu.png"), tmp / "gurultu.png")[1])["durum"] == "iyi", "kalite: ayrıntılı resim 'iyi'")

    G.is_baslat("üç görsel", "anime-duygusal", 640, 384, 3, 100)
    try:
        G.is_baslat("ikinci", None)
        ikinci = False
    except ValueError:
        ikinci = True
    for _ in range(80):
        if not G.is_durum()["calisiyor"]:
            break
        time.sleep(0.1)
    d = G.is_durum()
    toh = [G.al(i)["tohum"] for i in d["idler"]]
    ok(d["tamam"] == 3 and len(d["idler"]) == 3 and toh == [100, 101, 102] and not d["hata"], f"arka plan işi: 3 görsel, ardışık tohum {toh}")
    ok(ikinci, "iş sürerken ikinci iş reddedilir")

    a = o["id"]
    on = G.onayla(a, arsive=False)
    ok(on["durum"] == "onayli" and (G.ONAYLI / f"{a}.png").is_file() and not (G.TASLAK / f"{a}.png").exists(), "onay: dosya taslaktan onaylıya taşınır")
    ok(G.onayla(a, arsive=False)["durum"] == "onayli", "onay tekrarlanabilir (idempotent)")
    try:
        G.reddet(a)
        ok(False, "onaylı görsel reddedilmeliydi")
    except ValueError:
        ok(True, "onaylı görsel reddedilemez")
    rd = G.reddet(o2["id"])
    ok(rd["durum"] == "reddedildi", "taslak reddedilir")
    ok(len(G.liste("onayli")) == 1 and len(G.liste("taslak")) == 3 and len(G.liste("reddedildi")) == 1, "liste süzgeci: durum")
    for kotu in ("../etc/passwd", "g123", "G0123456789", ""):
        try:
            G.al(kotu)
            ok(False, f"geçersiz kimlik kabul edildi: {kotu!r}")
        except ValueError:
            ok(True, f"geçersiz kimlik reddedilir ({kotu!r})")

    G.is_baslat("yeniden", "anime-aksiyon", 512, 512, 1, 5, 8, {"id": "dizi-x", "sezon": 1, "bolum": 2})
    for _ in range(50):
        if not G.is_durum()["calisiyor"]:
            break
        time.sleep(0.1)
    ok(len(G.liste(seri="dizi-x")) == 1 and G.liste(seri="dizi-x")[0]["seri"]["bolum"] == 2, "seri/bölüm bilgisi görsele işlenir ve süzülür")
    n0 = len(G.liste())
    G.yeniden(a)
    for _ in range(50):
        if not G.is_durum()["calisiyor"]:
            break
        time.sleep(0.1)
    yeni = [x for x in G.liste() if x.get("kaynak") == a]
    ok(len(G.liste()) == n0 + 1 and yeni and yeni[0]["istem"] == o["istem"] and yeni[0]["stil"] == "sinematik" and yeni[0]["tohum"] != o["tohum"], "yeniden üret: aynı istem ve stil, yeni tohum")

    try:
        G.projeye(a, "../x")
        ok(False, "geçersiz proje reddedilmeliydi")
    except ValueError:
        ok(True, "projeye ekleme: geçersiz proje adı reddedilir")
    (proje / "ana").mkdir(parents=True, exist_ok=True)
    sn = G.projeye(a, "zz-gorsel", "ana")
    ok((proje / sn["kaynak"]).is_file() and (proje / sn["media"]).is_file(), "projeye ekleme: kaynak/foto ve Kurgu media/foto'ya kopyalanır")
    G.sil(a)
    ok(not (G.ONAYLI / f"{a}.png").exists() and all(x["id"] != a for x in G.liste()), "silme: dosya ve kayıt gider")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(proje, ignore_errors=True)
print("SONUÇ: %d tamam, %d hata" % tuple(S))
sys.exit(1 if S[1] else 0)
